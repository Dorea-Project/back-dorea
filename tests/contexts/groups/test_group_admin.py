"""G-5 — administration : modifier, fermer (cascade), révoquer le leadership.

Principe « structurer depuis au-dessus » : les actes structurels (fermer, révoquer un
responsable plein) exigent l'autorité du **parent** ; les actes DANS le nœud (renommer,
révoquer un formateur) restent au responsable du nœud.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.groups.application.commands.close_group import CloseGroup
from app.contexts.groups.application.commands.modify_group import ModifyGroup
from app.contexts.groups.application.commands.revoke_group_leadership import RevokeGroupLeadership
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.ports import ChurchRoleStore
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupStatus, GroupType
from app.contexts.groups.domain.errors import (
    GroupClosedError,
    GroupHasActiveChildrenError,
    InvalidGroupStatusError,
    LeadershipNotFoundError,
    UnauthorizedGroupActionError,
)
from app.contexts.groups.domain.leadership import GroupLeadershipGrade
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
            if g.parent_group_id == parent_id and g.status is not GroupStatus.CLOSED
        ]

    async def save(self, group):
        self._by_id[group.id] = group
        self.saved.append(group)


class _FakeGroupMemberships(GroupMembershipRepository):
    def __init__(self, members=None):
        self._m = list(members or [])

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
    def __init__(self, touched=1):
        self._touched = touched
        self.revoked = []
        self.revoked_all = []

    async def add_group_role(self, **kwargs):
        return uuid4()

    async def revoke_group_role(self, **kwargs):
        self.revoked.append(kwargs)
        return self._touched

    async def revoke_all_group_roles(self, **kwargs):
        self.revoked_all.append(kwargs)


def _church(account_id, tenant_id, *roles: RoleAssignment) -> Membership:
    return Membership(
        id=uuid4(),
        account_id=account_id,
        tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER,
        last_transition_at=_NOW,
        role_assignments=list(roles),
    )


def _role(role: RoleCode, *, group_id) -> RoleAssignment:
    return RoleAssignment(
        id=uuid4(),
        role=role,
        group_id=group_id,
        assigned_at=_NOW,
        assigned_by_account_id=uuid4(),
    )


def _root(tenant_id, *, name="Jeunesse", type=GroupType.MINISTERE) -> Group:
    return Group.create_root(
        id=uuid4(), tenant_id=tenant_id, name=name, type=type, now=_NOW,
        created_by_account_id=uuid4(),
    )


def _child(parent, *, name="Famille", type=GroupType.CELLULE) -> Group:
    return Group.create_child(
        id=uuid4(), parent=parent, name=name, type=type, now=_NOW,
        created_by_account_id=uuid4(),
    )


def _policy(church, *, owners=()) -> GroupAccessPolicy:
    return GroupAccessPolicy(_FakeOwnership(owners), church)


# --- ModifyGroup ---


async def test_modify_renames_and_sets_dormant():
    owner, tenant = uuid4(), uuid4()
    group = _root(tenant)
    groups = _FakeGroups([group])
    cmd = ModifyGroup(groups, _policy(_FakeChurch(), owners={(owner, tenant)}))

    dto = await cmd.execute(
        actor_account_id=owner,
        tenant_id=tenant,
        group_id=group.id,
        name="Jeunesse Vie",
        status=GroupStatus.DORMANT,
    )
    assert dto.name == "Jeunesse Vie"
    assert dto.status == "dormant"


async def test_modify_closed_group_is_rejected():
    owner, tenant = uuid4(), uuid4()
    group = _root(tenant)
    group.status = GroupStatus.CLOSED
    cmd = ModifyGroup(_FakeGroups([group]), _policy(_FakeChurch(), owners={(owner, tenant)}))
    with pytest.raises(GroupClosedError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, group_id=group.id, name="X"
        )


async def test_modify_to_forbidden_status_is_rejected():
    owner, tenant = uuid4(), uuid4()
    group = _root(tenant)
    cmd = ModifyGroup(_FakeGroups([group]), _policy(_FakeChurch(), owners={(owner, tenant)}))
    with pytest.raises(InvalidGroupStatusError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, group_id=group.id,
            status=GroupStatus.CLOSED,
        )


# --- CloseGroup ---


async def test_close_cascades_memberships_and_roles():
    owner, tenant, m1 = uuid4(), uuid4(), uuid4()
    group = _root(tenant)
    gm = GroupMembership.join(
        id=uuid4(), group_id=group.id, account_id=m1, tenant_id=tenant, now=_NOW,
        joined_by_account_id=uuid4(),
    )
    gmships = _FakeGroupMemberships([gm])
    store = _FakeRoleStore()
    cmd = CloseGroup(
        _FakeGroups([group]), gmships, store, _policy(_FakeChurch(), owners={(owner, tenant)}),
        clock=lambda: _NOW,
    )
    await cmd.execute(actor_account_id=owner, tenant_id=tenant, group_id=group.id)

    assert gm.status is GroupMembershipStatus.LEFT  # appartenance fermée
    assert store.revoked_all[0]["group_id"] == group.id  # rôles du nœud révoqués


async def test_close_blocked_by_active_children():
    owner, tenant = uuid4(), uuid4()
    parent = _root(tenant)
    child = _child(parent)  # sous-groupe actif rattaché au parent
    cmd = CloseGroup(
        _FakeGroups([parent, child]), _FakeGroupMemberships(), _FakeRoleStore(),
        _policy(_FakeChurch(), owners={(owner, tenant)}), clock=lambda: _NOW,
    )
    with pytest.raises(GroupHasActiveChildrenError):
        await cmd.execute(actor_account_id=owner, tenant_id=tenant, group_id=parent.id)


async def test_close_requires_parent_authority():
    """Le responsable d'un nœud ne peut PAS fermer son propre groupe (auto-dissolution)."""
    tenant, jeunesse_leader = uuid4(), uuid4()
    jeunesse = _root(tenant)
    famille = _child(jeunesse)
    # Responsable scopé à la FAMILLE elle-même.
    famille_leader = uuid4()
    church = _FakeChurch(
        [
            _church(jeunesse_leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=jeunesse.id)),
            _church(famille_leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=famille.id)),
        ]
    )
    groups = _FakeGroups([jeunesse, famille])

    # Le responsable de la Jeunesse (parent) PEUT fermer la famille.
    ok = CloseGroup(groups, _FakeGroupMemberships(), _FakeRoleStore(), _policy(church),
                    clock=lambda: _NOW)
    await ok.execute(actor_account_id=jeunesse_leader, tenant_id=tenant, group_id=famille.id)

    # Le responsable de la famille NE PEUT PAS la fermer lui-même.
    famille2 = _child(jeunesse, name="Famille 2")
    groups2 = _FakeGroups([jeunesse, famille2])
    church2 = _FakeChurch(
        [_church(famille_leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=famille2.id))]
    )
    ko = CloseGroup(groups2, _FakeGroupMemberships(), _FakeRoleStore(), _policy(church2),
                    clock=lambda: _NOW)
    with pytest.raises(UnauthorizedGroupActionError):
        await ko.execute(actor_account_id=famille_leader, tenant_id=tenant, group_id=famille2.id)


# --- RevokeGroupLeadership ---


async def test_revoke_group_leader_needs_parent_authority():
    tenant, admin, target = uuid4(), uuid4(), uuid4()
    jeunesse = _root(tenant)
    famille = _child(jeunesse)
    church = _FakeChurch(
        [
            _church(admin, tenant, _role(RoleCode.GROUP_LEADER, group_id=jeunesse.id)),
            _church(target, tenant, _role(RoleCode.GROUP_LEADER, group_id=famille.id)),
        ]
    )
    store = _FakeRoleStore()
    cmd = RevokeGroupLeadership(
        _FakeGroups([jeunesse, famille]), church, store, _policy(church), clock=lambda: _NOW
    )
    await cmd.execute(
        actor_account_id=admin, tenant_id=tenant, group_id=famille.id, account_id=target,
        grade=GroupLeadershipGrade.LEADER,
    )
    assert store.revoked[0]["role"] == "group_leader"
    assert store.revoked[0]["group_id"] == famille.id


async def test_revoke_trainee_is_a_node_act():
    tenant, leader, trainee = uuid4(), uuid4(), uuid4()
    famille = _root(tenant, type=GroupType.CELLULE)
    church = _FakeChurch(
        [
            _church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=famille.id)),
            _church(trainee, tenant, _role(RoleCode.LEADER_IN_TRAINING, group_id=famille.id)),
        ]
    )
    store = _FakeRoleStore()
    cmd = RevokeGroupLeadership(
        _FakeGroups([famille]), church, store, _policy(church), clock=lambda: _NOW
    )
    # Le responsable du nœud peut révoquer le Timothée (mentorat).
    await cmd.execute(
        actor_account_id=leader, tenant_id=tenant, group_id=famille.id, account_id=trainee,
        grade=GroupLeadershipGrade.IN_TRAINING,
    )
    assert store.revoked[0]["role"] == "leader_in_training"


async def test_revoke_absent_leadership_is_not_found():
    owner, tenant, target = uuid4(), uuid4(), uuid4()
    group = _root(tenant)
    church = _FakeChurch([_church(target, tenant)])  # aucun rôle
    store = _FakeRoleStore(touched=0)  # rien à révoquer
    cmd = RevokeGroupLeadership(
        _FakeGroups([group]), church, store, _policy(church, owners={(owner, tenant)}),
        clock=lambda: _NOW,
    )
    with pytest.raises(LeadershipNotFoundError):
        await cmd.execute(
            actor_account_id=owner, tenant_id=tenant, group_id=group.id, account_id=target,
            grade=GroupLeadershipGrade.LEADER,
        )
