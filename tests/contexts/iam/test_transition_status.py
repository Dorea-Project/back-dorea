"""Sprint 4 — TransitionStatus : autorisation + application de la table, avec faux dépôts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.commands.transition_status import TransitionStatus
from app.contexts.iam.application.ports import MembershipTransitionStore, OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import (
    MembershipStatus,
    MembershipTransitionEvent,
    RoleCode,
)
from app.contexts.iam.domain.errors import (
    MembershipNotFoundError,
    StatusSkipForbiddenError,
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
        return 0


class _FakeStore(MembershipTransitionStore):
    def __init__(self):
        self.calls = []

    async def apply_transition(
        self, *, membership_id, new_status, previous_status, transitioned_at
    ):
        self.calls.append(
            {"membership_id": membership_id, "new_status": new_status, "previous": previous_status}
        )


def _membership(account_id, tenant_id, status, *roles: RoleCode) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=status,
        last_transition_at=_NOW,
        role_assignments=[
            RoleAssignment(
                id=uuid4(),
                role=r,
                group_id=None,
                assigned_at=_NOW,
                assigned_by_account_id=uuid4(),
            )
            for r in roles
        ],
    )


class _FakeOwnership(OwnershipChecker):
    async def is_active_owner(self, account_id, tenant_id):
        return False


def _command(memberships, store) -> TransitionStatus:
    access = AccessControl(_FakeOwnership(), memberships)
    return TransitionStatus(memberships, store, access, clock=lambda: _NOW)


async def test_admin_qualifies_a_visitor_to_sympathizer():
    admin, target, tenant = uuid4(), uuid4(), uuid4()
    store = _FakeStore()
    ms = _FakeMemberships(
        [
            _membership(admin, tenant, MembershipStatus.CONFIRMED_MEMBER, RoleCode.ADMIN),
            _membership(target, tenant, MembershipStatus.VISITOR),
        ]
    )
    result = await _command(ms, store).execute(
        actor_account_id=admin,
        tenant_id=tenant,
        target_account_id=target,
        event=MembershipTransitionEvent.QUALIFY_SYMPATHIZER,
    )
    assert result.status == "sympathizer"
    assert result.previous_status == "visitor"
    assert store.calls[0]["new_status"] is MembershipStatus.SYMPATHIZER


async def test_welcome_team_cannot_transition():
    # welcome_team n'a pas MANAGE_MEMBERSHIP → refusé.
    actor, target, tenant = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships(
        [
            _membership(actor, tenant, MembershipStatus.CONFIRMED_MEMBER, RoleCode.WELCOME_TEAM),
            _membership(target, tenant, MembershipStatus.VISITOR),
        ]
    )
    with pytest.raises(UnauthorizedScopeError):
        await _command(ms, _FakeStore()).execute(
            actor_account_id=actor,
            tenant_id=tenant,
            target_account_id=target,
            event=MembershipTransitionEvent.QUALIFY_SYMPATHIZER,
        )


async def test_skip_is_rejected_through_the_command():
    admin, target, tenant = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships(
        [
            _membership(admin, tenant, MembershipStatus.CONFIRMED_MEMBER, RoleCode.ADMIN),
            _membership(target, tenant, MembershipStatus.INVITED),
        ]
    )
    with pytest.raises(StatusSkipForbiddenError):
        await _command(ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            target_account_id=target,
            event=MembershipTransitionEvent.CONFIRM_MEMBER,
        )


async def test_unknown_target_is_not_found():
    admin, tenant = uuid4(), uuid4()
    ms = _FakeMemberships(
        [_membership(admin, tenant, MembershipStatus.CONFIRMED_MEMBER, RoleCode.ADMIN)]
    )
    with pytest.raises(MembershipNotFoundError):
        await _command(ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            target_account_id=uuid4(),
            event=MembershipTransitionEvent.QUALIFY_SYMPATHIZER,
        )
