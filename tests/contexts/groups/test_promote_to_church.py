"""G-4 — church planting : un groupe s'émancipe en église autonome (Tenant + Owner + filiation)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.groups.application.commands.promote_group_to_church import PromoteGroupToChurch
from app.contexts.groups.application.ports import ChurchPlantStore
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupStatus, GroupType
from app.contexts.groups.domain.errors import (
    GroupAlreadyPromotedError,
    GroupNotFoundError,
    RequiresChurchMembershipError,
)
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.tenant.domain.enums import OwnershipMode

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_PLATFORM = uuid4()


class _FakeChurch(MembershipRepository):
    def __init__(self, members=()):
        self._members = set(members)  # {(account_id, tenant_id)}

    async def get_active(self, account_id, tenant_id):
        if (account_id, tenant_id) in self._members:
            return Membership(
                id=uuid4(),
                account_id=account_id,
                tenant_id=tenant_id,
                status=MembershipStatus.CONFIRMED_MEMBER,
                last_transition_at=_NOW,
                role_assignments=[],
            )
        return None

    async def list_active_by_account(self, account_id):
        return []

    async def count_active_group_leaders(self, tenant_id, group_id):
        return 0


class _FakeGroups(GroupRepository):
    def __init__(self, groups=()):
        self._by_id = {g.id: g for g in groups}
        self.saved = []

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
        self.saved.append(group)


class _FakeGroupMemberships(GroupMembershipRepository):
    def __init__(self, members_by_group=None):
        self._by_group = members_by_group or {}

    async def add(self, membership):
        pass

    async def save(self, membership):
        pass

    async def get_active(self, account_id, group_id):
        return None

    async def list_active_by_group(self, group_id):
        return [
            GroupMembership.join(
                id=uuid4(),
                group_id=group_id,
                account_id=acc,
                tenant_id=uuid4(),
                now=_NOW,
                joined_by_account_id=uuid4(),
            )
            for acc in self._by_group.get(group_id, [])
        ]


class _FakePlantStore(ChurchPlantStore):
    def __init__(self):
        self.call = None

    async def plant(self, *, tenant, ownership, memberships, actor_account_id):
        self.call = {
            "tenant": tenant,
            "ownership": ownership,
            "memberships": memberships,
            "actor_account_id": actor_account_id,
        }


def _cell(tenant_id, *, status=GroupStatus.ACTIVE) -> Group:
    g = Group.create_root(
        id=uuid4(),
        tenant_id=tenant_id,
        name="Amas de cellules",
        type=GroupType.CELLULE,
        now=_NOW,
        created_by_account_id=uuid4(),
    )
    g.status = status
    return g


def _cmd(groups, gmships, church, store) -> PromoteGroupToChurch:
    return PromoteGroupToChurch(
        groups, gmships, church, store, platform_account_id=_PLATFORM, clock=lambda: _NOW
    )


async def test_promotion_creates_church_owner_and_repoints_members():
    source_tenant, owner, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    group = _cell(source_tenant)
    groups = _FakeGroups([group])
    gmships = _FakeGroupMemberships({group.id: [owner, m1, m2]})
    church = _FakeChurch(members={(owner, source_tenant)})
    store = _FakePlantStore()
    cmd = _cmd(groups, gmships, church, store)

    dto = await cmd.execute(
        group_id=group.id, church_name="Église Fille", owner_account_id=owner
    )

    # Nouvelle église fille : filiation vers la mère.
    assert store.call["tenant"].parent_id == source_tenant
    assert dto.parent_tenant_id == source_tenant
    assert dto.tenant_id == store.call["tenant"].id
    # Ownership émancipation pour l'owner désigné.
    assert store.call["ownership"].mode is OwnershipMode.EMANCIPATION
    assert store.call["ownership"].account_id == owner
    # Re-pointage : owner + m1 + m2 (dédup owner), toutes dans la nouvelle église.
    memberships = store.call["memberships"]
    assert {m.account_id for m in memberships} == {owner, m1, m2}
    assert all(m.tenant_id == dto.tenant_id for m in memberships)
    assert dto.member_count == 3
    assert store.call["actor_account_id"] == _PLATFORM
    # La cellule source est clôturée (devenue église).
    assert (await groups.get(group.id)).status is GroupStatus.CLOSED


async def test_owner_must_be_member_of_source_church():
    source_tenant, stranger = uuid4(), uuid4()
    group = _cell(source_tenant)
    cmd = _cmd(
        _FakeGroups([group]),
        _FakeGroupMemberships({group.id: []}),
        _FakeChurch(),
        _FakePlantStore(),
    )
    with pytest.raises(RequiresChurchMembershipError):
        await cmd.execute(group_id=group.id, church_name="X", owner_account_id=stranger)


async def test_already_promoted_group_is_rejected():
    source_tenant, owner = uuid4(), uuid4()
    group = _cell(source_tenant, status=GroupStatus.CLOSED)
    cmd = _cmd(
        _FakeGroups([group]),
        _FakeGroupMemberships({group.id: []}),
        _FakeChurch(members={(owner, source_tenant)}),
        _FakePlantStore(),
    )
    with pytest.raises(GroupAlreadyPromotedError):
        await cmd.execute(group_id=group.id, church_name="X", owner_account_id=owner)


async def test_unknown_group_is_rejected():
    cmd = _cmd(_FakeGroups(), _FakeGroupMemberships(), _FakeChurch(), _FakePlantStore())
    with pytest.raises(GroupNotFoundError):
        await cmd.execute(group_id=uuid4(), church_name="X", owner_account_id=uuid4())
