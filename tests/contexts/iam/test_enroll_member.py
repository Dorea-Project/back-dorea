"""Sprint 4 — EnrollMember : autorité par rôle (Owner→staff, Admin→équipe), portée & cap.

L'Owner est reconnu par la **propriété** (`AccessControl` 1ᵉʳ étage), pas par un rôle.
Aucun credential n'est posé à l'enrôlement (M-0) ; un compte global existant est réutilisé (M-2).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.commands.enroll_member import EnrollMember
from app.contexts.iam.application.ports import MemberEnrollmentStore, OwnershipChecker
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import AccountStatus, MembershipStatus, RoleCode
from app.contexts.iam.domain.errors import (
    DuplicateActiveMembershipError,
    GroupLeaderCapExceededError,
    RoleNotEnrollableError,
    RoleRequiresGroupError,
    UnauthorizedScopeError,
)
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeOwnership(OwnershipChecker):
    def __init__(self, owners=()):
        self._owners = set(owners)  # {(account_id, tenant_id)}

    async def is_active_owner(self, account_id, tenant_id):
        return (account_id, tenant_id) in self._owners


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
        return [m for m in self._m if m.account_id == account_id and not m.is_closed]

    async def count_active_group_leaders(self, tenant_id, group_id):
        return sum(
            1
            for m in self._m
            if m.tenant_id == tenant_id
            for ra in m.active_roles()
            if ra.role is RoleCode.GROUP_LEADER and ra.group_id == group_id
        )


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
                "actor_account_id": actor_account_id,
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


def _command(accounts, memberships, store, *, owners=()) -> EnrollMember:
    access = AccessControl(_FakeOwnership(owners), memberships)
    return EnrollMember(accounts, memberships, store, access, clock=lambda: _NOW)


async def test_owner_enrolls_a_pastor():
    owner, tenant = uuid4(), uuid4()
    store = _FakeStore()
    # L'Owner est reconnu par la propriété (pas de rôle).
    cmd = _command(_FakeAccounts(), _FakeMemberships([]), store, owners={(owner, tenant)})

    result = await cmd.execute(
        actor_account_id=owner,
        tenant_id=tenant,
        role=RoleCode.PASTOR,
        phone_number="+2250700000050",
        first_name="Paul",
    )

    assert result.role == "pastor"
    created = store.calls[0]
    assert created["membership"].active_roles()[0].role is RoleCode.PASTOR
    # Aucun credential n'est fourni au store à l'enrôlement (M-0) : la signature
    # enroll() ne porte plus password_hash/hash_algo_version.
    assert store.added == []  # nouveau compte → enroll(), pas add_membership()


async def test_admin_enrolls_a_group_leader_with_scope():
    admin, tenant, group = uuid4(), uuid4(), uuid4()
    store = _FakeStore()
    ms = _FakeMemberships([_membership(admin, tenant, RoleCode.ADMIN)])
    result = await _command(_FakeAccounts(), ms, store).execute(
        actor_account_id=admin,
        tenant_id=tenant,
        role=RoleCode.GROUP_LEADER,
        phone_number="+2250700000051",
        group_id=group,
    )
    assert result.role == "group_leader"
    assert result.group_id == group
    assert store.calls[0]["membership"].active_roles()[0].group_id == group


async def test_admin_cannot_enroll_staff():
    admin, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_membership(admin, tenant, RoleCode.ADMIN)])
    with pytest.raises(UnauthorizedScopeError):
        await _command(_FakeAccounts(), ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            role=RoleCode.PASTOR,
            phone_number="+2250700000052",
        )


async def test_owner_enrolls_a_secretary_but_an_admin_cannot():
    """Elle parle au nom de l'église entière : sa nomination reste un acte d'état-major."""
    owner, admin, tenant = uuid4(), uuid4(), uuid4()
    store = _FakeStore()
    ms = _FakeMemberships([_membership(admin, tenant, RoleCode.ADMIN)])
    result = await _command(_FakeAccounts(), ms, store, owners={(owner, tenant)}).execute(
        actor_account_id=owner,
        tenant_id=tenant,
        role=RoleCode.SECRETARY,
        phone_number="+2250700000060",
        first_name="Marie",
    )
    assert result.role == "secretary"
    assert result.group_id is None  # non scopée : sa voix porte église-entière

    # L'Admin, lui, ne peut pas la nommer (MANAGE_STAFF = Owner seul).
    with pytest.raises(UnauthorizedScopeError):
        await _command(_FakeAccounts(), ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            role=RoleCode.SECRETARY,
            phone_number="+2250700000061",
        )


async def test_group_leader_requires_group_id():
    admin, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_membership(admin, tenant, RoleCode.ADMIN)])
    with pytest.raises(RoleRequiresGroupError):
        await _command(_FakeAccounts(), ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            role=RoleCode.GROUP_LEADER,
            phone_number="+2250700000053",
        )


async def test_group_leader_cap_of_six_is_enforced():
    admin, tenant, group = uuid4(), uuid4(), uuid4()
    existing = [
        _membership(uuid4(), tenant, RoleCode.GROUP_LEADER, group_id=group) for _ in range(6)
    ]
    ms = _FakeMemberships([_membership(admin, tenant, RoleCode.ADMIN), *existing])
    with pytest.raises(GroupLeaderCapExceededError):
        await _command(_FakeAccounts(), ms, _FakeStore()).execute(
            actor_account_id=admin,
            tenant_id=tenant,
            role=RoleCode.GROUP_LEADER,
            phone_number="+2250700000054",
            group_id=group,
        )


async def test_network_supervisor_role_is_not_enrollable():
    owner, tenant = uuid4(), uuid4()
    cmd = _command(_FakeAccounts(), _FakeMemberships([]), _FakeStore(), owners={(owner, tenant)})
    with pytest.raises(RoleNotEnrollableError):
        await cmd.execute(
            actor_account_id=owner,
            tenant_id=tenant,
            role=RoleCode.NETWORK_SUPERVISOR,
            phone_number="+2250700000055",
        )


async def test_existing_global_account_is_reused_not_recreated():
    """M-2 : un compte global existant sans appartenance ici → on ajoute l'appartenance."""
    owner, tenant = uuid4(), uuid4()
    existing = Account(id=uuid4(), phone_number="+2250700000056", status=AccountStatus.ACTIVE)
    store = _FakeStore()
    cmd = _command(
        _FakeAccounts({"+2250700000056": existing}),
        _FakeMemberships([]),
        store,
        owners={(owner, tenant)},
    )
    result = await cmd.execute(
        actor_account_id=owner,
        tenant_id=tenant,
        role=RoleCode.ADMIN,
        phone_number="+2250700000056",
    )
    assert result.account_id == existing.id
    assert store.calls == []  # aucun compte recréé
    assert store.added[0]["membership"].account_id == existing.id


async def test_existing_active_membership_is_rejected():
    """M-2 : déjà membre de CE tenant → refus (pas de doublon d'appartenance)."""
    owner, tenant = uuid4(), uuid4()
    existing = Account(id=uuid4(), phone_number="+2250700000057", status=AccountStatus.ACTIVE)
    ms = _FakeMemberships([_membership(existing.id, tenant, RoleCode.ADMIN)])
    cmd = _command(
        _FakeAccounts({"+2250700000057": existing}),
        ms,
        _FakeStore(),
        owners={(owner, tenant)},
    )
    with pytest.raises(DuplicateActiveMembershipError):
        await cmd.execute(
            actor_account_id=owner,
            tenant_id=tenant,
            role=RoleCode.ADMIN,
            phone_number="+2250700000057",
        )
