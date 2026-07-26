"""Sprint 4 — RevokeRole & CloseMembership : autorité + garde-fous (faux dépôts)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.commands.close_membership import CloseMembership
from app.contexts.iam.application.commands.revoke_role import RevokeRole
from app.contexts.iam.application.ports import MembershipLifecycleStore, OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipClosureReason, MembershipStatus, RoleCode
from app.contexts.iam.domain.errors import (
    GroupLastLeaderRemovalBlockedError,
    LastOwnerRemovalBlockedError,
    RoleAssignmentNotFoundError,
    UnauthorizedScopeError,
)
from app.contexts.iam.domain.repositories import MembershipRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeMemberships(MembershipRepository):
    def __init__(self, memberships):
        self._m = memberships

    async def get_active(self, account_id, tenant_id):
        return next(
            (
                m
                for m in self._m
                if m.account_id == account_id and m.tenant_id == tenant_id and not m.is_closed
            ),
            None,
        )

    async def list_active_by_account(self, account_id):
        return [m for m in self._m if m.account_id == account_id and not m.is_closed]

    async def count_active_group_leaders(self, tenant_id, group_id):
        return sum(
            1
            for m in self._m
            if m.tenant_id == tenant_id
            for ra in m.active_roles()
            if ra.role is RoleCode.GROUP_LEADER and ra.group_id == group_id
        )


class _FakeStore(MembershipLifecycleStore):
    def __init__(self):
        self.revoked = []
        self.closed = []

    async def revoke_role(self, *, role_assignment_id, revoked_at, reason):
        self.revoked.append({"id": role_assignment_id, "reason": reason})

    async def close_membership(self, *, membership_id, closed_at, closure_reason):
        self.closed.append({"membership_id": membership_id, "closure_reason": closure_reason})


def _m(account, tenant, roles=(), status=MembershipStatus.CONFIRMED_MEMBER) -> Membership:
    ras = [
        RoleAssignment(
            id=uuid4(), role=r, group_id=g, assigned_at=_NOW, assigned_by_account_id=uuid4()
        )
        for (r, g) in roles
    ]
    return Membership(
        id=uuid4(),
        account_id=account,
        tenant_id=tenant,
        status=status,
        last_transition_at=_NOW,
        role_assignments=ras,
    )


class _FakeOwnership(OwnershipChecker):
    def __init__(self, owners=()):
        self._owners = set(owners)  # {(account_id, tenant_id)}

    async def is_active_owner(self, account_id, tenant_id):
        return (account_id, tenant_id) in self._owners


def _revoke(ms, store, *, owners=()):
    return RevokeRole(ms, store, AccessControl(_FakeOwnership(owners), ms), clock=lambda: _NOW)


def _close(ms, store, *, owners=()):
    return CloseMembership(ms, store, AccessControl(_FakeOwnership(owners), ms), clock=lambda: _NOW)


# --- RevokeRole ---


async def test_admin_revokes_a_group_leader_when_others_remain():
    admin, target, other, tenant, group = (uuid4() for _ in range(5))
    store = _FakeStore()
    ms = _FakeMemberships(
        [
            _m(admin, tenant, [(RoleCode.ADMIN, None)]),
            _m(target, tenant, [(RoleCode.GROUP_LEADER, group)]),
            _m(other, tenant, [(RoleCode.GROUP_LEADER, group)]),  # 2ᵉ responsable
        ]
    )
    result = await _revoke(ms, store).execute(
        actor_account_id=admin,
        tenant_id=tenant,
        target_account_id=target,
        role=RoleCode.GROUP_LEADER,
        group_id=group,
    )
    assert result.role == "group_leader"
    assert len(store.revoked) == 1


async def test_cannot_revoke_last_group_leader():
    admin, target, tenant, group = (uuid4() for _ in range(4))
    ms = _FakeMemberships(
        [
            _m(admin, tenant, [(RoleCode.ADMIN, None)]),
            _m(target, tenant, [(RoleCode.GROUP_LEADER, group)]),  # seul responsable
        ]
    )
    with pytest.raises(GroupLastLeaderRemovalBlockedError):
        await _revoke(ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            target_account_id=target,
            role=RoleCode.GROUP_LEADER,
            group_id=group,
        )


async def test_revoke_role_not_assigned_is_404():
    admin, target, tenant = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships(
        [_m(admin, tenant, [(RoleCode.ADMIN, None)]), _m(target, tenant, [])]
    )
    with pytest.raises(RoleAssignmentNotFoundError):
        await _revoke(ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            target_account_id=target,
            role=RoleCode.WELCOME_TEAM,
        )


async def test_network_supervisor_role_cannot_be_revoked_this_way():
    admin, target, tenant = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships(
        [
            _m(admin, tenant, [(RoleCode.ADMIN, None)]),
            _m(target, tenant, [(RoleCode.NETWORK_SUPERVISOR, None)]),
        ]
    )
    with pytest.raises(UnauthorizedScopeError):
        await _revoke(ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            target_account_id=target,
            role=RoleCode.NETWORK_SUPERVISOR,
        )


# --- CloseMembership ---


async def test_admin_closes_a_plain_membership():
    admin, target, tenant = uuid4(), uuid4(), uuid4()
    store = _FakeStore()
    ms = _FakeMemberships(
        [_m(admin, tenant, [(RoleCode.ADMIN, None)]), _m(target, tenant, [])]
    )
    result = await _close(ms, store).execute(
        actor_account_id=admin,
        tenant_id=tenant,
        target_account_id=target,
        closure_reason=MembershipClosureReason.CHANGED_CHURCH,
    )
    assert result.status == "closed"
    assert result.closure_reason == "changed_church"
    assert len(store.closed) == 1


async def test_cannot_close_the_owner():
    # L'Owner est reconnu par la propriété (table ownership), pas par un rôle.
    admin, owner, tenant = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships(
        [_m(admin, tenant, [(RoleCode.ADMIN, None)]), _m(owner, tenant, [])]
    )
    with pytest.raises(LastOwnerRemovalBlockedError):
        await _close(ms, _FakeStore(), owners={(owner, tenant)}).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            target_account_id=owner,
            closure_reason=MembershipClosureReason.OTHER,
        )


async def test_close_blocked_if_it_orphans_a_group():
    admin, target, tenant, group = (uuid4() for _ in range(4))
    ms = _FakeMemberships(
        [
            _m(admin, tenant, [(RoleCode.ADMIN, None)]),
            _m(target, tenant, [(RoleCode.GROUP_LEADER, group)]),  # dernier responsable
        ]
    )
    with pytest.raises(GroupLastLeaderRemovalBlockedError):
        await _close(ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            target_account_id=target,
            closure_reason=MembershipClosureReason.INACTIVITY,
        )


async def test_integration_cannot_close_membership():
    # Intégration a MANAGE_MEMBERSHIP mais PAS CLOSE_MEMBERSHIP → « Admin seul ».
    actor, target, tenant = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships(
        [
            _m(actor, tenant, [(RoleCode.INTEGRATION_TEAM, None)]),
            _m(target, tenant, []),
        ]
    )
    with pytest.raises(UnauthorizedScopeError):
        await _close(ms, _FakeStore()).execute(
            actor_account_id=actor,
            tenant_id=tenant,
            target_account_id=target,
            closure_reason=MembershipClosureReason.OTHER,
        )
