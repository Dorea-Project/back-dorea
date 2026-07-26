"""G-1 — appartenance au groupe : ajout managé, prérequis église, dédup, retrait, roster."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.groups.application.commands.add_group_member import AddGroupMember
from app.contexts.groups.application.commands.remove_group_member import RemoveGroupMember
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.queries.list_group_members import ListGroupMembers
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import (
    DuplicateGroupMembershipError,
    GroupMembershipNotFoundError,
    GroupNotFoundError,
    RequiresChurchMembershipError,
    UnauthorizedGroupActionError,
)
from app.contexts.groups.domain.membership import GroupMembership, GroupMembershipStatus
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeOwnership(OwnershipChecker):
    def __init__(self, owners=()):
        self._owners = set(owners)

    async def is_active_owner(self, account_id, tenant_id):
        return (account_id, tenant_id) in self._owners


class _FakeChurch(MembershipRepository):
    """Sert double emploi : rôles de l'acteur (access) ET prérequis église (command)."""

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


class _FakeGroups(GroupRepository):
    def __init__(self, groups=()):
        self._by_id = {g.id: g for g in groups}

    async def add(self, group):
        self._by_id[group.id] = group

    async def get(self, group_id):
        return self._by_id.get(group_id)

    async def list_active_by_tenant(self, tenant_id):
        return [
            g
            for g in self._by_id.values()
            if g.tenant_id == tenant_id and g.status.value != "closed"
        ]

    async def list_children_by_lineage(self, mother_id):
        return [g for g in self._by_id.values() if g.multiplied_from_id == mother_id]

    async def list_active_structural_children(self, parent_id):
        return [
            g
            for g in self._by_id.values()
            if g.parent_group_id == parent_id and g.status.value != "closed"
        ]

    async def save(self, group):
        self._by_id[group.id] = group


class _FakeGroupMemberships(GroupMembershipRepository):
    def __init__(self):
        self._m: list[GroupMembership] = []

    async def add(self, membership):
        self._m.append(membership)

    async def save(self, membership):
        for i, existing in enumerate(self._m):
            if existing.id == membership.id:
                self._m[i] = membership
                return

    async def get_active(self, account_id, group_id):
        return next(
            (
                m
                for m in self._m
                if m.account_id == account_id and m.group_id == group_id and m.is_active
            ),
            None,
        )

    async def list_active_by_group(self, group_id):
        return [m for m in self._m if m.group_id == group_id and m.is_active]


def _church_membership(account_id, tenant_id, *roles: RoleAssignment) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER,
        last_transition_at=_NOW,
        role_assignments=list(roles),
    )


def _role(role: RoleCode, *, group_id=None) -> RoleAssignment:
    return RoleAssignment(
        id=uuid4(),
        role=role,
        group_id=group_id,
        assigned_at=_NOW,
        assigned_by_account_id=uuid4(),
    )


def _group(tenant_id) -> Group:
    return Group.create_root(
        id=uuid4(),
        tenant_id=tenant_id,
        name="Jeunesse",
        type=GroupType.MINISTERE,
        now=_NOW,
        created_by_account_id=uuid4(),
    )


def _policy(church, *, owners=()) -> GroupAccessPolicy:
    return GroupAccessPolicy(_FakeOwnership(owners), church)


async def test_owner_adds_a_member():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church_membership(koffi, tenant)])  # Koffi est membre de l'église
    gms = _FakeGroupMemberships()
    policy = _policy(church, owners={(owner, tenant)})
    cmd = AddGroupMember(_FakeGroups([group]), gms, church, policy, clock=lambda: _NOW)

    dto = await cmd.execute(
        actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=koffi
    )

    assert dto.account_id == koffi
    assert dto.status == "active"
    assert await gms.get_active(koffi, group.id) is not None


async def test_scoped_leader_adds_a_member_to_his_group():
    leader, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch(
        [
            _church_membership(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=group.id)),
            _church_membership(koffi, tenant),
        ]
    )
    cmd = AddGroupMember(
        _FakeGroups([group]), _FakeGroupMemberships(), church, _policy(church), clock=lambda: _NOW
    )

    dto = await cmd.execute(
        actor_account_id=leader, tenant_id=tenant, group_id=group.id, account_id=koffi
    )
    assert dto.status == "active"


async def test_add_requires_church_membership():
    owner, tenant, stranger = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch()  # personne n'est membre de l'église
    cmd = AddGroupMember(
        _FakeGroups([group]), _FakeGroupMemberships(), church,
        _policy(church, owners={(owner, tenant)}), clock=lambda: _NOW
    )
    with pytest.raises(RequiresChurchMembershipError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=stranger
        )


async def test_add_is_idempotent_guard_against_duplicate():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church_membership(koffi, tenant)])
    gms = _FakeGroupMemberships()
    policy = _policy(church, owners={(owner, tenant)})
    cmd = AddGroupMember(_FakeGroups([group]), gms, church, policy, clock=lambda: _NOW)
    await cmd.execute(actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=koffi)
    with pytest.raises(DuplicateGroupMembershipError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=koffi
        )


async def test_leader_cannot_add_to_group_outside_scope():
    leader, tenant, koffi = uuid4(), uuid4(), uuid4()
    jeunesse = _group(tenant)
    louange = _group(tenant)  # autre sous-arbre
    church = _FakeChurch(
        [
            _church_membership(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=jeunesse.id)),
            _church_membership(koffi, tenant),
        ]
    )
    cmd = AddGroupMember(
        _FakeGroups([jeunesse, louange]), _FakeGroupMemberships(), church, _policy(church),
        clock=lambda: _NOW,
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=leader, tenant_id=tenant, group_id=louange.id, account_id=koffi
        )


async def test_add_to_group_of_another_tenant_is_not_found():
    owner, tenant, other = uuid4(), uuid4(), uuid4()
    foreign = _group(other)
    church = _FakeChurch()
    cmd = AddGroupMember(
        _FakeGroups([foreign]), _FakeGroupMemberships(), church,
        _policy(church, owners={(owner, tenant)}), clock=lambda: _NOW
    )
    with pytest.raises(GroupNotFoundError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, group_id=foreign.id, account_id=uuid4()
        )


async def test_remove_member_marks_left():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church_membership(koffi, tenant)])
    gms = _FakeGroupMemberships()
    policy = _policy(church, owners={(owner, tenant)})
    await AddGroupMember(_FakeGroups([group]), gms, church, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=koffi
    )

    await RemoveGroupMember(_FakeGroups([group]), gms, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=koffi
    )

    assert await gms.get_active(koffi, group.id) is None  # plus actif
    assert gms._m[0].status is GroupMembershipStatus.LEFT


async def test_remove_non_member_is_not_found():
    owner, tenant = uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch()
    cmd = RemoveGroupMember(
        _FakeGroups([group]), _FakeGroupMemberships(), _policy(church, owners={(owner, tenant)}),
        clock=lambda: _NOW,
    )
    with pytest.raises(GroupMembershipNotFoundError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=uuid4()
        )


async def test_roster_lists_active_members_only():
    owner, tenant = uuid4(), uuid4()
    a, b = uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church_membership(a, tenant), _church_membership(b, tenant)])
    gms = _FakeGroupMemberships()
    policy = _policy(church, owners={(owner, tenant)})
    add = AddGroupMember(_FakeGroups([group]), gms, church, policy, clock=lambda: _NOW)
    await add.execute(actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=a)
    await add.execute(actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=b)
    await RemoveGroupMember(_FakeGroups([group]), gms, policy, clock=lambda: _NOW).execute(
        actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=b
    )

    roster = await ListGroupMembers(_FakeGroups([group]), gms, policy).execute(
        actor_account_id=owner, tenant_id=tenant, group_id=group.id
    )
    assert {m.account_id for m in roster} == {a}  # b est parti


async def test_roster_requires_management_rights():
    outsider, tenant = uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church_membership(outsider, tenant, _role(RoleCode.WELCOME_TEAM))])
    query = ListGroupMembers(_FakeGroups([group]), _FakeGroupMemberships(), _policy(church))
    with pytest.raises(UnauthorizedGroupActionError):
        await query.execute(actor_account_id=outsider, tenant_id=tenant, group_id=group.id)
