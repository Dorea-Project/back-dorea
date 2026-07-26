"""G-0 — CreateGroup : autorisation par sous-arbre (§4) et subsidiarité.

Le scénario clé : le responsable de la « Jeunesse » crée des cellules « famille »
**dans son sous-arbre**, sans validation — mais ne peut ni créer de racine ni agir hors
de sa portée.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.groups.application.commands.create_group import CreateGroup
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import (
    CrossTenantParentError,
    ParentGroupNotFoundError,
    UnauthorizedGroupActionError,
)
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeOwnership(OwnershipChecker):
    def __init__(self, owners=()):
        self._owners = set(owners)  # {(account_id, tenant_id)}

    async def is_active_owner(self, account_id, tenant_id):
        return (account_id, tenant_id) in self._owners


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


class _FakeGroups(GroupRepository):
    def __init__(self, groups=()):
        self._by_id = {g.id: g for g in groups}
        self.added = []

    async def add(self, group):
        self._by_id[group.id] = group
        self.added.append(group)

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


def _membership(account_id, tenant_id, *roles: RoleAssignment) -> Membership:
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


def _root(tenant_id, *, name="Jeunesse", type=GroupType.MINISTERE) -> Group:
    return Group.create_root(
        id=uuid4(),
        tenant_id=tenant_id,
        name=name,
        type=type,
        now=_NOW,
        created_by_account_id=uuid4(),
    )


def _command(groups, memberships, *, owners=()) -> CreateGroup:
    access = GroupAccessPolicy(_FakeOwnership(owners), memberships)
    return CreateGroup(groups, access, clock=lambda: _NOW)


async def test_owner_creates_a_root_group():
    owner, tenant = uuid4(), uuid4()
    groups = _FakeGroups()
    cmd = _command(groups, _FakeMemberships(), owners={(owner, tenant)})

    dto = await cmd.execute(
        actor_account_id=owner, tenant_id=tenant, name="Jeunesse", type=GroupType.MINISTERE
    )

    assert dto.parent_group_id is None
    assert dto.type == "ministere"
    assert groups.added[0].path == f"/{dto.id}/"  # chemin matérialisé racine


async def test_admin_creates_root_and_child():
    admin, tenant = uuid4(), uuid4()
    # Admin = MANAGE_GROUP non scopé (portée église entière).
    ms = _FakeMemberships([_membership(admin, tenant, _role(RoleCode.ADMIN))])
    groups = _FakeGroups()
    cmd = _command(groups, ms)

    root = await cmd.execute(
        actor_account_id=admin, tenant_id=tenant, name="Jeunesse", type=GroupType.MINISTERE
    )
    child = await cmd.execute(
        actor_account_id=admin,
        tenant_id=tenant,
        name="Famille A",
        type=GroupType.CELLULE,
        parent_group_id=root.id,
    )

    assert child.parent_group_id == root.id
    # Le chemin de l'enfant prolonge celui du parent (sous-arbre).
    assert groups.added[1].path == f"/{root.id}/{child.id}/"


async def test_youth_leader_creates_famille_in_his_subtree():
    """LE scénario : le responsable Jeunesse crée une cellule *famille* sous la Jeunesse."""
    leader, tenant = uuid4(), uuid4()
    jeunesse = _root(tenant)
    ms = _FakeMemberships(
        [_membership(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=jeunesse.id))]
    )
    cmd = _command(_FakeGroups([jeunesse]), ms)

    dto = await cmd.execute(
        actor_account_id=leader,
        tenant_id=tenant,
        name="Famille de Koffi",
        type=GroupType.CELLULE,
        parent_group_id=jeunesse.id,
    )

    assert dto.parent_group_id == jeunesse.id
    assert dto.type == "cellule"


async def test_leader_scope_reaches_grandchildren():
    """Portée = sous-arbre : le responsable Jeunesse agit aussi sous une famille (petit-enfant)."""
    leader, tenant = uuid4(), uuid4()
    jeunesse = _root(tenant)
    famille = Group.create_child(
        id=uuid4(),
        parent=jeunesse,
        name="Famille A",
        type=GroupType.CELLULE,
        now=_NOW,
        created_by_account_id=uuid4(),
    )
    ms = _FakeMemberships(
        [_membership(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=jeunesse.id))]
    )
    cmd = _command(_FakeGroups([jeunesse, famille]), ms)

    dto = await cmd.execute(
        actor_account_id=leader,
        tenant_id=tenant,
        name="Sous-cellule",
        type=GroupType.CELLULE,
        parent_group_id=famille.id,
    )
    assert dto.parent_group_id == famille.id


async def test_leader_cannot_act_outside_his_subtree():
    leader, tenant = uuid4(), uuid4()
    jeunesse = _root(tenant, name="Jeunesse")
    louange = _root(tenant, name="Louange")  # autre sous-arbre
    ms = _FakeMemberships(
        [_membership(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=jeunesse.id))]
    )
    cmd = _command(_FakeGroups([jeunesse, louange]), ms)

    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=leader,
            tenant_id=tenant,
            name="Intrusion",
            type=GroupType.CELLULE,
            parent_group_id=louange.id,
        )


async def test_leader_cannot_create_a_root_group():
    leader, tenant = uuid4(), uuid4()
    jeunesse = _root(tenant)
    ms = _FakeMemberships(
        [_membership(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=jeunesse.id))]
    )
    cmd = _command(_FakeGroups([jeunesse]), ms)

    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=leader,
            tenant_id=tenant,
            name="Ministère pirate",
            type=GroupType.MINISTERE,
        )


async def test_member_without_manage_group_is_rejected():
    account, tenant = uuid4(), uuid4()
    # Accueil : pas de MANAGE_GROUP.
    ms = _FakeMemberships([_membership(account, tenant, _role(RoleCode.WELCOME_TEAM))])
    cmd = _command(_FakeGroups(), ms)

    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=account, tenant_id=tenant, name="X", type=GroupType.MINISTERE
        )


async def test_stranger_without_membership_is_rejected():
    cmd = _command(_FakeGroups(), _FakeMemberships())
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=uuid4(), tenant_id=uuid4(), name="X", type=GroupType.MINISTERE
        )


async def test_cross_tenant_parent_is_rejected():
    owner, tenant, other_tenant = uuid4(), uuid4(), uuid4()
    foreign_parent = _root(other_tenant)
    cmd = _command(_FakeGroups([foreign_parent]), _FakeMemberships(), owners={(owner, tenant)})

    with pytest.raises(CrossTenantParentError):
        await cmd.execute(
            actor_account_id=owner,
            tenant_id=tenant,
            name="Famille",
            type=GroupType.CELLULE,
            parent_group_id=foreign_parent.id,
        )


async def test_unknown_parent_is_rejected():
    owner, tenant = uuid4(), uuid4()
    cmd = _command(_FakeGroups(), _FakeMemberships(), owners={(owner, tenant)})
    with pytest.raises(ParentGroupNotFoundError):
        await cmd.execute(
            actor_account_id=owner,
            tenant_id=tenant,
            name="Famille",
            type=GroupType.CELLULE,
            parent_group_id=uuid4(),
        )
