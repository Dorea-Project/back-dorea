"""G-2 — nomination du leadership : responsable (cap 6) & responsable-en-formation.

Le leadership est posé comme rôle IAM scopé (via `ChurchRoleStore`), autorisé par la
portée sous-arbre. Prérequis : Membership église. Cap 6 pour `group_leader`, pas pour
`in_training`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.groups.application.commands.appoint_group_leadership import (
    AppointGroupLeadership,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.ports import ChurchRoleStore
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import (
    DuplicateLeadershipError,
    GroupNotFoundError,
    LeaderCapExceededError,
    RequiresChurchMembershipError,
    UnauthorizedGroupActionError,
)
from app.contexts.groups.domain.leadership import GroupLeadershipGrade
from app.contexts.groups.domain.repositories import GroupRepository
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
    def __init__(self, memberships=(), leader_count=0):
        self._m = list(memberships)
        self._leader_count = leader_count

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
        return self._leader_count


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


def _church(account_id, tenant_id, *roles: RoleAssignment) -> Membership:
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


def _cmd(groups, church, store, *, owners=()) -> AppointGroupLeadership:
    access = GroupAccessPolicy(_FakeOwnership(owners), church)
    return AppointGroupLeadership(groups, church, store, access, clock=lambda: _NOW)


async def test_owner_appoints_a_group_leader():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church(koffi, tenant)])
    store = _FakeRoleStore()
    cmd = _cmd(_FakeGroups([group]), church, store, owners={(owner, tenant)})

    dto = await cmd.execute(
        actor_account_id=owner,
        tenant_id=tenant,
        group_id=group.id,
        account_id=koffi,
        grade=GroupLeadershipGrade.LEADER,
    )

    assert dto.role == "group_leader"
    assert store.calls[0]["role"] == "group_leader"
    assert store.calls[0]["group_id"] == group.id


async def test_scoped_leader_appoints_a_trainee():
    leader, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch(
        [
            _church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=group.id)),
            _church(koffi, tenant),
        ]
    )
    store = _FakeRoleStore()
    cmd = _cmd(_FakeGroups([group]), church, store)

    dto = await cmd.execute(
        actor_account_id=leader,
        tenant_id=tenant,
        group_id=group.id,
        account_id=koffi,
        grade=GroupLeadershipGrade.IN_TRAINING,
    )
    assert dto.role == "leader_in_training"
    assert dto.grade == "in_training"


async def test_appoint_requires_church_membership():
    owner, tenant, stranger = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    cmd = _cmd(_FakeGroups([group]), _FakeChurch(), _FakeRoleStore(), owners={(owner, tenant)})
    with pytest.raises(RequiresChurchMembershipError):
        await cmd.execute(
            actor_account_id=owner,
            tenant_id=tenant,
            group_id=group.id,
            account_id=stranger,
            grade=GroupLeadershipGrade.LEADER,
        )


async def test_duplicate_grade_is_rejected():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    # Koffi porte déjà group_leader sur ce groupe.
    church = _FakeChurch([_church(koffi, tenant, _role(RoleCode.GROUP_LEADER, group_id=group.id))])
    cmd = _cmd(_FakeGroups([group]), church, _FakeRoleStore(), owners={(owner, tenant)})
    with pytest.raises(DuplicateLeadershipError):
        await cmd.execute(
            actor_account_id=owner,
            tenant_id=tenant,
            group_id=group.id,
            account_id=koffi,
            grade=GroupLeadershipGrade.LEADER,
        )


async def test_leader_cap_of_six_is_enforced():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church(koffi, tenant)], leader_count=6)
    cmd = _cmd(_FakeGroups([group]), church, _FakeRoleStore(), owners={(owner, tenant)})
    with pytest.raises(LeaderCapExceededError):
        await cmd.execute(
            actor_account_id=owner,
            tenant_id=tenant,
            group_id=group.id,
            account_id=koffi,
            grade=GroupLeadershipGrade.LEADER,
        )


async def test_trainee_is_not_capped():
    owner, tenant, koffi = uuid4(), uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church(koffi, tenant)], leader_count=6)  # cap plein pour les leaders
    store = _FakeRoleStore()
    cmd = _cmd(_FakeGroups([group]), church, store, owners={(owner, tenant)})

    dto = await cmd.execute(
        actor_account_id=owner,
        tenant_id=tenant,
        group_id=group.id,
        account_id=koffi,
        grade=GroupLeadershipGrade.IN_TRAINING,
    )
    assert dto.role == "leader_in_training"  # le cap ne s'applique pas


async def test_leader_cannot_appoint_outside_subtree():
    leader, tenant, koffi = uuid4(), uuid4(), uuid4()
    jeunesse = _group(tenant)
    louange = _group(tenant)
    church = _FakeChurch(
        [
            _church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=jeunesse.id)),
            _church(koffi, tenant),
        ]
    )
    cmd = _cmd(_FakeGroups([jeunesse, louange]), church, _FakeRoleStore())
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=leader,
            tenant_id=tenant,
            group_id=louange.id,
            account_id=koffi,
            grade=GroupLeadershipGrade.LEADER,
        )


async def test_group_of_another_tenant_is_not_found():
    owner, tenant, other = uuid4(), uuid4(), uuid4()
    foreign = _group(other)
    cmd = _cmd(_FakeGroups([foreign]), _FakeChurch(), _FakeRoleStore(), owners={(owner, tenant)})
    with pytest.raises(GroupNotFoundError):
        await cmd.execute(
            actor_account_id=owner,
            tenant_id=tenant,
            group_id=foreign.id,
            account_id=uuid4(),
            grade=GroupLeadershipGrade.LEADER,
        )
