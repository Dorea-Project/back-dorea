"""Sprint 5 — BulkEnrollMembers : import best-effort (échec par ligne, dédup, réutilisation M-2)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.commands.bulk_enroll_members import (
    MAX_BATCH,
    BatchTooLargeError,
    BulkEnrollMembers,
)
from app.contexts.iam.application.dtos import InvitedMemberInput
from app.contexts.iam.application.ports import MemberEnrollmentStore, OwnershipChecker
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import AccountStatus, MembershipStatus, RoleCode
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
    def __init__(self, memberships=()):
        self._m = list(memberships)

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


class _FakeStore(MemberEnrollmentStore):
    def __init__(self):
        self.enrolled = 0
        self.added = 0

    async def enroll(self, **kwargs):
        self.enrolled += 1

    async def add_membership(self, **kwargs):
        self.added += 1


def _member(account_id, tenant_id, role: RoleCode) -> Membership:
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
                group_id=None,
                assigned_at=_NOW,
                assigned_by_account_id=uuid4(),
            )
        ],
    )


def _command(accounts, memberships, store) -> BulkEnrollMembers:
    access = AccessControl(_FakeOwnership(), memberships)
    return BulkEnrollMembers(accounts, memberships, store, access, clock=lambda: _NOW)


async def test_import_reuses_global_accounts_and_rejects_existing_members():
    admin, tenant = uuid4(), uuid4()
    # Compte existant déjà membre ICI → refus. Autre compte global pas membre ici → réutilisé.
    already = Account(id=uuid4(), phone_number="+2250700000002", status=AccountStatus.ACTIVE)
    elsewhere = Account(id=uuid4(), phone_number="+2250700000003", status=AccountStatus.ACTIVE)
    accounts = _FakeAccounts(
        by_phone={already.phone_number: already, elsewhere.phone_number: elsewhere}
    )
    memberships = _FakeMemberships(
        [_member(admin, tenant, RoleCode.ADMIN), _member(already.id, tenant, RoleCode.ADMIN)]
    )
    store = _FakeStore()
    cmd = _command(accounts, memberships, store)

    result = await cmd.execute(
        actor_account_id=admin,
        tenant_id=tenant,
        rows=[
            InvitedMemberInput("+2250700000001", "A"),  # nouveau compte
            InvitedMemberInput("+2250700000002", "B"),  # déjà membre ici → échec
            InvitedMemberInput("+2250700000003", "C"),  # compte global réutilisé
        ],
    )

    assert {r.phone_number for r in result.enrolled} == {"+2250700000001", "+2250700000003"}
    assert result.failed[0].phone_number == "+2250700000002"
    assert result.failed[0].reason == "IAM_DUPLICATE_ACTIVE_MEMBERSHIP"
    assert store.enrolled == 1  # seul "+..01" est un nouveau compte
    assert store.added == 1  # "+..03" réutilise le compte global


async def test_intra_batch_duplicate_fails_the_second():
    admin, tenant = uuid4(), uuid4()
    store = _FakeStore()
    memberships = _FakeMemberships([_member(admin, tenant, RoleCode.ADMIN)])
    cmd = _command(_FakeAccounts(), memberships, store)

    result = await cmd.execute(
        actor_account_id=admin,
        tenant_id=tenant,
        rows=[InvitedMemberInput("+2250700000009"), InvitedMemberInput("+2250700000009")],
    )
    assert len(result.enrolled) == 1
    assert len(result.failed) == 1
    assert result.failed[0].reason == "IAM_DUPLICATE_ROW_IN_BATCH"
    assert store.enrolled == 1


async def test_unauthorized_actor_is_rejected():
    cmd = _command(_FakeAccounts(), _FakeMemberships([]), _FakeStore())
    with pytest.raises(UnauthorizedScopeError):
        await cmd.execute(
            actor_account_id=uuid4(),
            tenant_id=uuid4(),
            rows=[InvitedMemberInput("+2250700000010")],
        )


async def test_batch_too_large_is_rejected():
    admin, tenant = uuid4(), uuid4()
    cmd = _command(
        _FakeAccounts(), _FakeMemberships([_member(admin, tenant, RoleCode.ADMIN)]), _FakeStore()
    )
    rows = [InvitedMemberInput(f"+22507{i:07d}") for i in range(MAX_BATCH + 1)]
    with pytest.raises(BatchTooLargeError):
        await cmd.execute(actor_account_id=admin, tenant_id=tenant, rows=rows)
