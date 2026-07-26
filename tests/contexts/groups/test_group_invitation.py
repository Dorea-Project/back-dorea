"""G-1b — lien d'invitation & self-join mobile : créer/révoquer, rejoindre par code, quitter."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.groups.application.commands.create_group_invitation import (
    INVITATION_TTL_DAYS,
    CreateGroupInvitation,
)
from app.contexts.groups.application.commands.join_group_by_code import JoinGroupByCode
from app.contexts.groups.application.commands.leave_group import LeaveGroup
from app.contexts.groups.application.commands.revoke_group_invitation import RevokeGroupInvitation
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.ports import ChurchEnrollmentStore, InvitationCodeGenerator
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupStatus, GroupType
from app.contexts.groups.domain.errors import (
    DuplicateGroupMembershipError,
    GroupClosedError,
    GroupMembershipNotFoundError,
    InvitationInactiveError,
    InvitationNotFoundError,
    UnauthorizedGroupActionError,
)
from app.contexts.groups.domain.invitation import GroupInvitation
from app.contexts.groups.domain.membership import GroupMembership, GroupMembershipStatus
from app.contexts.groups.domain.repositories import (
    GroupInvitationRepository,
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_CODE = "test-code-123"


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
        return []

    async def list_active_structural_children(self, parent_id):
        return []

    async def save(self, group):
        self._by_id[group.id] = group


class _FakeInvitations(GroupInvitationRepository):
    def __init__(self, invitations=()):
        self._by_id = {i.id: i for i in invitations}
        self.added = []

    async def add(self, invitation):
        self._by_id[invitation.id] = invitation
        self.added.append(invitation)

    async def get(self, invitation_id):
        return self._by_id.get(invitation_id)

    async def get_by_code(self, code):
        return next((i for i in self._by_id.values() if i.code == code), None)

    async def save(self, invitation):
        self._by_id[invitation.id] = invitation


class _FakeGroupMemberships(GroupMembershipRepository):
    def __init__(self, members=()):
        self._m = list(members)

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


class _FakeCodeGen(InvitationCodeGenerator):
    def generate(self):
        return _CODE


class _FakeEnrollment(ChurchEnrollmentStore):
    def __init__(self):
        self.calls = []

    async def enroll_invited(self, *, account_id, tenant_id, actor_account_id, now):
        self.calls.append({"account_id": account_id, "tenant_id": tenant_id})
        return uuid4()


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
        id=uuid4(), role=role, group_id=group_id, assigned_at=_NOW, assigned_by_account_id=uuid4()
    )


def _group(tenant_id, *, status=GroupStatus.ACTIVE) -> Group:
    g = Group.create_root(
        id=uuid4(), tenant_id=tenant_id, name="Famille", type=GroupType.CELLULE, now=_NOW,
        created_by_account_id=uuid4(),
    )
    g.status = status
    return g


def _invitation(group, *, code=_CODE, expires_at=None, revoked_at=None) -> GroupInvitation:
    return GroupInvitation(
        id=uuid4(),
        group_id=group.id,
        tenant_id=group.tenant_id,
        code=code,
        created_by_account_id=uuid4(),
        created_at=_NOW,
        expires_at=expires_at or (_NOW + timedelta(days=30)),
        revoked_at=revoked_at,
    )


def _join_gm(group, account_id, tenant_id) -> GroupMembership:
    return GroupMembership.join(
        id=uuid4(), group_id=group.id, account_id=account_id, tenant_id=tenant_id, now=_NOW,
        joined_by_account_id=uuid4(),
    )


# --- CreateGroupInvitation ---


async def test_leader_creates_an_invitation():
    owner, tenant = uuid4(), uuid4()
    group = _group(tenant)
    invs = _FakeInvitations()
    cmd = CreateGroupInvitation(
        _FakeGroups([group]), invs, _FakeCodeGen(),
        GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch()), clock=lambda: _NOW,
    )
    dto = await cmd.execute(actor_account_id=owner, tenant_id=tenant, group_id=group.id)
    assert dto.code == _CODE
    assert dto.expires_at == _NOW + timedelta(days=INVITATION_TTL_DAYS)
    assert invs.added[0].group_id == group.id


async def test_create_invitation_on_closed_group_is_rejected():
    owner, tenant = uuid4(), uuid4()
    group = _group(tenant, status=GroupStatus.CLOSED)
    cmd = CreateGroupInvitation(
        _FakeGroups([group]), _FakeInvitations(), _FakeCodeGen(),
        GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch()), clock=lambda: _NOW,
    )
    with pytest.raises(GroupClosedError):
        await cmd.execute(actor_account_id=owner, tenant_id=tenant, group_id=group.id)


async def test_create_invitation_requires_management_rights():
    outsider, tenant = uuid4(), uuid4()
    group = _group(tenant)
    church = _FakeChurch([_church(outsider, tenant, _role(RoleCode.WELCOME_TEAM, group_id=None))])
    cmd = CreateGroupInvitation(
        _FakeGroups([group]), _FakeInvitations(), _FakeCodeGen(),
        GroupAccessPolicy(_FakeOwnership(), church), clock=lambda: _NOW,
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(actor_account_id=outsider, tenant_id=tenant, group_id=group.id)


# --- RevokeGroupInvitation ---


async def test_revoke_invitation():
    owner, tenant = uuid4(), uuid4()
    group = _group(tenant)
    inv = _invitation(group)
    invs = _FakeInvitations([inv])
    cmd = RevokeGroupInvitation(
        _FakeGroups([group]), invs,
        GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch()), clock=lambda: _NOW,
    )
    await cmd.execute(actor_account_id=owner, tenant_id=tenant, invitation_id=inv.id)
    assert (await invs.get(inv.id)).revoked_at == _NOW


async def test_revoke_unknown_invitation_is_not_found():
    owner, tenant = uuid4(), uuid4()
    cmd = RevokeGroupInvitation(
        _FakeGroups(), _FakeInvitations(),
        GroupAccessPolicy(_FakeOwnership({(owner, tenant)}), _FakeChurch()), clock=lambda: _NOW,
    )
    with pytest.raises(InvitationNotFoundError):
        await cmd.execute(actor_account_id=owner, tenant_id=tenant, invitation_id=uuid4())


# --- JoinGroupByCode ---


def _join_cmd(group, invs, gmships, church, enrollment) -> JoinGroupByCode:
    return JoinGroupByCode(
        _FakeGroups([group]), invs, gmships, church, enrollment, clock=lambda: _NOW
    )


async def test_existing_member_joins_without_enrollment():
    tenant, joiner = uuid4(), uuid4()
    group = _group(tenant)
    invs = _FakeInvitations([_invitation(group)])
    gmships = _FakeGroupMemberships()
    church = _FakeChurch([_church(joiner, tenant)])  # déjà membre de l'église
    enrollment = _FakeEnrollment()
    cmd = _join_cmd(group, invs, gmships, church, enrollment)

    dto = await cmd.execute(actor_account_id=joiner, code=_CODE)
    assert dto.enrolled_in_church is False
    assert enrollment.calls == []  # pas d'enrôlement
    assert await gmships.get_active(joiner, group.id) is not None


async def test_new_person_is_onboarded_then_joins():
    tenant, joiner = uuid4(), uuid4()
    group = _group(tenant)
    invs = _FakeInvitations([_invitation(group)])
    gmships = _FakeGroupMemberships()
    church = _FakeChurch()  # PAS membre de l'église
    enrollment = _FakeEnrollment()
    cmd = _join_cmd(group, invs, gmships, church, enrollment)

    dto = await cmd.execute(actor_account_id=joiner, code=_CODE)
    assert dto.enrolled_in_church is True
    assert enrollment.calls[0]["tenant_id"] == tenant  # le lien a onboardé
    assert await gmships.get_active(joiner, group.id) is not None


async def test_join_unknown_code_is_not_found():
    cmd = _join_cmd(
        _group(uuid4()), _FakeInvitations(), _FakeGroupMemberships(), _FakeChurch(),
        _FakeEnrollment(),
    )
    with pytest.raises(InvitationNotFoundError):
        await cmd.execute(actor_account_id=uuid4(), code="nope")


async def test_join_expired_code_is_rejected():
    tenant, joiner = uuid4(), uuid4()
    group = _group(tenant)
    expired = _invitation(group, expires_at=_NOW - timedelta(days=1))
    cmd = _join_cmd(
        group, _FakeInvitations([expired]), _FakeGroupMemberships(),
        _FakeChurch([_church(joiner, tenant)]), _FakeEnrollment(),
    )
    with pytest.raises(InvitationInactiveError):
        await cmd.execute(actor_account_id=joiner, code=_CODE)


async def test_join_revoked_code_is_rejected():
    tenant, joiner = uuid4(), uuid4()
    group = _group(tenant)
    revoked = _invitation(group, revoked_at=_NOW - timedelta(hours=1))
    cmd = _join_cmd(
        group, _FakeInvitations([revoked]), _FakeGroupMemberships(),
        _FakeChurch([_church(joiner, tenant)]), _FakeEnrollment(),
    )
    with pytest.raises(InvitationInactiveError):
        await cmd.execute(actor_account_id=joiner, code=_CODE)


async def test_join_when_already_member_is_duplicate():
    tenant, joiner = uuid4(), uuid4()
    group = _group(tenant)
    gmships = _FakeGroupMemberships([_join_gm(group, joiner, tenant)])
    cmd = _join_cmd(
        group, _FakeInvitations([_invitation(group)]), gmships,
        _FakeChurch([_church(joiner, tenant)]), _FakeEnrollment(),
    )
    with pytest.raises(DuplicateGroupMembershipError):
        await cmd.execute(actor_account_id=joiner, code=_CODE)


async def test_join_closed_group_is_rejected():
    tenant, joiner = uuid4(), uuid4()
    group = _group(tenant, status=GroupStatus.CLOSED)
    cmd = _join_cmd(
        group, _FakeInvitations([_invitation(group)]), _FakeGroupMemberships(),
        _FakeChurch([_church(joiner, tenant)]), _FakeEnrollment(),
    )
    with pytest.raises(GroupClosedError):
        await cmd.execute(actor_account_id=joiner, code=_CODE)


# --- LeaveGroup ---


async def test_member_leaves_group():
    tenant, member = uuid4(), uuid4()
    group = _group(tenant)
    gm = _join_gm(group, member, tenant)
    gmships = _FakeGroupMemberships([gm])
    await LeaveGroup(gmships, clock=lambda: _NOW).execute(
        actor_account_id=member, group_id=group.id
    )
    assert gm.status is GroupMembershipStatus.LEFT


async def test_leave_when_not_member_is_not_found():
    cmd = LeaveGroup(_FakeGroupMemberships(), clock=lambda: _NOW)
    with pytest.raises(GroupMembershipNotFoundError):
        await cmd.execute(actor_account_id=uuid4(), group_id=uuid4())
