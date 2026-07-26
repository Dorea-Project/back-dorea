"""G-3 — multiplication cellulaire : fille (lignée, génération), déplacement, promotion ; report."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.groups.application.commands.multiply_cell import MULTIPLY_THRESHOLD, MultiplyCell
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.ports import ChurchRoleStore
from app.contexts.groups.application.queries.get_cell_report import GetCellReport
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import (
    MemberNotInCellError,
    NotACellError,
    RequiresChurchMembershipError,
    UnauthorizedGroupActionError,
)
from app.contexts.groups.domain.membership import GroupMembership
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
    def __init__(self, memberships=()):
        self._m = list(memberships)

    async def get_active(self, account_id, tenant_id):
        return next(
            (m for m in self._m if m.account_id == account_id and m.tenant_id == tenant_id), None
        )

    async def list_active_by_account(self, account_id):
        return [m for m in self._m if m.account_id == account_id]

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
        for i, e in enumerate(self._m):
            if e.id == membership.id:
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


class _FakeRoleStore(ChurchRoleStore):
    def __init__(self):
        self.calls = []

    async def add_group_role(self, **kwargs):
        self.calls.append(kwargs)
        return uuid4()

    async def revoke_group_role(self, **kwargs):
        return 1

    async def revoke_all_group_roles(self, **kwargs):
        return None


def _church(account_id, tenant_id) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER,
        last_transition_at=_NOW,
        role_assignments=[],
    )


def _leader_church(account_id, tenant_id, group_id) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER,
        last_transition_at=_NOW,
        role_assignments=[
            RoleAssignment(
                id=uuid4(),
                role=RoleCode.GROUP_LEADER,
                group_id=group_id,
                assigned_at=_NOW,
                assigned_by_account_id=uuid4(),
            )
        ],
    )


def _cell(tenant_id, *, name="Famille A") -> Group:
    return Group.create_root(
        id=uuid4(),
        tenant_id=tenant_id,
        name=name,
        type=GroupType.CELLULE,
        now=_NOW,
        created_by_account_id=uuid4(),
    )


def _join(gmships, group_id, account_id, tenant_id):
    gmships._m.append(
        GroupMembership.join(
            id=uuid4(),
            group_id=group_id,
            account_id=account_id,
            tenant_id=tenant_id,
            now=_NOW,
            joined_by_account_id=uuid4(),
        )
    )


def _cmd(groups, gmships, church, store, *, owners=()) -> MultiplyCell:
    access = GroupAccessPolicy(_FakeOwnership(owners), church)
    return MultiplyCell(groups, gmships, church, store, access, clock=lambda: _NOW)


async def test_multiply_creates_daughter_moves_members_promotes_leader():
    owner, tenant = uuid4(), uuid4()
    timothee, m1, m2 = uuid4(), uuid4(), uuid4()
    mother = _cell(tenant)
    gmships = _FakeGroupMemberships()
    for acc in (timothee, m1, m2):
        _join(gmships, mother.id, acc, tenant)
    church = _FakeChurch([_church(timothee, tenant)])
    groups = _FakeGroups([mother])
    store = _FakeRoleStore()
    cmd = _cmd(groups, gmships, church, store, owners={(owner, tenant)})

    dto = await cmd.execute(
        actor_account_id=owner,
        tenant_id=tenant,
        mother_group_id=mother.id,
        daughter_name="Famille A (fille)",
        new_leader_account_id=timothee,
        member_account_ids=[m1, m2],
    )

    # Fille : cellule, génération +1, lignée vers la mère, sœur (même parent → path racine).
    daughter = await groups.get(dto.daughter_group_id)
    assert daughter.type is GroupType.CELLULE
    assert daughter.generation == 2
    assert daughter.multiplied_from_id == mother.id
    assert daughter.parent_group_id is None
    assert daughter.path == f"/{daughter.id}/"
    assert dto.moved_members == 2

    # Membres déplacés : plus actifs dans la mère, actifs dans la fille.
    assert await gmships.get_active(m1, mother.id) is None
    assert await gmships.get_active(m1, daughter.id) is not None
    # Le Timothée rejoint la fille et est promu group_leader de la fille.
    assert await gmships.get_active(timothee, daughter.id) is not None
    assert store.calls[0]["role"] == "group_leader"
    assert store.calls[0]["group_id"] == daughter.id


async def test_daughter_is_sibling_of_a_nested_mother():
    owner, tenant, timothee = uuid4(), uuid4(), uuid4()
    jeunesse = Group.create_root(
        id=uuid4(), tenant_id=tenant, name="Jeunesse", type=GroupType.MINISTERE,
        now=_NOW, created_by_account_id=uuid4(),
    )
    mother = Group.create_child(
        id=uuid4(), parent=jeunesse, name="Famille", type=GroupType.CELLULE,
        now=_NOW, created_by_account_id=uuid4(),
    )
    gmships = _FakeGroupMemberships()
    church = _FakeChurch([_church(timothee, tenant)])
    groups = _FakeGroups([jeunesse, mother])
    cmd = _cmd(groups, gmships, church, _FakeRoleStore(), owners={(owner, tenant)})

    dto = await cmd.execute(
        actor_account_id=owner, tenant_id=tenant, mother_group_id=mother.id,
        daughter_name="Famille (fille)", new_leader_account_id=timothee, member_account_ids=[],
    )
    daughter = await groups.get(dto.daughter_group_id)
    # Sœur : même parent structurel (Jeunesse), chemin sous Jeunesse.
    assert daughter.parent_group_id == jeunesse.id
    assert daughter.path == f"/{jeunesse.id}/{daughter.id}/"


async def test_scoped_leader_can_multiply_his_cell():
    leader, tenant, timothee = uuid4(), uuid4(), uuid4()
    mother = _cell(tenant)
    church = _FakeChurch(
        [_leader_church(leader, tenant, mother.id), _church(timothee, tenant)]
    )
    cmd = _cmd(_FakeGroups([mother]), _FakeGroupMemberships(), church, _FakeRoleStore())
    dto = await cmd.execute(
        actor_account_id=leader, tenant_id=tenant, mother_group_id=mother.id,
        daughter_name="fille", new_leader_account_id=timothee, member_account_ids=[],
    )
    assert dto.generation == 2


async def test_only_a_cell_multiplies():
    owner, tenant, timothee = uuid4(), uuid4(), uuid4()
    ministere = Group.create_root(
        id=uuid4(), tenant_id=tenant, name="Jeunesse", type=GroupType.MINISTERE,
        now=_NOW, created_by_account_id=uuid4(),
    )
    church = _FakeChurch([_church(timothee, tenant)])
    cmd = _cmd(_FakeGroups([ministere]), _FakeGroupMemberships(), church, _FakeRoleStore(),
               owners={(owner, tenant)})
    with pytest.raises(NotACellError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, mother_group_id=ministere.id,
            daughter_name="x", new_leader_account_id=timothee, member_account_ids=[],
        )


async def test_mover_not_in_mother_is_rejected():
    owner, tenant, timothee, outsider = uuid4(), uuid4(), uuid4(), uuid4()
    mother = _cell(tenant)
    church = _FakeChurch([_church(timothee, tenant)])
    cmd = _cmd(_FakeGroups([mother]), _FakeGroupMemberships(), church, _FakeRoleStore(),
               owners={(owner, tenant)})
    with pytest.raises(MemberNotInCellError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, mother_group_id=mother.id,
            daughter_name="x", new_leader_account_id=timothee, member_account_ids=[outsider],
        )


async def test_new_leader_must_be_church_member():
    owner, tenant, stranger = uuid4(), uuid4(), uuid4()
    mother = _cell(tenant)
    cmd = _cmd(_FakeGroups([mother]), _FakeGroupMemberships(), _FakeChurch(), _FakeRoleStore(),
               owners={(owner, tenant)})
    with pytest.raises(RequiresChurchMembershipError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, mother_group_id=mother.id,
            daughter_name="x", new_leader_account_id=stranger, member_account_ids=[],
        )


async def test_unauthorized_actor_cannot_multiply():
    stranger, tenant, timothee = uuid4(), uuid4(), uuid4()
    mother = _cell(tenant)
    church = _FakeChurch([_church(timothee, tenant)])  # stranger a aucun rôle, pas owner
    cmd = _cmd(_FakeGroups([mother]), _FakeGroupMemberships(), church, _FakeRoleStore())
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=stranger, tenant_id=tenant, mother_group_id=mother.id,
            daughter_name="x", new_leader_account_id=timothee, member_account_ids=[],
        )


async def test_cell_report_signals_readiness_and_lineage():
    owner, tenant = uuid4(), uuid4()
    mother = _cell(tenant)
    gmships = _FakeGroupMemberships()
    for _ in range(MULTIPLY_THRESHOLD):  # effectif au seuil → prêt à multiplier
        _join(gmships, mother.id, uuid4(), tenant)
    # Une fille déjà née (génération 2).
    daughter = mother.multiply(
        daughter_id=uuid4(), name="fille", now=_NOW, created_by_account_id=owner
    )
    groups = _FakeGroups([mother, daughter])
    access = GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch())
    report = GetCellReport(groups, gmships, access)

    dto = await report.execute(actor_account_id=owner, tenant_id=tenant, group_id=mother.id)
    assert dto.active_member_count == MULTIPLY_THRESHOLD
    assert dto.ready_to_multiply is True
    assert dto.generation == 1
    assert {d.id for d in dto.daughters} == {daughter.id}
    assert dto.daughters[0].generation == 2


async def test_cell_report_not_ready_below_threshold():
    owner, tenant = uuid4(), uuid4()
    mother = _cell(tenant)
    gmships = _FakeGroupMemberships()
    _join(gmships, mother.id, uuid4(), tenant)  # 1 membre → pas prêt
    report = GetCellReport(
        _FakeGroups([mother]), gmships,
        GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch()),
    )
    dto = await report.execute(actor_account_id=owner, tenant_id=tenant, group_id=mother.id)
    assert dto.ready_to_multiply is False
