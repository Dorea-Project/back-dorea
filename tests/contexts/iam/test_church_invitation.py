"""M-5 — Rejoindre une église par lien/code : création (autorité), join (le code autorise)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.commands.church_invitation import (
    CreateChurchInvitation,
    JoinChurchByCode,
    RevokeChurchInvitation,
)
from app.contexts.iam.application.ports import (
    InvitationCodeGenerator,
    MemberEnrollmentStore,
    OwnershipChecker,
)
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.church_invitation import ChurchInvitation
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.errors import (
    ChurchInvitationInactiveError,
    ChurchInvitationNotFoundError,
    UnauthorizedScopeError,
)
from app.contexts.iam.domain.repositories import (
    ChurchInvitationRepository,
    MembershipRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeOwnership(OwnershipChecker):
    def __init__(self, owners=()):
        self._owners = set(owners)

    async def is_active_owner(self, account_id, tenant_id):
        return (account_id, tenant_id) in self._owners


class _FakeMemberships(MembershipRepository):
    def __init__(self, items=()):
        self._m = list(items)

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


class _FakeInvitations(ChurchInvitationRepository):
    def __init__(self, items=()):
        self._i = list(items)

    async def add(self, inv):
        self._i.append(inv)

    async def get(self, iid):
        return next((x for x in self._i if x.id == iid), None)

    async def get_by_code(self, code):
        return next((x for x in self._i if x.code == code), None)

    async def save(self, inv):
        pass  # agrégat muté en mémoire

    async def list_active_by_tenant(self, tid):
        return [x for x in self._i if x.tenant_id == tid and x.revoked_at is None]


class _FakeEnrollment(MemberEnrollmentStore):
    def __init__(self):
        self.added = []

    async def enroll(self, *, account, membership, creation_source, actor_account_id):
        self.added.append(membership)

    async def add_membership(self, *, membership, actor_account_id):
        self.added.append(membership)


class _FakeCodes(InvitationCodeGenerator):
    def __init__(self, code="JOIN-PENIEL"):
        self._code = code

    def generate(self):
        return self._code


def _member(account, tenant, *roles, status=MembershipStatus.CONFIRMED_MEMBER) -> Membership:
    ras = [
        RoleAssignment(
            id=uuid4(), role=r, group_id=g, assigned_at=_NOW, assigned_by_account_id=uuid4()
        )
        for (r, g) in roles
    ]
    return Membership(
        id=uuid4(), account_id=account, tenant_id=tenant, status=status,
        last_transition_at=_NOW, role_assignments=ras,
    )


def _access(memberships, *, owners=()):
    return AccessControl(_FakeOwnership(owners), memberships)


def _invite(tenant, code="JOIN-PENIEL", *, revoked=False, expired=False) -> ChurchInvitation:
    return ChurchInvitation(
        id=uuid4(), tenant_id=tenant, code=code, created_by_account_id=uuid4(),
        created_at=_NOW,
        expires_at=_NOW - timedelta(days=1) if expired else _NOW + timedelta(days=30),
        revoked_at=_NOW if revoked else None,
    )


# --- Créer un lien : autorité église-entière ---


async def test_welcome_team_creates_a_church_link():
    accueil, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(accueil, tenant, (RoleCode.WELCOME_TEAM, None))])
    invs = _FakeInvitations()
    dto = await CreateChurchInvitation(
        invs, _FakeCodes(), _access(ms), clock=lambda: _NOW
    ).execute(actor_account_id=accueil, tenant_id=tenant)
    assert dto.code == "JOIN-PENIEL" and dto.revoked is False
    assert len(invs._i) == 1


async def test_a_scoped_leader_cannot_mint_a_church_wide_link():
    leader, tenant, cell = uuid4(), uuid4(), uuid4()
    # group_leader a ENROLL_MEMBER, mais **scopé** à sa cellule → pas au nom de l'église.
    ms = _FakeMemberships([_member(leader, tenant, (RoleCode.GROUP_LEADER, cell))])
    with pytest.raises(UnauthorizedScopeError):
        await CreateChurchInvitation(
            _FakeInvitations(), _FakeCodes(), _access(ms), clock=lambda: _NOW
        ).execute(actor_account_id=leader, tenant_id=tenant)


async def test_owner_can_always_create():
    owner, tenant = uuid4(), uuid4()
    dto = await CreateChurchInvitation(
        _FakeInvitations(), _FakeCodes(), _access(_FakeMemberships(), owners={(owner, tenant)}),
        clock=lambda: _NOW,
    ).execute(actor_account_id=owner, tenant_id=tenant)
    assert dto.code == "JOIN-PENIEL"


# --- Rejoindre : le code EST l'autorisation ---


async def test_join_enrolls_an_invited_member():
    newcomer, tenant = uuid4(), uuid4()
    invs = _FakeInvitations([_invite(tenant)])
    store = _FakeEnrollment()
    result = await JoinChurchByCode(
        invs, _FakeMemberships(), store, clock=lambda: _NOW
    ).execute(actor_account_id=newcomer, code="JOIN-PENIEL")

    assert result.status == "invited" and result.already_member is False
    assert len(store.added) == 1
    assert store.added[0].status is MembershipStatus.INVITED


async def test_join_when_already_member_does_not_duplicate():
    member, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])  # déjà membre
    store = _FakeEnrollment()
    result = await JoinChurchByCode(
        _FakeInvitations([_invite(tenant)]), ms, store, clock=lambda: _NOW
    ).execute(actor_account_id=member, code="JOIN-PENIEL")

    assert result.already_member is True
    assert store.added == []  # aucune appartenance créée


async def test_join_with_unknown_code_is_404():
    with pytest.raises(ChurchInvitationNotFoundError):
        await JoinChurchByCode(
            _FakeInvitations(), _FakeMemberships(), _FakeEnrollment(), clock=lambda: _NOW
        ).execute(actor_account_id=uuid4(), code="NOPE")


async def test_join_with_expired_or_revoked_link_is_rejected():
    tenant = uuid4()
    for inv in (_invite(tenant, expired=True), _invite(tenant, revoked=True)):
        with pytest.raises(ChurchInvitationInactiveError):
            await JoinChurchByCode(
                _FakeInvitations([inv]), _FakeMemberships(), _FakeEnrollment(),
                clock=lambda: _NOW,
            ).execute(actor_account_id=uuid4(), code=inv.code)


async def test_revoke_then_join_is_inactive():
    admin, newcomer, tenant = uuid4(), uuid4(), uuid4()
    inv = _invite(tenant)
    invs = _FakeInvitations([inv])
    ms = _FakeMemberships([_member(admin, tenant, (RoleCode.ADMIN, None))])
    dto = await RevokeChurchInvitation(invs, _access(ms), clock=lambda: _NOW).execute(
        actor_account_id=admin, invitation_id=inv.id
    )
    assert dto.revoked is True
    with pytest.raises(ChurchInvitationInactiveError):
        await JoinChurchByCode(
            invs, _FakeMemberships(), _FakeEnrollment(), clock=lambda: _NOW
        ).execute(actor_account_id=newcomer, code=inv.code)
