"""M9-0 — l'ossature missionnaire : liens (perso/groupe), carte publique, réactions, Seeker."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.iam.application.ports import MemberEnrollmentStore, OwnershipChecker
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import AccountStatus, MembershipStatus, RoleCode
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository
from app.contexts.mission.application.commands.accompany import (
    AccompanySeeker,
    CloseSeeker,
)
from app.contexts.mission.application.commands.create_link import (
    CreateGroupLink,
    CreateMyLink,
)
from app.contexts.mission.application.commands.engage_card import (
    AcceptInvitation,
    ReactToCard,
)
from app.contexts.mission.application.commands.integrate import IntegrateSeeker
from app.contexts.mission.application.ports import (
    InvitationCodeGenerator,
    InviterDirectory,
)
from app.contexts.mission.application.queries.get_card import GetCard
from app.contexts.mission.application.queries.list_my_seekers import ListMySeekers
from app.contexts.mission.domain.aggregates import MissionLink, Seeker
from app.contexts.mission.domain.enums import SeekerReaction, SeekerStatus
from app.contexts.mission.domain.errors import (
    InvalidMissionLinkError,
    MissionLinkInactiveError,
    MissionLinkNotFoundError,
    NotAChurchMemberError,
    SeekerAlreadyResolvedError,
    SeekerContactRequiredError,
    SeekerNotFoundError,
    SeekerPhoneRequiredError,
)
from app.contexts.mission.domain.repositories import (
    MissionLinkRepository,
    MissionReactionRepository,
    SeekerRepository,
)
from app.contexts.notifications.application.notifier import Notifier

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


# --- fakes ---


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
        return [m for m in self._m if m.account_id == account_id]

    async def count_active_group_leaders(self, tenant_id, group_id):
        return 0


class _FakeGroups(GroupRepository):
    def __init__(self, groups=()):
        self._by_id = {g.id: g for g in groups}

    async def add(self, g):
        self._by_id[g.id] = g

    async def get(self, gid):
        return self._by_id.get(gid)

    async def list_children_by_lineage(self, mother_id):
        return []

    async def list_active_structural_children(self, parent_id):
        return []

    async def list_active_by_tenant(self, tenant_id):
        return [g for g in self._by_id.values() if g.tenant_id == tenant_id]

    async def save(self, g):
        self._by_id[g.id] = g


class _FakeLinks(MissionLinkRepository):
    def __init__(self, items=()):
        self._l = list(items)

    async def add(self, link):
        self._l.append(link)

    async def get(self, link_id):
        return next((x for x in self._l if x.id == link_id), None)

    async def get_by_code(self, code):
        return next((x for x in self._l if x.code == code), None)

    async def save(self, link):
        pass  # muté en mémoire

    async def get_active_personal(self, account_id, tenant_id):
        return next(
            (
                x
                for x in self._l
                if x.inviter_account_id == account_id
                and x.tenant_id == tenant_id
                and x.revoked_at is None
            ),
            None,
        )

    async def get_active_group(self, group_id):
        return next(
            (x for x in self._l if x.inviter_group_id == group_id and x.revoked_at is None), None
        )


class _FakeSeekers(SeekerRepository):
    def __init__(self, items=()):
        self._s = list(items)

    async def add(self, seeker):
        self._s.append(seeker)

    async def get(self, seeker_id):
        return next((s for s in self._s if s.id == seeker_id), None)

    async def save(self, seeker):
        pass  # muté en mémoire (même instance)

    async def list_by_inviter_account(self, account_id, tenant_id):
        return [
            s for s in self._s if s.inviter_account_id == account_id and s.tenant_id == tenant_id
        ]

    async def list_by_inviter_group(self, group_id):
        return [s for s in self._s if s.inviter_group_id == group_id]

    async def count_by_link(self, link_id):
        return sum(1 for s in self._s if s.link_id == link_id)


class _FakeReactions(MissionReactionRepository):
    def __init__(self):
        self._r = []

    async def add(self, reaction):
        self._r.append(reaction)

    async def counts_by_kind(self, link_id):
        out = {}
        for r in self._r:
            if r.link_id == link_id:
                out[r.kind] = out.get(r.kind, 0) + 1
        return out


class _FakeDirectory(InviterDirectory):
    async def person_label(self, account_id):
        return "Awa"

    async def group_label(self, group_id):
        return "Cellule Jeunesse"

    async def church_label(self, tenant_id):
        return "Église Peniel"


class _FakeCodes(InvitationCodeGenerator):
    def __init__(self, code="INV-1"):
        self._code = code

    def generate(self):
        return self._code


def _cell(tenant) -> Group:
    return Group.create_root(
        id=uuid4(), tenant_id=tenant, name="Cellule", type=GroupType.CELLULE, now=_NOW,
        created_by_account_id=uuid4(),
    )


def _member(account, tenant, *roles) -> Membership:
    ras = [
        RoleAssignment(
            id=uuid4(), role=r, group_id=g, assigned_at=_NOW, assigned_by_account_id=uuid4()
        )
        for (r, g) in roles
    ]
    return Membership(
        id=uuid4(), account_id=account, tenant_id=tenant,
        status=MembershipStatus.CONFIRMED_MEMBER, last_transition_at=_NOW, role_assignments=ras,
    )


def _access(memberships, *, owners=()):
    return GroupAccessPolicy(_FakeOwnership(owners), memberships)


def _link(tenant, *, account=None, group=None, code="INV-1", revoked=False, expired=False):
    return MissionLink.create(
        id=uuid4(), tenant_id=tenant, inviter_account_id=account, inviter_group_id=group,
        message="Viens", code=code, now=_NOW,
        expires_at=_NOW - timedelta(days=1) if expired else _NOW + timedelta(days=90),
    ) if not revoked else _revoked(tenant, account, group, code)


def _revoked(tenant, account, group, code):
    link = MissionLink.create(
        id=uuid4(), tenant_id=tenant, inviter_account_id=account, inviter_group_id=group,
        message="Viens", code=code, now=_NOW, expires_at=_NOW + timedelta(days=90),
    )
    link.revoke(now=_NOW)
    return link


# --- Le domaine : la carte est cohérente ---


def test_link_requires_exactly_one_owner():
    with pytest.raises(InvalidMissionLinkError):  # ni personne ni groupe
        MissionLink.create(
            id=uuid4(), tenant_id=uuid4(), inviter_account_id=None, inviter_group_id=None,
            message="x", code="c", now=_NOW, expires_at=_NOW + timedelta(days=1),
        )
    with pytest.raises(InvalidMissionLinkError):  # les deux
        MissionLink.create(
            id=uuid4(), tenant_id=uuid4(), inviter_account_id=uuid4(), inviter_group_id=uuid4(),
            message="x", code="c", now=_NOW, expires_at=_NOW + timedelta(days=1),
        )


def test_link_requires_message_and_complete_geo():
    with pytest.raises(InvalidMissionLinkError):
        MissionLink.create(
            id=uuid4(), tenant_id=uuid4(), inviter_account_id=uuid4(), inviter_group_id=None,
            message="   ", code="c", now=_NOW, expires_at=_NOW + timedelta(days=1),
        )
    with pytest.raises(InvalidMissionLinkError):  # latitude sans longitude
        MissionLink.create(
            id=uuid4(), tenant_id=uuid4(), inviter_account_id=uuid4(), inviter_group_id=None,
            message="x", code="c", now=_NOW, expires_at=_NOW + timedelta(days=1), latitude=5.3,
        )


def test_card_can_be_image_only():
    # Ni verset ni texte écrit : une image seule (photo uploadée ou carte-verset) suffit.
    link = MissionLink.create(
        id=uuid4(), tenant_id=uuid4(), inviter_account_id=uuid4(), inviter_group_id=None,
        message="", code="c", now=_NOW, expires_at=_NOW + timedelta(days=1),
        media_urls=["https://cdn/card.svg"],
    )
    assert link.message == "" and link.media_urls == ["https://cdn/card.svg"]


def test_card_needs_message_or_media():
    with pytest.raises(InvalidMissionLinkError):  # ni message ni image
        MissionLink.create(
            id=uuid4(), tenant_id=uuid4(), inviter_account_id=uuid4(), inviter_group_id=None,
            message="  ", code="c", now=_NOW, expires_at=_NOW + timedelta(days=1),
        )


# --- Créer un lien ---


async def test_member_creates_a_personal_link_idempotently():
    member, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    links = _FakeLinks()
    cmd = CreateMyLink(links, ms, _FakeCodes(), clock=lambda: _NOW)

    dto1 = await cmd.execute(actor_account_id=member, tenant_id=tenant, message="Viens")
    dto2 = await cmd.execute(actor_account_id=member, tenant_id=tenant, message="Autre")
    assert dto1.inviter_kind == "person"
    assert dto1.id == dto2.id  # idempotent : un seul lien personnel
    assert len(links._l) == 1


async def test_member_creates_an_image_only_card():
    # Carte image seule (verset généré ou photo uploadée), sans message écrit.
    member, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    cmd = CreateMyLink(_FakeLinks(), ms, _FakeCodes(), clock=lambda: _NOW)
    dto = await cmd.execute(
        actor_account_id=member, tenant_id=tenant, media_urls=["https://cdn/card.svg"]
    )
    assert dto.message == "" and dto.media_urls == ["https://cdn/card.svg"]


async def test_non_member_cannot_create_a_link():
    stranger, tenant = uuid4(), uuid4()
    cmd = CreateMyLink(_FakeLinks(), _FakeMemberships(), _FakeCodes(), clock=lambda: _NOW)
    with pytest.raises(NotAChurchMemberError):
        await cmd.execute(actor_account_id=stranger, tenant_id=tenant, message="Viens")


async def test_leader_creates_a_group_campaign_link():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    ms = _FakeMemberships([_member(leader, tenant, (RoleCode.GROUP_LEADER, cell.id))])
    cmd = CreateGroupLink(
        _FakeLinks(), _FakeGroups([cell]), _access(ms), _FakeCodes(), clock=lambda: _NOW
    )
    dto = await cmd.execute(
        actor_account_id=leader, tenant_id=tenant, group_id=cell.id, message="Campagne"
    )
    assert dto.inviter_kind == "group"


async def test_non_manager_cannot_create_a_group_link():
    outsider, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    cmd = CreateGroupLink(
        _FakeLinks(), _FakeGroups([cell]), _access(_FakeMemberships()), _FakeCodes(),
        clock=lambda: _NOW,
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=outsider, tenant_id=tenant, group_id=cell.id, message="x"
        )


# --- La carte publique ---


async def test_public_card_shows_the_face_and_church():
    tenant = uuid4()
    link = _link(tenant, account=uuid4())
    card = await GetCard(_FakeLinks([link]), _FakeDirectory(), clock=lambda: _NOW).execute(
        code=link.code
    )
    assert card.inviter_label == "Awa"  # le visage
    assert card.church_label == "Église Peniel"
    assert card.active is True


async def test_public_card_unknown_code_is_404():
    with pytest.raises(MissionLinkNotFoundError):
        await GetCard(_FakeLinks(), _FakeDirectory(), clock=lambda: _NOW).execute(code="nope")


# --- Réagir (anonyme) ---


async def test_react_is_anonymous_and_counted():
    tenant = uuid4()
    link = _link(tenant, account=uuid4())
    links, reacts = _FakeLinks([link]), _FakeReactions()
    react = ReactToCard(links, reacts, clock=lambda: _NOW)
    await react.execute(code=link.code, kind=SeekerReaction.TOUCHED)
    await react.execute(code=link.code, kind=SeekerReaction.AMEN)
    counts = await reacts.counts_by_kind(link.id)
    assert counts[SeekerReaction.TOUCHED] == 1 and counts[SeekerReaction.AMEN] == 1


async def test_react_on_a_revoked_link_is_rejected():
    tenant = uuid4()
    link = _link(tenant, account=uuid4(), revoked=True)
    with pytest.raises(MissionLinkInactiveError):
        await ReactToCard(_FakeLinks([link]), _FakeReactions(), clock=lambda: _NOW).execute(
            code=link.code, kind=SeekerReaction.TOUCHED
        )


# --- Accepter → devenir Seeker ---


async def test_accept_creates_a_seeker_attributed_to_the_inviter():
    tenant, inviter = uuid4(), uuid4()
    link = _link(tenant, account=inviter)
    links, seekers = _FakeLinks([link]), _FakeSeekers()
    seeker_id = await AcceptInvitation(links, seekers, clock=lambda: _NOW).execute(
        code=link.code, name="Koffi", phone="+2250700"
    )
    assert seeker_id is not None
    mine = await seekers.list_by_inviter_account(inviter, tenant)
    assert len(mine) == 1 and mine[0].name == "Koffi"
    assert mine[0].status.value == "accepted"


class _FakeNotifier(Notifier):
    def __init__(self):
        self.calls = []

    async def notify(self, account_ids, notification):
        self.calls.append((list(account_ids), notification))


async def test_accepting_notifies_the_inviter():
    tenant, inviter = uuid4(), uuid4()
    link = _link(tenant, account=inviter)
    notifier = _FakeNotifier()
    accept = AcceptInvitation(_FakeLinks([link]), _FakeSeekers(), notifier, clock=lambda: _NOW)
    await accept.execute(code=link.code, name="Koffi")
    assert notifier.calls and notifier.calls[0][0] == [inviter]


async def test_accept_requires_a_name():
    tenant = uuid4()
    link = _link(tenant, account=uuid4())
    with pytest.raises(SeekerContactRequiredError):
        await AcceptInvitation(_FakeLinks([link]), _FakeSeekers(), clock=lambda: _NOW).execute(
            code=link.code, name="   "
        )


# --- Mon fruit (privé) ---


async def test_my_seekers_lists_my_fruit_with_reaction_signal():
    member, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    links, seekers, reacts = _FakeLinks(), _FakeSeekers(), _FakeReactions()
    # le membre a un lien, deux acceptations, une réaction
    dto = await CreateMyLink(links, ms, _FakeCodes(), clock=lambda: _NOW).execute(
        actor_account_id=member, tenant_id=tenant, message="Viens"
    )
    accept = AcceptInvitation(links, seekers, clock=lambda: _NOW)
    await accept.execute(code=dto.code, name="A")
    await accept.execute(code=dto.code, name="B")
    await ReactToCard(links, reacts, clock=lambda: _NOW).execute(
        code=dto.code, kind=SeekerReaction.TOUCHED
    )

    fruit = await ListMySeekers(links, seekers, reacts).execute(
        actor_account_id=member, tenant_id=tenant
    )
    assert fruit.total == 2
    assert fruit.reaction_counts == {"touched": 1}  # le signal, remis à l'inviteur


# --- Accompagner (M9-3) : le relais humain ---


def _seeker(
    tenant, *, account=None, group=None, status=SeekerStatus.ACCEPTED, phone=None
) -> Seeker:
    return Seeker(
        id=uuid4(), tenant_id=tenant, link_id=uuid4(),
        inviter_account_id=account, inviter_group_id=group,
        name="Koffi", phone=phone, status=status, created_at=_NOW,
    )


def test_seeker_accompany_records_who_and_when():
    member = uuid4()
    s = _seeker(uuid4(), account=uuid4())
    s.accompany(by_account_id=member, now=_NOW)
    assert s.status is SeekerStatus.ACCOMPANIED
    assert s.accompanied_by_account_id == member and s.accompanied_at == _NOW


def test_seeker_accompany_on_a_resolved_parcours_raises():
    s = _seeker(uuid4(), account=uuid4(), status=SeekerStatus.INTEGRATED)
    with pytest.raises(SeekerAlreadyResolvedError):
        s.accompany(by_account_id=uuid4(), now=_NOW)


def test_seeker_close_is_without_judgment_and_idempotent():
    s = _seeker(uuid4(), account=uuid4())
    s.close(now=_NOW)
    assert s.status is SeekerStatus.CLOSED and s.closed_at == _NOW
    s.close(now=_NOW)  # idempotent
    assert s.status is SeekerStatus.CLOSED


async def test_inviter_accompanies_their_own_seeker():
    inviter, tenant = uuid4(), uuid4()
    s = _seeker(tenant, account=inviter)
    cmd = AccompanySeeker(
        _FakeSeekers([s]), _FakeGroups(), _access(_FakeMemberships()), clock=lambda: _NOW
    )
    dto = await cmd.execute(actor_account_id=inviter, seeker_id=s.id)
    assert dto.status == "accompanied" and dto.accompanied_by == inviter


async def test_a_stranger_cannot_accompany_a_personal_seeker():
    inviter, tenant = uuid4(), uuid4()
    s = _seeker(tenant, account=inviter)
    cmd = AccompanySeeker(
        _FakeSeekers([s]), _FakeGroups(), _access(_FakeMemberships()), clock=lambda: _NOW
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(actor_account_id=uuid4(), seeker_id=s.id)


async def test_group_manager_accompanies_a_group_seeker():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    s = _seeker(tenant, group=cell.id)
    ms = _FakeMemberships([_member(leader, tenant, (RoleCode.GROUP_LEADER, cell.id))])
    cmd = AccompanySeeker(_FakeSeekers([s]), _FakeGroups([cell]), _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(actor_account_id=leader, seeker_id=s.id)
    assert dto.status == "accompanied"


async def test_accompany_unknown_seeker_is_404():
    cmd = AccompanySeeker(
        _FakeSeekers(), _FakeGroups(), _access(_FakeMemberships()), clock=lambda: _NOW
    )
    with pytest.raises(SeekerNotFoundError):
        await cmd.execute(actor_account_id=uuid4(), seeker_id=uuid4())


async def test_inviter_closes_a_seeker_without_judgment():
    inviter, tenant = uuid4(), uuid4()
    s = _seeker(tenant, account=inviter)
    cmd = CloseSeeker(
        _FakeSeekers([s]), _FakeGroups(), _access(_FakeMemberships()), clock=lambda: _NOW
    )
    dto = await cmd.execute(actor_account_id=inviter, seeker_id=s.id)
    assert dto.status == "closed"


# --- Intégrer (M9-4) : le chercheur devient membre (réutilise le tunnel visiteur→membre) ---


class _FakeAccounts(AccountRepository):
    def __init__(self, accounts=()):
        self._a = list(accounts)

    async def get_by_id(self, account_id):
        return next((a for a in self._a if a.id == account_id), None)

    async def get_by_phone(self, phone_number):
        return next((a for a in self._a if a.phone_number == phone_number), None)


class _FakeEnrollStore(MemberEnrollmentStore):
    """Écrit dans le même `_FakeMemberships` (l'appartenance créée devient visible)."""

    def __init__(self, memberships):
        self._ms = memberships
        self.enrolled = []
        self.added = []

    async def enroll(self, *, account, membership, creation_source, actor_account_id):
        self._ms._m.append(membership)
        self.enrolled.append((account, membership, creation_source))

    async def add_membership(self, *, membership, actor_account_id):
        self._ms._m.append(membership)
        self.added.append(membership)


class _FakeGroupMemberships(GroupMembershipRepository):
    def __init__(self, members=()):
        self._gm = list(members)

    async def add(self, m):
        self._gm.append(m)

    async def save(self, m):
        pass

    async def get_active(self, account_id, group_id):
        return next(
            (m for m in self._gm if m.account_id == account_id and m.group_id == group_id
             and m.is_active),
            None,
        )

    async def list_active_by_group(self, group_id):
        return [m for m in self._gm if m.group_id == group_id and m.is_active]


def _account(phone, *, first_name=None) -> Account:
    return Account(
        id=uuid4(), phone_number=phone, status=AccountStatus.ACTIVE, first_name=first_name
    )


def _integrate(seekers, ms, groups, gms, store):
    return IntegrateSeeker(
        seekers, _FakeAccounts(), ms, store, groups, gms, _access(ms), clock=lambda: _NOW
    )


def test_seeker_integrate_records_the_account_it_became():
    account = uuid4()
    s = _seeker(uuid4(), account=uuid4())
    s.integrate(account_id=account, now=_NOW)
    assert s.status is SeekerStatus.INTEGRATED
    assert s.integrated_account_id == account and s.integrated_at == _NOW


def test_seeker_integrate_on_a_closed_parcours_raises():
    s = _seeker(uuid4(), account=uuid4(), status=SeekerStatus.CLOSED)
    with pytest.raises(SeekerAlreadyResolvedError):
        s.integrate(account_id=uuid4(), now=_NOW)


async def test_integrate_group_seeker_creates_invited_member_and_joins_cell():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    s = _seeker(tenant, group=cell.id, phone="+2250700000099")
    ms = _FakeMemberships([_member(leader, tenant, (RoleCode.GROUP_LEADER, cell.id))])
    seekers, gms, store = _FakeSeekers([s]), _FakeGroupMemberships(), _FakeEnrollStore(ms)
    cmd = _integrate(seekers, ms, _FakeGroups([cell]), gms, store)

    result = await cmd.execute(actor_account_id=leader, seeker_id=s.id)
    assert result.membership_status == "invited" and result.reused_account is False
    assert result.group_id == cell.id and result.seeker_status == "integrated"
    assert len(store.enrolled) == 1  # compte + appartenance créés
    assert len(gms._gm) == 1  # inscrit au roster de la cellule
    assert s.status is SeekerStatus.INTEGRATED


async def test_integrate_personal_seeker_needs_church_wide_authority():
    owner, tenant = uuid4(), uuid4()
    s = _seeker(tenant, account=uuid4(), phone="+2250700000098")
    ms = _FakeMemberships()
    seekers, gms, store = _FakeSeekers([s]), _FakeGroupMemberships(), _FakeEnrollStore(ms)
    # Owner → autorité église-entière ; pas de cellule cible (pas de roster).
    cmd = IntegrateSeeker(
        seekers, _FakeAccounts(), ms, store, _FakeGroups(), gms,
        _access(ms, owners={(owner, tenant)}), clock=lambda: _NOW,
    )
    result = await cmd.execute(actor_account_id=owner, seeker_id=s.id)
    assert result.group_id is None and result.reused_account is False
    assert len(gms._gm) == 0  # chercheur personnel → pas de roster


async def test_integrate_reuses_a_global_account_by_phone():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    existing = _account("+2250700000097")
    s = _seeker(tenant, group=cell.id, phone="+2250700000097")
    ms = _FakeMemberships([_member(leader, tenant, (RoleCode.GROUP_LEADER, cell.id))])
    seekers, gms, store = _FakeSeekers([s]), _FakeGroupMemberships(), _FakeEnrollStore(ms)
    cmd = IntegrateSeeker(
        seekers, _FakeAccounts([existing]), ms, store, _FakeGroups([cell]), gms,
        _access(ms), clock=lambda: _NOW,
    )
    result = await cmd.execute(actor_account_id=leader, seeker_id=s.id)
    assert result.reused_account is True and result.account_id == existing.id
    assert len(store.enrolled) == 0 and len(store.added) == 1  # appartenance ajoutée au compte


async def test_integrate_requires_a_phone():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    s = _seeker(tenant, group=cell.id, phone=None)  # ni le Seeker ni la requête n'ont de tél
    ms = _FakeMemberships([_member(leader, tenant, (RoleCode.GROUP_LEADER, cell.id))])
    cmd = _integrate(_FakeSeekers([s]), ms, _FakeGroups([cell]), _FakeGroupMemberships(),
                     _FakeEnrollStore(ms))
    with pytest.raises(SeekerPhoneRequiredError):
        await cmd.execute(actor_account_id=leader, seeker_id=s.id)


async def test_integrate_without_enrollment_authority_is_rejected():
    outsider, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    s = _seeker(tenant, group=cell.id, phone="+2250700000096")
    ms = _FakeMemberships()  # aucun rôle → pas d'autorité d'enrôlement
    cmd = _integrate(_FakeSeekers([s]), ms, _FakeGroups([cell]), _FakeGroupMemberships(),
                     _FakeEnrollStore(ms))
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(actor_account_id=outsider, seeker_id=s.id)


async def test_integrate_unknown_seeker_is_404():
    ms = _FakeMemberships()
    cmd = _integrate(_FakeSeekers(), ms, _FakeGroups(), _FakeGroupMemberships(),
                     _FakeEnrollStore(ms))
    with pytest.raises(SeekerNotFoundError):
        await cmd.execute(actor_account_id=uuid4(), seeker_id=uuid4())
