"""M8 — Le fil d'actualité : type→couleur/emojis/intention, 3 portées, réactions, engagement."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.announcements.application.commands.archive_announcement import (
    ArchiveAnnouncement,
)
from app.contexts.announcements.application.commands.engage_announcement import (
    EngageAnnouncement,
    WithdrawEngagement,
)
from app.contexts.announcements.application.commands.publish_announcement import (
    PublishAnnouncement,
    PublishPlatformAnnouncement,
)
from app.contexts.announcements.application.commands.react_to_announcement import (
    RemoveReaction,
    SetReaction,
)
from app.contexts.announcements.application.ports import (
    AudiencePort,
    GatheringRsvpPort,
    MemberDirectoryPort,
)
from app.contexts.announcements.application.queries.get_consolation import GetConsolation
from app.contexts.announcements.application.queries.list_church_announcements import (
    ListChurchAnnouncements,
)
from app.contexts.announcements.application.queries.list_my_announcements import (
    ListMyAnnouncements,
)
from app.contexts.announcements.application.queries.list_responders import ListResponders
from app.contexts.announcements.domain.aggregates import Announcement
from app.contexts.announcements.domain.enums import (
    AnnouncementCategory,
    AnnouncementIntent,
    AnnouncementScope,
)
from app.contexts.announcements.domain.errors import (
    AnnouncementClosedError,
    EmojiNotAllowedError,
    InvalidAnnouncementError,
    MobilizationFullError,
    NotAChurchMemberError,
    NotInAudienceError,
    ResponsesNotAcceptedError,
)
from app.contexts.announcements.domain.repositories import (
    AnnouncementEngagementRepository,
    AnnouncementReactionRepository,
    AnnouncementRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.notifications.application.notifier import Notifier

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
Cat, Intent = AnnouncementCategory, AnnouncementIntent


# --- fakes ---


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
        return []

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


class _FakeAnnouncements(AnnouncementRepository):
    def __init__(self, items=()):
        self._a = list(items)

    async def add(self, a):
        self._a.append(a)

    async def get(self, aid):
        return next((x for x in self._a if x.id == aid), None)

    async def save(self, a):
        pass  # agrégat muté en mémoire

    async def list_feed_candidates(self, tenant_id, *, now, before, limit):
        rows = [
            a
            for a in self._a
            if (a.tenant_id is None or a.tenant_id == tenant_id) and a.is_live(now)
        ]
        if before is not None:
            rows = [a for a in rows if a.published_at < before]
        rows.sort(key=lambda a: a.published_at, reverse=True)
        return rows[:limit]

    async def list_by_tenant(self, tid):
        return [x for x in self._a if x.tenant_id == tid]


class _FakeEngagements(AnnouncementEngagementRepository):
    def __init__(self):
        self._r = []

    async def add(self, r):
        self._r.append(r)

    async def get(self, aid, acc):
        return next(
            (x for x in self._r if x.announcement_id == aid and x.account_id == acc), None
        )

    async def remove(self, aid, acc):
        self._r = [
            x for x in self._r if not (x.announcement_id == aid and x.account_id == acc)
        ]

    async def count_for(self, aid):
        return sum(1 for x in self._r if x.announcement_id == aid)

    async def list_for(self, aid):
        return [x for x in self._r if x.announcement_id == aid]

    async def counts_for_many(self, ids):
        s = set(ids)
        out = {}
        for x in self._r:
            if x.announcement_id in s:
                out[x.announcement_id] = out.get(x.announcement_id, 0) + 1
        return out

    async def engaged_among(self, acc, ids):
        s = set(ids)
        return {
            x.announcement_id for x in self._r if x.account_id == acc and x.announcement_id in s
        }


class _FakeReactions(AnnouncementReactionRepository):
    def __init__(self):
        self._r = []

    async def set_for(self, reaction):
        for x in self._r:
            if (
                x.announcement_id == reaction.announcement_id
                and x.account_id == reaction.account_id
            ):
                x.emoji = reaction.emoji  # remplace
                return
        self._r.append(reaction)

    async def remove(self, aid, acc):
        self._r = [
            x for x in self._r if not (x.announcement_id == aid and x.account_id == acc)
        ]

    async def counts_by_emoji(self, aid):
        out = {}
        for x in self._r:
            if x.announcement_id == aid:
                out[x.emoji] = out.get(x.emoji, 0) + 1
        return out

    async def counts_by_emoji_for_many(self, ids):
        s = set(ids)
        out = {}
        for x in self._r:
            if x.announcement_id in s:
                out.setdefault(x.announcement_id, {})
                out[x.announcement_id][x.emoji] = out[x.announcement_id].get(x.emoji, 0) + 1
        return out

    async def reactions_of_account_among(self, acc, ids):
        s = set(ids)
        return {
            x.announcement_id: x.emoji
            for x in self._r
            if x.account_id == acc and x.announcement_id in s
        }


class _FakeAudience(AudiencePort):
    def __init__(self, covering=()):
        self._c = set(covering)

    async def covering_group_ids(self, *, account_id, tenant_id):
        return set(self._c)


class _FakeNotifier(Notifier):
    def __init__(self):
        self.calls = []

    async def notify(self, account_ids, notification):
        self.calls.append((list(account_ids), notification))


class _FakeMembers(MemberDirectoryPort):
    def __init__(self, members=(), subtree=None):
        self._m = list(members)
        self._subtree = subtree or {}  # group_id -> list[account_id]

    async def member_account_ids(self, tenant_id):
        return list(self._m)

    async def member_account_ids_in_subtree(self, tenant_id, group_id):
        return list(self._subtree.get(group_id, []))


class _FakeScheduler:
    def __init__(self):
        self.calls = []

    async def schedule(self, account_ids, notification, *, at):
        self.calls.append((list(account_ids), notification, at))


class _FakeRsvpPort(GatheringRsvpPort):
    def __init__(self):
        self.set = []
        self.cleared = []

    async def set_rsvp(self, *, gathering_id, account_id, now):
        self.set.append((gathering_id, account_id))

    async def clear_rsvp(self, *, gathering_id, account_id):
        self.cleared.append((gathering_id, account_id))


def _cell(tenant, name="Cellule") -> Group:
    return Group.create_root(
        id=uuid4(), tenant_id=tenant, name=name, type=GroupType.CELLULE, now=_NOW,
        created_by_account_id=uuid4(),
    )


def _church(account_id, tenant_id, *roles: RoleAssignment) -> Membership:
    return Membership(
        id=uuid4(), account_id=account_id, tenant_id=tenant_id,
        status=MembershipStatus.CONFIRMED_MEMBER, last_transition_at=_NOW,
        role_assignments=list(roles),
    )


def _role(role, *, group_id) -> RoleAssignment:
    return RoleAssignment(
        id=uuid4(), role=role, group_id=group_id, assigned_at=_NOW, assigned_by_account_id=uuid4()
    )


def _access(church, *, owners=()):
    return GroupAccessPolicy(_FakeOwnership(owners), church)


def _ann(tenant, category, scope, author, *, slots=None, event_at=None, intent=None,
         expires_at=None, published_at=None, media=None, concerns=None, gathering=None):
    a = Announcement.publish(
        id=uuid4(), tenant_id=tenant, category=category, scope_group_id=scope,
        title="T", body=None, author_account_id=author, now=_NOW, intent=intent,
        slots_needed=slots, event_at=event_at, gathering_id=gathering,
        expires_at=expires_at, media_urls=media, concerns_account_id=concerns,
    )
    if published_at is not None:
        a.published_at = published_at
    return a


# --- Le type pilote : couleur, emojis, intention dérivée ---


def test_category_drives_tone_intent_and_emojis():
    death = _ann(uuid4(), Cat.DEATH, None, uuid4())
    assert death.tone.value == "mourning"  # la couleur vient du type
    # Un décès n'est pas un clic de prière : c'est une mobilisation (veillée, accompagnement).
    assert death.intent is Intent.MOBILIZE
    assert "🙏" in death.allowed_emojis and "🎉" not in death.allowed_emojis

    birth = _ann(uuid4(), Cat.BIRTH, None, uuid4())
    assert birth.tone.value == "joy" and birth.intent is Intent.INFORM
    assert "🎉" in birth.allowed_emojis


def test_intent_can_be_overridden_on_a_category():
    # Un mariage informe par défaut… mais peut convoquer avec RSVP.
    wedding = _ann(uuid4(), Cat.WEDDING, None, uuid4(), intent=Intent.CONVENE, event_at=_NOW)
    assert wedding.intent is Intent.CONVENE
    assert wedding.accepts_engagement is True


def test_no_party_emoji_on_a_death():
    death = _ann(uuid4(), Cat.DEATH, None, uuid4())
    with pytest.raises(EmojiNotAllowedError):
        death.ensure_emoji_allowed("🎉")


def test_mobilization_may_be_uncapped_and_convene_needs_a_when():
    open_call = _ann(uuid4(), Cat.CALL, None, uuid4())  # sans places → on ne plafonne pas
    assert open_call.is_capped is False and open_call.slots_needed is None
    with pytest.raises(InvalidAnnouncementError):
        _ann(uuid4(), Cat.CALL, None, uuid4(), slots=0)  # un plafond doit avoir un sens
    with pytest.raises(InvalidAnnouncementError):
        _ann(uuid4(), Cat.SERVICE, None, uuid4())  # convene sans date


def test_platform_announcement_cannot_target_a_group():
    with pytest.raises(InvalidAnnouncementError):
        _ann(None, Cat.INFO, uuid4(), uuid4())


# --- Les trois portées ---


def test_three_scopes_are_derived():
    tenant, cell = uuid4(), uuid4()
    assert _ann(None, Cat.INFO, None, uuid4()).scope is AnnouncementScope.PLATFORM
    assert _ann(tenant, Cat.INFO, None, uuid4()).scope is AnnouncementScope.CHURCH
    assert _ann(tenant, Cat.INFO, cell, uuid4()).scope is AnnouncementScope.GROUP


def test_platform_and_church_reach_everyone_group_only_its_subtree():
    tenant, cell = uuid4(), uuid4()
    assert _ann(None, Cat.INFO, None, uuid4()).reaches(set()) is True  # Dorea → tous
    assert _ann(tenant, Cat.INFO, None, uuid4()).reaches(set()) is True  # église → tous
    scoped = _ann(tenant, Cat.INFO, cell, uuid4())
    assert scoped.reaches({cell}) is True
    assert scoped.reaches({uuid4()}) is False


async def test_dorea_publishes_to_all_churches():
    platform_account = uuid4()
    anns = _FakeAnnouncements()
    cmd = PublishPlatformAnnouncement(
        anns, platform_account_id=platform_account, clock=lambda: _NOW
    )
    dto = await cmd.execute(category=Cat.INFO, title="Nouvelle version de Dorea")
    assert dto.scope == "platform" and dto.tenant_id is None
    assert dto.author_account_id == platform_account


# --- Publier : l'autorité de la portée ---


async def test_leader_publishes_to_their_cell_only():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    church = _FakeChurch([_church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id))])
    pub = PublishAnnouncement(
        _FakeAnnouncements(), _FakeGroups([cell]), _access(church), clock=lambda: _NOW
    )
    dto = await pub.execute(
        actor_account_id=leader, tenant_id=tenant, category=Cat.INFO,
        title="Salle changée", scope_group_id=cell.id,
    )
    assert dto.scope == "group"
    # …mais il ne peut pas s'adresser à toute l'église.
    with pytest.raises(UnauthorizedGroupActionError):
        await pub.execute(
            actor_account_id=leader, tenant_id=tenant, category=Cat.INFO, title="Culte 9h"
        )


async def test_secretary_publishes_church_wide_with_images():
    """Sur son PWA, la secrétaire porte la voix de l'église (le pasteur est en lecture seule)."""
    secretary, tenant = uuid4(), uuid4()
    church = _FakeChurch([_church(secretary, tenant, _role(RoleCode.SECRETARY, group_id=None))])
    pub = PublishAnnouncement(
        _FakeAnnouncements(), _FakeGroups(), _access(church), clock=lambda: _NOW
    )
    dto = await pub.execute(
        actor_account_id=secretary, tenant_id=tenant, category=Cat.WEDDING,
        title="Mariage de Awa et Yao", media_urls=["https://cdn/x.jpg"],
    )
    assert dto.scope == "church" and dto.tone == "celebration"
    assert dto.media_urls == ["https://cdn/x.jpg"]


async def test_church_wide_announcement_broadcasts_to_the_church():
    secretary, tenant, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    church = _FakeChurch([_church(secretary, tenant, _role(RoleCode.SECRETARY, group_id=None))])
    notifier = _FakeNotifier()
    pub = PublishAnnouncement(
        _FakeAnnouncements(), _FakeGroups(), _access(church),
        _FakeMembers([secretary, m1, m2]), notifier, clock=lambda: _NOW,
    )
    await pub.execute(
        actor_account_id=secretary, tenant_id=tenant, category=Cat.INFO, title="Culte à 9h"
    )
    broadcast = [c for c in notifier.calls if c[1].title == "Nouvelle annonce"]
    assert broadcast and sorted(broadcast[0][0]) == sorted([m1, m2])  # pas la secrétaire


async def test_group_scoped_announcement_enqueues_the_subtree_broadcast():
    leader, tenant, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    church = _FakeChurch([_church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id))])
    notifier, scheduler = _FakeNotifier(), _FakeScheduler()
    pub = PublishAnnouncement(
        _FakeAnnouncements(), _FakeGroups([cell]), _access(church),
        _FakeMembers(subtree={cell.id: [leader, m1, m2]}), notifier, scheduler,
        clock=lambda: _NOW,
    )
    await pub.execute(
        actor_account_id=leader, tenant_id=tenant, category=Cat.INFO,
        title="Salle changée", scope_group_id=cell.id,
    )
    # portée groupe → enqueue (outbox), pas d'envoi synchrone du broadcast
    assert not [c for c in notifier.calls if c[1].title == "Nouvelle annonce"]
    assert scheduler.calls
    targets, notif, at = scheduler.calls[0]
    assert sorted(targets) == sorted([m1, m2]) and at == _NOW  # pas le responsable (auteur)
    assert notif.data == {"type": "announcement", "id": scheduler.calls[0][1].data["id"]}


async def test_an_announcement_that_concerns_someone_notifies_them():
    secretary, tenant, widow = uuid4(), uuid4(), uuid4()
    church = _FakeChurch([_church(secretary, tenant, _role(RoleCode.SECRETARY, group_id=None))])
    notifier = _FakeNotifier()
    pub = PublishAnnouncement(
        _FakeAnnouncements(), _FakeGroups(), _access(church),
        _FakeMembers([secretary, widow]), notifier, clock=lambda: _NOW,
    )
    await pub.execute(
        actor_account_id=secretary, tenant_id=tenant, category=Cat.DEATH,
        title="Deuil", concerns_account_id=widow,
    )
    concerned = [
        c for c in notifier.calls
        if c[0] == [widow] and c[1].body == "Une annonce vous concerne."
    ]
    assert concerned  # la personne concernée est prévenue personnellement


async def test_pastor_cannot_publish_his_secretary_can():
    """Le pasteur ne parle pas lui-même : il est en lecture seule. Elle est sa voix."""
    pastor, secretary, tenant = uuid4(), uuid4(), uuid4()
    church = _FakeChurch([
        _church(pastor, tenant, _role(RoleCode.PASTOR, group_id=None)),
        _church(secretary, tenant, _role(RoleCode.SECRETARY, group_id=None)),
    ])
    pub = PublishAnnouncement(
        _FakeAnnouncements(), _FakeGroups(), _access(church), clock=lambda: _NOW
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await pub.execute(
            actor_account_id=pastor, tenant_id=tenant, category=Cat.INFO, title="Culte 9h"
        )
    dto = await pub.execute(
        actor_account_id=secretary, tenant_id=tenant, category=Cat.INFO, title="Culte 9h"
    )
    assert dto.scope == "church"


# --- Les réactions (pas de commentaires) ---


async def test_reaction_is_set_changed_and_removed():
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.DEATH, cell, uuid4())
    anns, reacts = _FakeAnnouncements([a]), _FakeReactions()
    audience = _FakeAudience({cell})
    react = SetReaction(anns, reacts, audience, clock=lambda: _NOW)

    dto = await react.execute(actor_account_id=awa, announcement_id=a.id, emoji="🙏")
    assert dto.my_reaction == "🙏"
    assert dto.reaction_counts is None  # jamais de score en retour : ce n'est pas une vitrine
    # on change d'emoji : une seule réaction par personne
    await react.execute(actor_account_id=awa, announcement_id=a.id, emoji="🖤")
    assert await reacts.counts_by_emoji(a.id) == {"🖤": 1}  # en base : une seule
    dto = await RemoveReaction(anns, reacts).execute(
        actor_account_id=awa, announcement_id=a.id
    )
    assert dto.my_reaction is None
    assert await reacts.counts_by_emoji(a.id) == {}


async def test_reaction_rejects_emoji_outside_the_category_palette():
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.DEATH, cell, uuid4())
    react = SetReaction(
        _FakeAnnouncements([a]), _FakeReactions(), _FakeAudience({cell}), clock=lambda: _NOW
    )
    with pytest.raises(EmojiNotAllowedError):
        await react.execute(actor_account_id=awa, announcement_id=a.id, emoji="🎉")


async def test_reaction_is_possible_even_on_inform():
    """« Informer » n'attend pas d'engagement — mais on peut réagir."""
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.BIRTH, cell, uuid4())  # inform
    assert a.accepts_engagement is False
    dto = await SetReaction(
        _FakeAnnouncements([a]), _FakeReactions(), _FakeAudience({cell}), clock=lambda: _NOW
    ).execute(actor_account_id=awa, announcement_id=a.id, emoji="🎉")
    assert dto.my_reaction == "🎉"


async def test_reaction_out_of_audience_is_rejected():
    tenant, cell, stranger = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.PRAYER, cell, uuid4())
    react = SetReaction(
        _FakeAnnouncements([a]), _FakeReactions(), _FakeAudience(set()), clock=lambda: _NOW
    )
    with pytest.raises(NotInAudienceError):
        await react.execute(actor_account_id=stranger, announcement_id=a.id, emoji="🙏")


# --- L'engagement ---


async def test_engage_is_idempotent_and_inform_refuses_it():
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.SERVICE, cell, uuid4(), event_at=_NOW)  # convene
    anns, engs = _FakeAnnouncements([a]), _FakeEngagements()
    engage = EngageAnnouncement(anns, engs, _FakeAudience({cell}), clock=lambda: _NOW)
    dto = await engage.execute(actor_account_id=awa, announcement_id=a.id)
    assert dto.engaged is True
    dto = await engage.execute(actor_account_id=awa, announcement_id=a.id)
    assert dto.engaged is True  # idempotent : s'engager deux fois ne compte qu'une
    # Une convocation n'a pas de plafond : le nombre n'a pas de dénominateur, donc il est tu.
    # Sans ça, « 24 confirmés » se compare d'une annonce à l'autre — c'est un score.
    assert dto.engagement_count is None
    assert await engs.count_for(a.id) == 1

    info = _ann(tenant, Cat.INFO, cell, uuid4())
    with pytest.raises(ResponsesNotAcceptedError):
        await EngageAnnouncement(
            _FakeAnnouncements([info]), _FakeEngagements(), _FakeAudience({cell}),
            clock=lambda: _NOW,
        ).execute(actor_account_id=awa, announcement_id=info.id)


async def test_mobilization_fills_refuses_then_frees():
    tenant, cell, awa, yao = uuid4(), uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.CALL, cell, uuid4(), slots=1)
    anns, engs = _FakeAnnouncements([a]), _FakeEngagements()
    audience = _FakeAudience({cell})
    engage = EngageAnnouncement(anns, engs, audience, clock=lambda: _NOW)

    dto = await engage.execute(actor_account_id=awa, announcement_id=a.id)
    assert dto.slots_remaining == 0
    with pytest.raises(MobilizationFullError):
        await engage.execute(actor_account_id=yao, announcement_id=a.id)
    await WithdrawEngagement(anns, engs).execute(actor_account_id=awa, announcement_id=a.id)
    dto = await engage.execute(actor_account_id=yao, announcement_id=a.id)  # place libérée
    assert dto.slots_remaining == 0


# --- Archivage : manuel + expiration ---


async def test_expired_announcement_leaves_the_feed_by_itself():
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.INFO, cell, uuid4(), expires_at=_NOW + timedelta(days=1))
    later = _NOW + timedelta(days=2)
    assert a.is_live(_NOW) is True
    assert a.is_live(later) is False  # expirée → hors du fil, sans geste humain

    with pytest.raises(AnnouncementClosedError):
        await SetReaction(
            _FakeAnnouncements([a]), _FakeReactions(), _FakeAudience({cell}), clock=lambda: later
        ).execute(actor_account_id=awa, announcement_id=a.id, emoji="👍")


def test_expiry_must_be_in_the_future():
    with pytest.raises(InvalidAnnouncementError):
        _ann(uuid4(), Cat.INFO, None, uuid4(), expires_at=_NOW - timedelta(days=1))


async def test_leader_archives_manually_then_reaction_is_blocked():
    leader, tenant, awa = uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    a = _ann(tenant, Cat.PRAYER, cell.id, uuid4())
    anns = _FakeAnnouncements([a])
    church = _FakeChurch([_church(leader, tenant, _role(RoleCode.GROUP_LEADER, group_id=cell.id))])
    await ArchiveAnnouncement(anns, _FakeGroups([cell]), _access(church)).execute(
        actor_account_id=leader, announcement_id=a.id
    )
    with pytest.raises(AnnouncementClosedError):
        await SetReaction(
            anns, _FakeReactions(), _FakeAudience({cell.id}), clock=lambda: _NOW
        ).execute(actor_account_id=awa, announcement_id=a.id, emoji="🙏")


async def test_a_church_cannot_archive_a_dorea_announcement():
    admin, tenant = uuid4(), uuid4()
    a = _ann(None, Cat.INFO, None, uuid4())  # annonce Dorea
    church = _FakeChurch([_church(admin, tenant, _role(RoleCode.ADMIN, group_id=None))])
    with pytest.raises(UnauthorizedGroupActionError):
        await ArchiveAnnouncement(
            _FakeAnnouncements([a]), _FakeGroups(), _access(church)
        ).execute(actor_account_id=admin, announcement_id=a.id)


# --- Le fil d'actualité ---


async def test_feed_merges_dorea_church_and_my_groups():
    tenant, cell, other, awa = uuid4(), uuid4(), uuid4(), uuid4()
    dorea = _ann(None, Cat.INFO, None, uuid4(), published_at=_NOW)
    wide = _ann(tenant, Cat.INFO, None, uuid4(), published_at=_NOW - timedelta(hours=1))
    mine = _ann(tenant, Cat.INFO, cell, uuid4(), published_at=_NOW - timedelta(hours=2))
    theirs = _ann(tenant, Cat.INFO, other, uuid4(), published_at=_NOW - timedelta(hours=3))
    feed = ListMyAnnouncements(
        _FakeAnnouncements([dorea, wide, mine, theirs]),
        _FakeEngagements(), _FakeReactions(), _FakeAudience({cell}),
        _FakeChurch([_church(awa, tenant)]), clock=lambda: _NOW,
    )
    dto = await feed.execute(actor_account_id=awa, tenant_id=tenant)

    assert [a.id for a in dto.announcements] == [dorea.id, wide.id, mine.id]  # tri récent→ancien
    assert theirs.id not in {a.id for a in dto.announcements}  # hors de sa portée
    assert dto.announcements[0].scope == "platform"


async def test_a_foreign_member_cannot_read_a_church_feed():
    tenant, awa = uuid4(), uuid4()
    wide = _ann(tenant, Cat.INFO, None, uuid4())  # annonce église-entière
    feed = ListMyAnnouncements(
        _FakeAnnouncements([wide]), _FakeEngagements(), _FakeReactions(),
        _FakeAudience(), _FakeChurch([]), clock=lambda: _NOW,  # l'intrus n'est membre de rien
    )
    with pytest.raises(NotAChurchMemberError):  # isolation inter-église (DOREA-012)
        await feed.execute(actor_account_id=awa, tenant_id=tenant)


async def test_feed_paginates_with_a_cursor():
    tenant, awa = uuid4(), uuid4()
    items = [
        _ann(tenant, Cat.INFO, None, uuid4(), published_at=_NOW - timedelta(hours=i))
        for i in range(5)
    ]
    feed = ListMyAnnouncements(
        _FakeAnnouncements(items), _FakeEngagements(), _FakeReactions(),
        _FakeAudience(), _FakeChurch([_church(awa, tenant)]), clock=lambda: _NOW,
    )
    page1 = await feed.execute(actor_account_id=awa, tenant_id=tenant, limit=2)
    assert len(page1.announcements) == 2 and page1.next_before is not None
    page2 = await feed.execute(
        actor_account_id=awa, tenant_id=tenant, limit=2, before=page1.next_before
    )
    assert {a.id for a in page1.announcements}.isdisjoint({a.id for a in page2.announcements})


async def test_feed_carries_reactions_and_my_state():
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.BIRTH, cell, uuid4())
    anns, reacts = _FakeAnnouncements([a]), _FakeReactions()
    audience = _FakeAudience({cell})
    await SetReaction(anns, reacts, audience, clock=lambda: _NOW).execute(
        actor_account_id=awa, announcement_id=a.id, emoji="🎉"
    )
    dto = await ListMyAnnouncements(
        anns, _FakeEngagements(), reacts, audience,
        _FakeChurch([_church(awa, tenant)]), clock=lambda: _NOW,
    ).execute(actor_account_id=awa, tenant_id=tenant)
    card = dto.announcements[0]
    assert card.tone == "joy"  # la couleur voyage jusqu'au fil
    assert card.my_reaction == "🎉"  # je sais que j'ai réagi…
    assert card.reaction_counts is None  # …mais le fil ne porte AUCUN score
    assert card.allowed_emojis == ["🎉", "❤️", "👶"]  # la palette du type


# --- Les noms : l'auteur voit, un tiers non ---


async def test_death_is_an_uncapped_mobilization_nobody_caps_a_veillee():
    """Le décès mobilise : la veillée ne se remplit jamais, tout le monde peut venir."""
    tenant, cell = uuid4(), uuid4()
    a = _ann(tenant, Cat.DEATH, cell, uuid4())  # aucun plafond
    anns, engs = _FakeAnnouncements([a]), _FakeEngagements()
    engage = EngageAnnouncement(anns, engs, _FakeAudience({cell}), clock=lambda: _NOW)

    assert a.accepts_engagement is True  # on s'engage, on ne se contente pas de cliquer 🙏
    for _ in range(30):  # trente personnes à la veillée : jamais « complet »
        dto = await engage.execute(actor_account_id=uuid4(), announcement_id=a.id)
    assert await engs.count_for(a.id) == 30  # elles sont bien là
    assert dto.slots_remaining is None  # pas de plafond, donc pas de reste
    # **Et le nombre ne s'affiche pas.** « 30 portent » sur un décès est un score ; ce compte a
    # déjà son destinataire légitime — la famille, par `GetConsolation`.
    assert dto.engagement_count is None


# --- L'anti-vitrine : le décompte va au sujet, pas à l'auteur ---


async def test_consolation_goes_to_the_subject_never_to_the_author():
    tenant, cell, secretary, widow = uuid4(), uuid4(), uuid4(), uuid4()
    # La secrétaire publie ; l'annonce CONCERNE la veuve.
    a = _ann(tenant, Cat.DEATH, cell, secretary, concerns=widow)
    anns, reacts, engs = _FakeAnnouncements([a]), _FakeReactions(), _FakeEngagements()
    react = SetReaction(anns, reacts, _FakeAudience({cell}), clock=lambda: _NOW)
    for _ in range(32):
        await react.execute(actor_account_id=uuid4(), announcement_id=a.id, emoji="🙏")

    consolation = GetConsolation(anns, reacts, engs, _access(_FakeChurch()))
    # La veuve reçoit le décompte — c'est une consolation.
    dto = await consolation.execute(actor_account_id=widow, announcement_id=a.id)
    assert dto.total == 32 and dto.reaction_counts == {"🙏": 32}

    # La secrétaire qui a publié ne récolte RIEN : ce n'est pas son applaudimètre.
    with pytest.raises(UnauthorizedGroupActionError):
        await consolation.execute(actor_account_id=secretary, announcement_id=a.id)


async def test_pastor_sees_the_truth_reactions_versus_real_presence():
    """« 40 réactions, 2 personnes à la veillée » — le révélateur, pas la vitrine."""
    tenant, cell, pastor, widow = uuid4(), uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.DEATH, cell, uuid4(), concerns=widow)
    anns, reacts, engs = _FakeAnnouncements([a]), _FakeReactions(), _FakeEngagements()
    audience = _FakeAudience({cell})
    for _ in range(40):  # 40 clics de compassion
        await SetReaction(anns, reacts, audience, clock=lambda: _NOW).execute(
            actor_account_id=uuid4(), announcement_id=a.id, emoji="🙏"
        )
    for _ in range(2):  # 2 personnes se déplacent réellement
        await EngageAnnouncement(anns, engs, audience, clock=lambda: _NOW).execute(
            actor_account_id=uuid4(), announcement_id=a.id
        )
    church = _FakeChurch([_church(pastor, tenant, _role(RoleCode.PASTOR, group_id=None))])
    dto = await GetConsolation(anns, reacts, engs, _access(church)).execute(
        actor_account_id=pastor, announcement_id=a.id
    )
    assert dto.total == 40 and dto.engagement_count == 2  # l'écart est visible


async def test_a_stranger_never_sees_the_count():
    tenant, cell, widow, nosy = uuid4(), uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.DEATH, cell, uuid4(), concerns=widow)
    consolation = GetConsolation(
        _FakeAnnouncements([a]), _FakeReactions(), _FakeEngagements(), _access(_FakeChurch())
    )
    with pytest.raises(UnauthorizedGroupActionError):
        await consolation.execute(actor_account_id=nosy, announcement_id=a.id)


# --- RSVP → présence M6 : « je viens » pré-remplit le roster ---


async def test_convene_engagement_prefills_gathering_rsvp_and_withdraw_clears():
    tenant, cell, awa, gid = uuid4(), uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.SERVICE, cell, uuid4(), event_at=_NOW, gathering=gid)  # convoquer
    anns, engs, port = _FakeAnnouncements([a]), _FakeEngagements(), _FakeRsvpPort()

    await EngageAnnouncement(
        anns, engs, _FakeAudience({cell}), clock=lambda: _NOW, rsvp=port
    ).execute(actor_account_id=awa, announcement_id=a.id)
    assert port.set == [(gid, awa)]  # « je viens » → présence attendue M6

    await WithdrawEngagement(anns, engs, rsvp=port).execute(
        actor_account_id=awa, announcement_id=a.id
    )
    assert port.cleared == [(gid, awa)]  # se rétracter retire le RSVP


async def test_mobilization_engagement_without_a_gathering_touches_no_rsvp():
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.CALL, cell, uuid4(), slots=3)  # mobiliser, aucune rencontre liée
    port = _FakeRsvpPort()
    await EngageAnnouncement(
        _FakeAnnouncements([a]), _FakeEngagements(), _FakeAudience({cell}),
        clock=lambda: _NOW, rsvp=port,
    ).execute(actor_account_id=awa, announcement_id=a.id)
    assert port.set == []  # pas de rencontre → pas de RSVP


# --- Idée ① : l'Église parle, pas la personne (le fil dé-identifié) ---


async def test_feed_hides_the_author_and_tells_only_the_subject():
    tenant, cell, secretary, widow, other = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.DEATH, cell, secretary, concerns=widow)
    anns = _FakeAnnouncements([a])

    church = _FakeChurch([_church(widow, tenant), _church(other, tenant)])

    def feed_for(who):
        return ListMyAnnouncements(
            anns, _FakeEngagements(), _FakeReactions(), _FakeAudience({cell}),
            church, clock=lambda: _NOW,
        ).execute(actor_account_id=who, tenant_id=tenant)

    card = (await feed_for(widow)).announcements[0]
    assert card.author_account_id is None  # la secrétaire n'est pas signée
    assert card.concerns_account_id is None  # l'identité du sujet n'est exposée à personne
    assert card.concerns_me is True  # …mais la veuve sait que c'est pour elle

    other_card = (await feed_for(other)).announcements[0]
    assert other_card.concerns_me is False  # un tiers ne se voit pas concerné


async def test_backoffice_reveals_the_author_for_accountability():
    admin, tenant, secretary, widow = uuid4(), uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.DEATH, None, secretary, concerns=widow)  # église-entière
    church = _FakeChurch([_church(admin, tenant, _role(RoleCode.ADMIN, group_id=None))])
    dto = await ListChurchAnnouncements(
        _FakeAnnouncements([a]), _FakeEngagements(), _FakeReactions(), _access(church)
    ).execute(actor_account_id=admin, tenant_id=tenant)
    card = dto.announcements[0]
    assert card.author_account_id == secretary  # le pilotage voit qui a publié
    assert card.concerns_account_id == widow


# --- Idée ② : le clic n'absout pas (la réaction ouvre un geste) ---


async def test_reaction_opens_an_invitation_toward_the_costly_gesture():
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.DEATH, cell, uuid4())  # mobilize (veillée)
    dto = await SetReaction(
        _FakeAnnouncements([a]), _FakeReactions(), _FakeAudience({cell}), clock=lambda: _NOW
    ).execute(actor_account_id=awa, announcement_id=a.id, emoji="🙏")
    # Réagir 🙏 ne clôt rien : ça invite à venir à la veillée.
    assert dto.invitation == "come"


async def test_invitation_depends_on_intent_and_disappears_once_engaged():
    tenant, cell = uuid4(), uuid4()
    convene = _ann(tenant, Cat.SERVICE, cell, uuid4(), event_at=_NOW)  # convene
    pray = _ann(tenant, Cat.PRAYER, cell, uuid4())  # pray
    info = _ann(tenant, Cat.BIRTH, cell, uuid4())  # inform → aucun engagement
    assert convene.invitation().value == "confirm"
    assert pray.invitation().value == "reach_out"
    assert info.invitation() is None  # « informer » n'ouvre sur rien

    # Une fois qu'on s'est engagé, le geste est fait : plus d'invitation.
    anns, engs = _FakeAnnouncements([convene]), _FakeEngagements()
    dto = await EngageAnnouncement(
        anns, engs, _FakeAudience({cell}), clock=lambda: _NOW
    ).execute(actor_account_id=uuid4(), announcement_id=convene.id)
    assert dto.engaged is True and dto.invitation is None


async def test_responders_visible_to_author_hidden_from_outsider():
    tenant, author, awa, outsider = uuid4(), uuid4(), uuid4(), uuid4()
    cell = _cell(tenant)
    a = _ann(tenant, Cat.CALL, cell.id, author, slots=3)
    anns, engs = _FakeAnnouncements([a]), _FakeEngagements()
    await EngageAnnouncement(anns, engs, _FakeAudience({cell.id}), clock=lambda: _NOW).execute(
        actor_account_id=awa, announcement_id=a.id
    )
    listing = ListResponders(anns, engs, _FakeGroups([cell]), _access(_FakeChurch()))
    dto = await listing.execute(actor_account_id=author, announcement_id=a.id)
    assert dto.count == 1 and dto.responders[0].account_id == awa
    with pytest.raises(UnauthorizedGroupActionError):
        await listing.execute(actor_account_id=outsider, announcement_id=a.id)


# --- La règle du dénominateur ---


async def test_a_capped_mobilization_shows_the_count_because_it_has_a_denominator():
    """« 12 / 15 places » ne se lit pas comme une popularité : ça se lit *reste-t-il une place*.

    Sans ce nombre, le membre ne peut pas décider — c'est de la capacité, pas un score. C'est le
    seul cas où un compteur public est légitime."""
    tenant, cell, awa = uuid4(), uuid4(), uuid4()
    a = _ann(tenant, Cat.CALL, cell, uuid4(), slots=15)  # un appel à volontaires, plafonné
    engs = _FakeEngagements()
    engage = EngageAnnouncement(
        _FakeAnnouncements([a]), engs, _FakeAudience({cell}), clock=lambda: _NOW
    )

    dto = await engage.execute(actor_account_id=awa, announcement_id=a.id)

    assert a.is_capped is True
    assert dto.engagement_count == 1  # le compte, **avec** son dénominateur
    assert dto.slots_needed == 15
    assert dto.slots_remaining == 14
