"""Sprint 4 — EnrollInvitedMember : fidèle ordinaire en `invited`, sans rôle ni credential."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.commands.enroll_invited_member import EnrollInvitedMember
from app.contexts.iam.application.ports import MemberEnrollmentStore, OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.errors import UnauthorizedScopeError
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeOwnership(OwnershipChecker):
    async def is_active_owner(self, account_id, tenant_id):
        return False


class _FakeAccounts(AccountRepository):
    def __init__(self, by_phone=None):
        self._by_phone = by_phone or {}

    async def get_by_id(self, account_id):
        return None

    async def get_by_phone(self, phone_number):
        return self._by_phone.get(phone_number)


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
        return []

    async def count_active_group_leaders(self, tenant_id, group_id):
        return 0


class _FakeStore(MemberEnrollmentStore):
    def __init__(self):
        self.calls = []
        self.added = []

    async def enroll(self, *, account, membership, creation_source, actor_account_id):
        self.calls.append(
            {
                "account": account,
                "membership": membership,
                "creation_source": creation_source,
            }
        )

    async def add_membership(self, *, membership, actor_account_id):
        self.added.append({"membership": membership, "actor_account_id": actor_account_id})


def _membership(account_id, tenant_id, role: RoleCode, *, group_id=None) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER,
        last_transition_at=_NOW,
        role_assignments=[
            RoleAssignment(
                id=uuid4(),
                role=role,
                group_id=group_id,
                assigned_at=_NOW,
                assigned_by_account_id=uuid4(),
            )
        ],
    )


def _command(memberships, store, accounts=None) -> EnrollInvitedMember:
    access = AccessControl(_FakeOwnership(), memberships)
    return EnrollInvitedMember(
        accounts or _FakeAccounts(), memberships, store, access, clock=lambda: _NOW
    )


async def test_welcome_team_enrolls_a_visitor_without_credential():
    welcome, tenant = uuid4(), uuid4()
    store = _FakeStore()
    ms = _FakeMemberships([_membership(welcome, tenant, RoleCode.WELCOME_TEAM)])

    result = await _command(ms, store).execute(
        actor_account_id=welcome,
        tenant_id=tenant,
        phone_number="+2250700000070",
        first_name="Awa",
    )

    assert result.status == "invited"
    call = store.calls[0]
    assert call["membership"].status is MembershipStatus.INVITED
    assert call["membership"].active_roles() == []
    assert store.added == []  # nouveau compte → enroll(), pas add_membership()
    assert call["creation_source"].value == "walk_in_registration"


async def test_admin_can_enroll_a_member():
    admin, tenant = uuid4(), uuid4()
    store = _FakeStore()
    ms = _FakeMemberships([_membership(admin, tenant, RoleCode.ADMIN)])
    result = await _command(ms, store).execute(
        actor_account_id=admin, tenant_id=tenant, phone_number="+2250700000071"
    )
    assert result.status == "invited"


async def test_pastor_cannot_enroll_a_member():
    pastor, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_membership(pastor, tenant, RoleCode.PASTOR)])
    with pytest.raises(UnauthorizedScopeError):
        await _command(ms, _FakeStore()).execute(
            actor_account_id=pastor, tenant_id=tenant, phone_number="+2250700000072"
        )


async def test_group_leader_scoped_permission_does_not_cover_unscoped_enrollment():
    leader, tenant, group = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_membership(leader, tenant, RoleCode.GROUP_LEADER, group_id=group)])
    with pytest.raises(UnauthorizedScopeError):
        await _command(ms, _FakeStore()).execute(
            actor_account_id=leader, tenant_id=tenant, phone_number="+2250700000073"
        )
