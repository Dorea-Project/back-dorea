"""Module Event (E-0, portée église) : publier, réagir, confirmer sa présence.

Tout membre publie pour son église (au-delà = compte Business, à venir) ; réactions comptées ;
liste des présents réservée à l'organisateur.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.events.application.commands.engage_event import (
    REMINDER_LEAD_HOURS,
    ConfirmParticipation,
    ReactToEvent,
    WithdrawParticipation,
)
from app.contexts.events.application.commands.moderation import (
    ReportEvent,
    TakeDownEvent,
)
from app.contexts.events.application.commands.publish_event import (
    CancelEvent,
    PublishEvent,
)
from app.contexts.events.application.commands.record_view import RecordEventView
from app.contexts.events.application.ports import BusinessTierPort, EventAudiencePort
from app.contexts.events.application.queries.event_stats import GetEventStats
from app.contexts.events.application.queries.reported_events import ListReportedEvents
from app.contexts.events.application.queries.view_events import (
    GetEvent,
    GetPublicEvent,
    ListChurchEvents,
    ListParticipants,
    ListVisibleEvents,
)
from app.contexts.events.domain.aggregates import (
    MAX_COVER_TEXT,
    PUBLICATION_COOLDOWN_DAYS,
    Event,
    EventCover,
)
from app.contexts.events.domain.enums import (
    CoverKind,
    EventCategory,
    EventReaction,
    EventScope,
)
from app.contexts.events.domain.errors import (
    EventCancelledError,
    EventTakenDownError,
    InvalidEventError,
    NotAChurchMemberError,
    NotEventAuthorError,
    PublicationCadenceError,
    WiderReachRequiresBusinessError,
    WiderReachRequiresMandateError,
)
from app.contexts.events.domain.repositories import (
    EventParticipantRepository,
    EventReactionRepository,
    EventReportRepository,
    EventRepository,
    EventViewRepository,
)
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.notifications.application.notifier import Notifier

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_SOON = _NOW + timedelta(days=10)


# --- fakes ---


class _FakeMemberships(MembershipRepository):
    def __init__(self, items=()):
        self._m = list(items)

    async def get_active(self, account_id, tenant_id):
        return next(
            (m for m in self._m if m.account_id == account_id and m.tenant_id == tenant_id), None
        )

    async def list_active_by_account(self, account_id):
        return [m for m in self._m if m.account_id == account_id]

    async def count_active_group_leaders(self, tenant_id, group_id):
        return 0


class _FakeEvents(EventRepository):
    def __init__(self, items=()):
        self._e = list(items)

    async def add(self, event):
        self._e.append(event)

    async def get(self, event_id):
        return next((e for e in self._e if e.id == event_id), None)

    async def save(self, event):
        pass  # muté en mémoire

    async def list_published_by_tenant(self, tenant_id):
        from app.contexts.events.domain.enums import EventStatus
        return [
            e for e in self._e
            if e.tenant_id == tenant_id and e.status is EventStatus.PUBLISHED
        ]

    async def last_published_at_by(self, author_account_id, tenant_id):
        # Les annulés et les retirés comptent : annuler ne remet pas le compteur à zéro.
        dates = [
            e.created_at for e in self._e
            if e.author_account_id == author_account_id and e.tenant_id == tenant_id
        ]
        return max(dates) if dates else None

    async def list_published_by_scope(self, scope, tenant_ids=None):
        from app.contexts.events.domain.enums import EventStatus
        res = [
            e for e in self._e
            if e.status is EventStatus.PUBLISHED and e.scope is scope
        ]
        if tenant_ids is not None:
            res = [e for e in res if e.tenant_id in set(tenant_ids)]
        return res


class _FakeParticipants(EventParticipantRepository):
    def __init__(self):
        self._p = []

    async def add(self, participant):
        self._p.append(participant)

    async def get(self, event_id, account_id):
        return next(
            (p for p in self._p if p.event_id == event_id and p.account_id == account_id), None
        )

    async def remove(self, event_id, account_id):
        self._p = [
            p for p in self._p if not (p.event_id == event_id and p.account_id == account_id)
        ]

    async def list_by_event(self, event_id):
        return [p for p in self._p if p.event_id == event_id]

    async def count_by_event(self, event_id):
        return sum(1 for p in self._p if p.event_id == event_id)


class _FakeReactions(EventReactionRepository):
    def __init__(self):
        self._r = []

    async def get_for(self, event_id, account_id):
        return next(
            (r for r in self._r if r.event_id == event_id and r.account_id == account_id), None
        )

    async def add(self, reaction):
        self._r.append(reaction)

    async def remove(self, event_id, account_id):
        self._r = [
            r for r in self._r if not (r.event_id == event_id and r.account_id == account_id)
        ]

    async def counts_by_kind(self, event_id):
        out = {}
        for r in self._r:
            if r.event_id == event_id:
                out[r.kind] = out.get(r.kind, 0) + 1
        return out


class _FakeViews(EventViewRepository):
    def __init__(self):
        self._v = []

    async def get(self, event_id, viewer_account_id):
        return next(
            (x for x in self._v
             if x.event_id == event_id and x.viewer_account_id == viewer_account_id),
            None,
        )

    async def add(self, view):
        self._v.append(view)

    async def count_by_event(self, event_id):
        return sum(1 for x in self._v if x.event_id == event_id)

    async def counts_by_denomination(self, event_id):
        out = {}
        for x in self._v:
            if x.event_id == event_id:
                out[x.denomination] = out.get(x.denomination, 0) + 1
        return out


class _FakeAudience(EventAudiencePort):
    def __init__(
        self, denomination=None, member_count=0, peers=(), members=(), all_tenants=(),
        locations=None, near=None,
    ):
        self._denomination = denomination
        self._member_count = member_count
        self._peers = list(peers)
        self._members = list(members)
        self._all_tenants = list(all_tenants)
        # `locations` : tenant -> (lat, lon). `near` : les églises à portée, si on veut les
        # imposer sans passer par la géométrie.
        self._locations = dict(locations or {})
        self._near = list(near) if near is not None else None

    async def denomination_of(self, tenant_id):
        return self._denomination

    async def count_active_members(self, tenant_id):
        return self._member_count

    async def tenants_in_denomination(self, denomination):
        return list(self._peers)

    async def all_tenant_ids(self):
        return list(self._all_tenants)

    async def member_account_ids(self, tenant_ids):
        return list(self._members)

    async def location_of(self, tenant_id):
        return self._locations.get(tenant_id)

    async def tenants_near(self, *, latitude, longitude, radius_km):
        if self._near is not None:
            return list(self._near)
        from app.contexts.events.domain.geo import distance_km

        return [
            t for t, (lat, lon) in self._locations.items()
            if distance_km(latitude, longitude, lat, lon) <= radius_km
        ]


class _FakeBusiness(BusinessTierPort):
    def __init__(self, is_business=False):
        self._b = is_business

    async def is_business(self, account_id):
        return self._b


class _FakeReports(EventReportRepository):
    def __init__(self):
        self._r = []

    async def get(self, event_id, reporter_account_id):
        return next(
            (x for x in self._r
             if x.event_id == event_id and x.reporter_account_id == reporter_account_id),
            None,
        )

    async def add(self, report):
        self._r.append(report)

    async def count_by_event(self, event_id):
        return sum(1 for x in self._r if x.event_id == event_id)

    async def counts_by_event(self):
        out = {}
        for x in self._r:
            out[x.event_id] = out.get(x.event_id, 0) + 1
        return out


class _FakeNotifier(Notifier):
    def __init__(self):
        self.calls = []

    async def notify(self, account_ids, notification):
        self.calls.append((list(account_ids), notification))


class _FakeScheduler:
    def __init__(self):
        self.calls = []

    async def schedule(self, account_ids, notification, *, at):
        self.calls.append((list(account_ids), notification, at))


def _member(account, tenant) -> Membership:
    return Membership(
        id=uuid4(), account_id=account, tenant_id=tenant,
        status=MembershipStatus.CONFIRMED_MEMBER, last_transition_at=_NOW, role_assignments=[],
    )


def _event(tenant, author, *, cancelled=False) -> Event:
    e = Event.publish(
        id=uuid4(), tenant_id=tenant, author_account_id=author,
        category=EventCategory.VIGIL, title="Veillée", starts_at=_SOON, now=_NOW,
    )
    if cancelled:
        e.cancel()
    return e


# --- Le domaine ---


def test_publish_requires_a_title():
    with pytest.raises(InvalidEventError):
        Event.publish(
            id=uuid4(), tenant_id=uuid4(), author_account_id=uuid4(),
            category=EventCategory.OTHER, title="   ", starts_at=_SOON, now=_NOW,
        )


def test_publish_beyond_church_requires_business():
    with pytest.raises(WiderReachRequiresBusinessError):
        Event.publish(
            id=uuid4(), tenant_id=uuid4(), author_account_id=uuid4(),
            category=EventCategory.CONVENTION, title="Convention", starts_at=_SOON, now=_NOW,
            scope=EventScope.DENOMINATION,
        )


def test_publish_validates_geo_and_end():
    with pytest.raises(InvalidEventError):  # latitude sans longitude
        Event.publish(
            id=uuid4(), tenant_id=uuid4(), author_account_id=uuid4(),
            category=EventCategory.OTHER, title="x", starts_at=_SOON, now=_NOW, latitude=5.3,
        )
    with pytest.raises(InvalidEventError):  # fin avant début
        Event.publish(
            id=uuid4(), tenant_id=uuid4(), author_account_id=uuid4(),
            category=EventCategory.OTHER, title="x", starts_at=_SOON, now=_NOW,
            ends_at=_SOON - timedelta(hours=1),
        )


# --- Publier / annuler ---


async def test_member_publishes_a_church_event():
    member, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    cmd = PublishEvent(_FakeEvents(), ms, _FakeBusiness(), clock=lambda: _NOW)
    dto = await cmd.execute(
        actor_account_id=member, tenant_id=tenant,
        category=EventCategory.CONCERT, title="Concert de louange", starts_at=_SOON,
    )
    assert dto.scope == "church" and dto.status == "published"
    assert dto.author_account_id == member


async def test_a_non_member_cannot_publish():
    cmd = PublishEvent(_FakeEvents(), _FakeMemberships(), _FakeBusiness(), clock=lambda: _NOW)
    with pytest.raises(NotAChurchMemberError):
        await cmd.execute(
            actor_account_id=uuid4(), tenant_id=uuid4(),
            category=EventCategory.OTHER, title="x", starts_at=_SOON,
        )


async def test_a_business_author_publishes_at_denomination_scope():
    member, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    cmd = PublishEvent(_FakeEvents(), ms, _FakeBusiness(is_business=True), clock=lambda: _NOW)
    dto = await cmd.execute(
        actor_account_id=member, tenant_id=tenant,
        category=EventCategory.CONVENTION, title="Convention régionale", starts_at=_SOON,
        scope=EventScope.DENOMINATION,
    )
    assert dto.scope == "denomination"


async def test_a_free_author_cannot_publish_beyond_church():
    member, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    cmd = PublishEvent(_FakeEvents(), ms, _FakeBusiness(is_business=False), clock=lambda: _NOW)
    with pytest.raises(WiderReachRequiresBusinessError):
        await cmd.execute(
            actor_account_id=member, tenant_id=tenant,
            category=EventCategory.CONVENTION, title="x", starts_at=_SOON,
            scope=EventScope.PLATFORM,
        )


async def test_author_cancels_their_event():
    tenant, author = uuid4(), uuid4()
    e = _event(tenant, author)
    dto = await CancelEvent(_FakeEvents([e]), clock=lambda: _NOW).execute(
        actor_account_id=author, event_id=e.id
    )
    assert dto.status == "cancelled"


async def test_a_non_author_cannot_cancel():
    tenant, author = uuid4(), uuid4()
    e = _event(tenant, author)
    with pytest.raises(NotEventAuthorError):
        await CancelEvent(_FakeEvents([e]), clock=lambda: _NOW).execute(
            actor_account_id=uuid4(), event_id=e.id
        )


# --- Réactions ---


async def test_member_reacts_and_it_is_counted():
    tenant, member, author = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    events, reacts = _FakeEvents([_event(tenant, author)]), _FakeReactions()
    e = events._e[0]
    await ReactToEvent(events, reacts, ms, clock=lambda: _NOW).execute(
        actor_account_id=member, event_id=e.id, kind=EventReaction.INTERESTED
    )
    dto = await GetEvent(events, _FakeParticipants(), reacts, _FakeAudience(), ms).execute(
        event_id=e.id, viewer_account_id=member
    )
    # Ma réaction reste visible (état individuel) ; le décompte agrégé n'est plus exposé sur la
    # carte/le détail (invariant anti-compteur). La donnée, elle, reste enregistrée.
    assert dto.my_reaction == "interested"
    assert not hasattr(dto, "reaction_counts")
    assert await reacts.counts_by_kind(e.id) == {EventReaction.INTERESTED: 1}


async def test_re_reacting_changes_the_kind():
    tenant, member, author = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    events, reacts = _FakeEvents([_event(tenant, author)]), _FakeReactions()
    e = events._e[0]
    react = ReactToEvent(events, reacts, ms, clock=lambda: _NOW)
    await react.execute(actor_account_id=member, event_id=e.id, kind=EventReaction.INTERESTED)
    await react.execute(actor_account_id=member, event_id=e.id, kind=EventReaction.BLESSED)
    counts = await reacts.counts_by_kind(e.id)
    assert counts == {EventReaction.BLESSED: 1}  # une seule réaction par membre


async def test_cannot_react_to_a_cancelled_event():
    tenant, member, author = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    e = _event(tenant, author, cancelled=True)
    with pytest.raises(EventCancelledError):
        await ReactToEvent(_FakeEvents([e]), _FakeReactions(), ms, clock=lambda: _NOW).execute(
            actor_account_id=member, event_id=e.id, kind=EventReaction.PRAY
        )


# --- Présence confirmée ---


async def test_member_confirms_presence_and_it_is_counted():
    tenant, member, author = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    events, parts = _FakeEvents([_event(tenant, author)]), _FakeParticipants()
    e = events._e[0]
    confirm = ConfirmParticipation(events, parts, ms, clock=lambda: _NOW)
    await confirm.execute(actor_account_id=member, event_id=e.id)
    await confirm.execute(actor_account_id=member, event_id=e.id)  # idempotent
    dto = await GetEvent(events, parts, _FakeReactions(), _FakeAudience(), ms).execute(
        event_id=e.id, viewer_account_id=member
    )
    assert dto.i_confirmed is True
    # Le décompte n'est plus public : sans capacité, « 24 confirmés » est un nombre nu, donc
    # comparable d'un événement à l'autre, donc un score. L'organisateur le lit dans /stats.
    assert dto.participant_count is None
    assert await parts.count_by_event(e.id) == 1  # la donnée est bien là


async def test_withdraw_removes_presence():
    tenant, member, author = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    events, parts = _FakeEvents([_event(tenant, author)]), _FakeParticipants()
    e = events._e[0]
    await ConfirmParticipation(events, parts, ms, clock=lambda: _NOW).execute(
        actor_account_id=member, event_id=e.id
    )
    await WithdrawParticipation(parts).execute(actor_account_id=member, event_id=e.id)
    assert await parts.count_by_event(e.id) == 0


# --- La liste des présents : l'organisateur seul ---


async def test_organizer_sees_the_participant_list():
    tenant, author, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(m1, tenant), _member(m2, tenant)])
    events, parts = _FakeEvents([_event(tenant, author)]), _FakeParticipants()
    e = events._e[0]
    confirm = ConfirmParticipation(events, parts, ms, clock=lambda: _NOW)
    await confirm.execute(actor_account_id=m1, event_id=e.id)
    await confirm.execute(actor_account_id=m2, event_id=e.id)
    listed = await ListParticipants(events, parts).execute(
        actor_account_id=author, event_id=e.id
    )
    assert len(listed) == 2


async def test_a_non_organizer_cannot_see_the_participant_list():
    tenant, author = uuid4(), uuid4()
    events = _FakeEvents([_event(tenant, author)])
    with pytest.raises(NotEventAuthorError):
        await ListParticipants(events, _FakeParticipants()).execute(
            actor_account_id=uuid4(), event_id=events._e[0].id
        )


# --- Le fil ---


async def test_feed_lists_my_church_events_by_date():
    tenant, author, viewer = uuid4(), uuid4(), uuid4()
    soon = _event(tenant, author)
    later = Event.publish(
        id=uuid4(), tenant_id=tenant, author_account_id=author,
        category=EventCategory.SEMINAR, title="Séminaire", starts_at=_SOON + timedelta(days=5),
        now=_NOW,
    )
    events = _FakeEvents([later, soon])  # ajoutés dans le désordre
    ms = _FakeMemberships([_member(viewer, tenant)])
    feed = await ListVisibleEvents(
        events, _FakeParticipants(), _FakeReactions(), _FakeAudience(), ms
    ).execute(tenant_id=tenant, viewer_account_id=viewer)
    assert [e.title for e in feed] == ["Veillée", "Séminaire"]  # triés par date


def _wider(tenant, author, title, scope, *, days):
    return Event.publish(
        id=uuid4(), tenant_id=tenant, author_account_id=author, category=EventCategory.CONVENTION,
        title=title, starts_at=_SOON + timedelta(days=days), now=_NOW, scope=scope,
        business_active=True,
    )


async def test_visible_feed_reaches_denomination_and_platform_but_not_foreign():
    mine_t, peer_t, other_t = uuid4(), uuid4(), uuid4()
    author, viewer = uuid4(), uuid4()
    mine = _event(mine_t, author)  # mon église (« Veillée »)
    denom = _wider(peer_t, author, "Convention dénomination", EventScope.DENOMINATION, days=1)
    platform = _wider(other_t, author, "Grand concert Dorea", EventScope.PLATFORM, days=2)
    foreign = _wider(other_t, author, "Convention étrangère", EventScope.DENOMINATION, days=3)
    events = _FakeEvents([mine, denom, platform, foreign])
    # ma dénomination = {mon église, l'église sœur} ; other_t en est exclue
    audience = _FakeAudience(denomination="AD", peers=[mine_t, peer_t])
    ms = _FakeMemberships([_member(viewer, mine_t)])
    feed = await ListVisibleEvents(
        events, _FakeParticipants(), _FakeReactions(), audience, ms
    ).execute(tenant_id=mine_t, viewer_account_id=viewer)
    titles = {e.title for e in feed}
    assert titles == {"Veillée", "Convention dénomination", "Grand concert Dorea"}
    assert "Convention étrangère" not in titles  # dénomination étrangère → invisible


async def test_a_foreign_member_cannot_read_a_church_feed_or_event():
    tenant, foreign, author = uuid4(), uuid4(), uuid4()
    events = _FakeEvents([_event(tenant, author)])  # événement portée église
    ms = _FakeMemberships([])  # l'intrus n'est membre d'aucune église
    with pytest.raises(NotAChurchMemberError):  # fil inter-tenant refusé (DOREA-013)
        await ListVisibleEvents(
            events, _FakeParticipants(), _FakeReactions(), _FakeAudience(), ms
        ).execute(tenant_id=tenant, viewer_account_id=foreign)
    with pytest.raises(NotAChurchMemberError):  # IDOR par id refusé (DOREA-014)
        await GetEvent(events, _FakeParticipants(), _FakeReactions(), _FakeAudience(), ms).execute(
            event_id=events._e[0].id, viewer_account_id=foreign
        )


# --- Modération : signalement (membre) + retrait (Plateforme) ---


async def test_member_reports_an_event_once():
    tenant, member, author = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    events, reports = _FakeEvents([_event(tenant, author)]), _FakeReports()
    e = events._e[0]
    cmd = ReportEvent(events, reports, ms, clock=lambda: _NOW)
    await cmd.execute(actor_account_id=member, event_id=e.id, reason="spam")
    await cmd.execute(actor_account_id=member, event_id=e.id, reason="encore")  # idempotent
    assert await reports.count_by_event(e.id) == 1


async def test_a_non_member_cannot_report():
    tenant, author = uuid4(), uuid4()
    e = _event(tenant, author)
    cmd = ReportEvent(_FakeEvents([e]), _FakeReports(), _FakeMemberships(), clock=lambda: _NOW)
    with pytest.raises(NotAChurchMemberError):
        await cmd.execute(actor_account_id=uuid4(), event_id=e.id)


async def test_platform_takes_down_an_event():
    tenant, author = uuid4(), uuid4()
    events = _FakeEvents([_event(tenant, author)])
    dto = await TakeDownEvent(events, clock=lambda: _NOW).execute(
        event_id=events._e[0].id, reason="abus"
    )
    assert dto.status == "taken_down"


async def test_cannot_react_to_a_taken_down_event():
    tenant, member, author = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    events = _FakeEvents([_event(tenant, author)])
    e = events._e[0]
    await TakeDownEvent(events, clock=lambda: _NOW).execute(event_id=e.id)
    with pytest.raises(EventTakenDownError):
        await ReactToEvent(events, _FakeReactions(), ms, clock=lambda: _NOW).execute(
            actor_account_id=member, event_id=e.id, kind=EventReaction.PRAY
        )


async def test_a_taken_down_event_leaves_the_feed():
    tenant, author, viewer = uuid4(), uuid4(), uuid4()
    events = _FakeEvents([_event(tenant, author)])
    ms = _FakeMemberships([_member(viewer, tenant)])
    await TakeDownEvent(events, clock=lambda: _NOW).execute(event_id=events._e[0].id)
    feed = await ListVisibleEvents(
        events, _FakeParticipants(), _FakeReactions(), _FakeAudience(), ms
    ).execute(tenant_id=tenant, viewer_account_id=viewer)
    assert feed == []


async def test_review_queue_ranks_by_report_count():
    tenant, a1, a2, author = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(a1, tenant), _member(a2, tenant)])
    e1 = _event(tenant, author)  # « Veillée »
    e2 = Event.publish(
        id=uuid4(), tenant_id=tenant, author_account_id=author,
        category=EventCategory.CONCERT, title="Concert", starts_at=_SOON, now=_NOW,
    )
    events, reports = _FakeEvents([e1, e2]), _FakeReports()
    report = ReportEvent(events, reports, ms, clock=lambda: _NOW)
    await report.execute(actor_account_id=a1, event_id=e1.id)
    await report.execute(actor_account_id=a2, event_id=e1.id)  # Veillée : 2
    await report.execute(actor_account_id=a1, event_id=e2.id)  # Concert : 1
    queue = await ListReportedEvents(events, reports).execute()
    assert [(r.title, r.report_count) for r in queue] == [("Veillée", 2), ("Concert", 1)]


# --- Notifications (déclencheurs Event) ---


async def test_cancelling_notifies_the_confirmed_participants():
    tenant, author, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(m1, tenant), _member(m2, tenant)])
    events, parts = _FakeEvents([_event(tenant, author)]), _FakeParticipants()
    e = events._e[0]
    confirm = ConfirmParticipation(events, parts, ms, clock=lambda: _NOW)
    await confirm.execute(actor_account_id=m1, event_id=e.id)
    await confirm.execute(actor_account_id=m2, event_id=e.id)
    notifier = _FakeNotifier()
    await CancelEvent(events, parts, notifier, clock=lambda: _NOW).execute(
        actor_account_id=author, event_id=e.id
    )
    assert notifier.calls and sorted(notifier.calls[0][0]) == sorted([m1, m2])


async def test_takedown_notifies_the_author():
    tenant, author = uuid4(), uuid4()
    events = _FakeEvents([_event(tenant, author)])
    notifier = _FakeNotifier()
    await TakeDownEvent(events, notifier, clock=lambda: _NOW).execute(event_id=events._e[0].id)
    assert notifier.calls and notifier.calls[0][0] == [author]


async def test_confirming_presence_notifies_the_organizer():
    tenant, author, member = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    events, parts = _FakeEvents([_event(tenant, author)]), _FakeParticipants()
    notifier = _FakeNotifier()
    await ConfirmParticipation(events, parts, ms, notifier, clock=lambda: _NOW).execute(
        actor_account_id=member, event_id=events._e[0].id
    )
    assert notifier.calls and notifier.calls[0][0] == [author]


class _FakeMandate:
    """Le mandat de diffusion élargie — accordé ou refusé, et on retient ce qui a été demandé."""

    def __init__(self, *, granted=True):
        self.granted = granted
        self.asked: list[str] = []

    async def ensure_church_wide(self, *, actor_account_id, tenant_id, permission):
        self.asked.append(permission.value)
        if not self.granted:
            from app.contexts.groups.domain.errors import UnauthorizedGroupActionError

            raise UnauthorizedGroupActionError("Pas de mandat.", details={})


async def test_publishing_a_church_event_broadcasts_to_the_church():
    tenant, author, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(author, tenant)])
    audience = _FakeAudience(members=[author, m1, m2])
    notifier = _FakeNotifier()
    cmd = PublishEvent(
        _FakeEvents(), ms, _FakeBusiness(), _FakeMandate(), audience, notifier,
        clock=lambda: _NOW,
    )
    await cmd.execute(
        actor_account_id=author, tenant_id=tenant,
        category=EventCategory.VIGIL, title="Veillée", starts_at=_SOON,
    )
    assert notifier.calls and sorted(notifier.calls[0][0]) == sorted([m1, m2])  # pas l'auteur


async def test_publishing_a_denomination_event_broadcasts_to_the_denomination():
    tenant, author, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(author, tenant)])
    audience = _FakeAudience(denomination="AD", peers=[tenant, uuid4()], members=[author, m1, m2])
    notifier = _FakeNotifier()
    cmd = PublishEvent(
        _FakeEvents(), ms, _FakeBusiness(is_business=True), _FakeMandate(), audience,
        notifier, clock=lambda: _NOW,
    )
    await cmd.execute(
        actor_account_id=author, tenant_id=tenant,
        category=EventCategory.CONVENTION, title="Convention", starts_at=_SOON,
        scope=EventScope.DENOMINATION,
    )
    assert notifier.calls and sorted(notifier.calls[0][0]) == sorted([m1, m2])


async def test_publishing_a_platform_event_enqueues_the_broadcast():
    tenant, author, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(author, tenant)])
    audience = _FakeAudience(all_tenants=[tenant, uuid4()], members=[author, m1, m2])
    notifier, scheduler = _FakeNotifier(), _FakeScheduler()
    cmd = PublishEvent(
        _FakeEvents(), ms, _FakeBusiness(is_business=True), _FakeMandate(), audience,
        notifier, scheduler, clock=lambda: _NOW,
    )
    await cmd.execute(
        actor_account_id=author, tenant_id=tenant,
        category=EventCategory.CONCERT, title="Grand concert Dorea", starts_at=_SOON,
        scope=EventScope.PLATFORM,
    )
    # audience trop large → enqueue (outbox), pas d'envoi synchrone
    assert notifier.calls == []
    assert scheduler.calls
    targets, _notif, at = scheduler.calls[0]
    assert sorted(targets) == sorted([m1, m2]) and at == _NOW  # pas l'auteur


# --- Le rayonnement : vues (par dénomination), portée, tableau de bord organisateur ---


async def test_recording_a_view_is_distinct_per_viewer():
    tenant, member, author = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    events, views = _FakeEvents([_event(tenant, author)]), _FakeViews()
    e = events._e[0]
    rec = RecordEventView(events, views, ms, _FakeAudience("AD Yopougon", 120), clock=lambda: _NOW)
    await rec.execute(actor_account_id=member, event_id=e.id)
    await rec.execute(actor_account_id=member, event_id=e.id)  # même spectateur, pas 2 vues
    assert await views.count_by_event(e.id) == 1


async def test_views_are_split_by_denomination():
    tenant, m1, m2, author = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(m1, tenant), _member(m2, tenant)])
    events, views = _FakeEvents([_event(tenant, author)]), _FakeViews()
    e = events._e[0]
    rec = RecordEventView(events, views, ms, _FakeAudience("AD Yopougon", 120), clock=lambda: _NOW)
    await rec.execute(actor_account_id=m1, event_id=e.id)
    await rec.execute(actor_account_id=m2, event_id=e.id)
    assert await views.counts_by_denomination(e.id) == {"AD Yopougon": 2}


async def test_a_non_member_cannot_record_a_view():
    tenant, author = uuid4(), uuid4()
    e = _event(tenant, author)
    rec = RecordEventView(
        _FakeEvents([e]), _FakeViews(), _FakeMemberships(), _FakeAudience(), clock=lambda: _NOW
    )
    with pytest.raises(NotAChurchMemberError):
        await rec.execute(actor_account_id=uuid4(), event_id=e.id)


async def test_organizer_sees_the_reach_dashboard():
    tenant, author, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(m1, tenant), _member(m2, tenant)])
    events = _FakeEvents([_event(tenant, author)])
    e = events._e[0]
    views, parts, reacts = _FakeViews(), _FakeParticipants(), _FakeReactions()
    audience = _FakeAudience("AD Yopougon", 120)
    rec = RecordEventView(events, views, ms, audience, clock=lambda: _NOW)
    await rec.execute(actor_account_id=m1, event_id=e.id)
    await rec.execute(actor_account_id=m2, event_id=e.id)
    await ReactToEvent(events, reacts, ms, clock=lambda: _NOW).execute(
        actor_account_id=m1, event_id=e.id, kind=EventReaction.INTERESTED
    )
    await ConfirmParticipation(events, parts, ms, clock=lambda: _NOW).execute(
        actor_account_id=m2, event_id=e.id
    )
    stats = await GetEventStats(events, views, parts, reacts, audience).execute(
        actor_account_id=author, event_id=e.id
    )
    assert stats.reach == 120  # la portée = les membres de l'église
    assert stats.views_total == 2 and stats.views_by_denomination == {"AD Yopougon": 2}
    assert stats.interested_count == 1 and stats.confirmed_count == 1


async def test_a_non_organizer_cannot_see_the_stats():
    tenant, author = uuid4(), uuid4()
    events = _FakeEvents([_event(tenant, author)])
    stats = GetEventStats(
        events, _FakeViews(), _FakeParticipants(), _FakeReactions(), _FakeAudience()
    )
    with pytest.raises(NotEventAuthorError):
        await stats.execute(actor_account_id=uuid4(), event_id=events._e[0].id)


# --- Le mandat : deux clés, pas une ------------------------------------------------------


async def test_a_business_member_without_a_mandate_does_not_broadcast_wider():
    """Le compte Business est le droit de **payer**, pas celui de parler au nom d'une église.

    Sans cette seconde clé, n'importe quel membre actif diffusait à toute sa dénomination en
    enregistrant une carte : la légitimité invoquée était institutionnelle, le porteur du droit
    individuel."""
    tenant, member = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    mandate = _FakeMandate(granted=False)
    cmd = PublishEvent(
        _FakeEvents(), ms, _FakeBusiness(is_business=True), mandate, clock=lambda: _NOW
    )

    with pytest.raises(WiderReachRequiresMandateError):
        await cmd.execute(
            actor_account_id=member, tenant_id=tenant,
            category=EventCategory.CONVENTION, title="Convention", starts_at=_SOON,
            scope=EventScope.DENOMINATION,
        )
    assert mandate.asked == ["broadcast_wider"]


async def test_a_mandated_pastor_without_a_card_does_not_broadcast_either():
    """Le pendant : le mandat n'est pas un moyen de paiement.

    Et le refus est **distinct** — un refus de mandat n'est pas un refus de paiement. Renvoyer vers
    une page d'abonnement quelqu'un qui a payé ne lui apprendrait rien."""
    tenant, pastor = uuid4(), uuid4()
    ms = _FakeMemberships([_member(pastor, tenant)])
    cmd = PublishEvent(
        _FakeEvents(), ms, _FakeBusiness(is_business=False), _FakeMandate(), clock=lambda: _NOW
    )

    with pytest.raises(WiderReachRequiresBusinessError):
        await cmd.execute(
            actor_account_id=pastor, tenant_id=tenant,
            category=EventCategory.CONVENTION, title="Convention", starts_at=_SOON,
            scope=EventScope.DENOMINATION,
        )


async def test_the_two_keys_together_publish():
    tenant, pastor = uuid4(), uuid4()
    ms = _FakeMemberships([_member(pastor, tenant)])
    cmd = PublishEvent(
        _FakeEvents(), ms, _FakeBusiness(is_business=True), _FakeMandate(), clock=lambda: _NOW
    )

    dto = await cmd.execute(
        actor_account_id=pastor, tenant_id=tenant,
        category=EventCategory.CONVENTION, title="Convention régionale", starts_at=_SOON,
        scope=EventScope.DENOMINATION,
    )

    assert dto.scope == "denomination"


async def test_the_church_scope_needs_neither_card_nor_mandate():
    """L'église reste gratuite et ouverte : c'est chez soi qu'on parle sans rien demander."""
    tenant, member = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    mandate = _FakeMandate(granted=False)
    cmd = PublishEvent(
        _FakeEvents(), ms, _FakeBusiness(is_business=False), mandate, clock=lambda: _NOW
    )

    dto = await cmd.execute(
        actor_account_id=member, tenant_id=tenant,
        category=EventCategory.VIGIL, title="Veillée", starts_at=_SOON,
    )

    assert dto.scope == "church"
    assert mandate.asked == []  # on ne demande rien pour parler chez soi


# --- Le voisinage : la portée géographique -----------------------------------------------
#
# Les trois portées d'origine sont **institutionnelles** (mon église, mon corps, la plateforme).
# Celle-ci est **géographique**, et elle manquait : pour un repas de quartier à Yopougon, la seule
# portée qui franchissait la dénomination touchait 11 272 personnes pour en viser 662.

_YOPOUGON = (5.3364, -4.0761)
_YOPOUGON_BIS = (5.3450, -4.0700)  # ~1 km — la même commune, une autre dénomination
_COCODY = (5.3600, -3.9800)  # ~11 km — l'autre bout d'Abidjan
_BOUAKE = (7.6900, -5.0300)  # ~300 km


def _nearby(events, memberships, *, audience=None, mandate=None, notifier=None):
    return PublishEvent(
        events, memberships, _FakeBusiness(False), mandate, audience, notifier,
        _FakeScheduler(), clock=lambda: _NOW,
    )


async def test_a_neighbourhood_event_needs_a_place():
    """« Autour » exige un « ici ». Sans coordonnées, la portée ne désignerait aucune église —
    et l'auteur croirait rayonner."""
    tenant, yao = uuid4(), uuid4()
    publier = _nearby(_FakeEvents(), _FakeMemberships([_member(yao, tenant)]))

    with pytest.raises(InvalidEventError):
        await publier.execute(
            actor_account_id=yao, tenant_id=tenant, category=EventCategory.OUTING,
            title="HozanaBouf", starts_at=_SOON, scope=EventScope.NEARBY,
        )


async def test_the_neighbourhood_costs_nothing_and_asks_no_mandate():
    """Un membre ordinaire, sans compte Business et sans mandat, atteint son quartier.

    C'est le geste que les trois portées institutionnelles rendaient impossible : pour Yopougon
    il fallait `PLATFORM` — dix-sept fois trop large, et un pasteur qui a raison de refuser."""
    tenant, yao = uuid4(), uuid4()
    mandat = _FakeMandate(granted=False)  # même refusé, il ne doit pas être consulté
    publier = _nearby(
        _FakeEvents(), _FakeMemberships([_member(yao, tenant)]), mandate=mandat
    )

    dto = await publier.execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.OUTING,
        title="HozanaBouf", starts_at=_SOON, scope=EventScope.NEARBY,
        latitude=_YOPOUGON[0], longitude=_YOPOUGON[1],
    )

    assert dto.scope == "nearby"
    assert mandat.asked == []  # aucun mandat demandé pour parler à son quartier


async def test_the_neighbourhood_wakes_no_phone_outside_my_church():
    """**Rayonner et déranger sont deux choses différentes.**

    C'est ce qui permet à cette portée d'être gratuite *et* sans mandat : un membre ordinaire ne
    peut pas faire sonner six cents téléphones dans des églises qui ne sont pas la sienne. Les
    voisins la verront en ouvrant Dorea — un seul envoi, celui de son église."""
    tenant, voisine, yao = uuid4(), uuid4(), uuid4()
    notifier = _FakeNotifier()
    audience = _FakeAudience(
        members=[yao, uuid4(), uuid4()],
        locations={tenant: _YOPOUGON, voisine: _YOPOUGON_BIS},
    )
    publier = _nearby(
        _FakeEvents(), _FakeMemberships([_member(yao, tenant)]),
        audience=audience, notifier=notifier,
    )

    await publier.execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.OUTING,
        title="HozanaBouf", starts_at=_SOON, scope=EventScope.NEARBY,
        latitude=_YOPOUGON[0], longitude=_YOPOUGON[1],
    )

    assert len(notifier.calls) == 1  # une seule diffusion : celle de l'église de l'auteur
    assert yao not in notifier.calls[0][0]


def test_the_radius_is_the_products_decision_not_the_publishers():
    """**Le point de sûreté de cette portée.**

    Un rayon choisi à la publication serait une porte dérobée : « autour de moi, dans 20 000 km »
    atteindrait toute la plateforme sans compte Business ni mandat. Le publicateur dit *où* a lieu
    son événement ; le produit dit *jusqu'où* « autour » veut dire quelque chose."""
    import inspect

    params = inspect.signature(PublishEvent.execute).parameters
    assert not any("radius" in p or "rayon" in p for p in params)


def test_what_counts_as_the_neighbourhood():
    """Un kilomètre, c'est le quartier ; onze, c'est déjà l'autre bout d'Abidjan."""
    from app.contexts.events.domain.aggregates import NEARBY_RADIUS_KM
    from app.contexts.events.domain.geo import distance_km

    assert distance_km(*_YOPOUGON, *_YOPOUGON_BIS) <= NEARBY_RADIUS_KM
    assert distance_km(*_YOPOUGON, *_COCODY) > NEARBY_RADIUS_KM
    assert distance_km(*_YOPOUGON, *_BOUAKE) > 250


async def test_the_neighbours_see_it_without_being_of_my_denomination():
    """Le fond du cas : Shalom est CMA, Hozana est AD-CI, et elles sont à trois rues."""
    hozana, shalom, yao, awa = uuid4(), uuid4(), uuid4(), uuid4()
    events = _FakeEvents()
    audience = _FakeAudience(
        denomination="CMA",  # celle de Shalom — sans rapport avec l'événement
        locations={hozana: _YOPOUGON, shalom: _YOPOUGON_BIS},
    )
    memberships = _FakeMemberships([_member(yao, hozana), _member(awa, shalom)])
    dto = await _nearby(events, memberships).execute(
        actor_account_id=yao, tenant_id=hozana, category=EventCategory.OUTING,
        title="HozanaBouf", starts_at=_SOON, scope=EventScope.NEARBY,
        latitude=_YOPOUGON[0], longitude=_YOPOUGON[1],
    )

    fil = await ListVisibleEvents(
        events, _FakeParticipants(), _FakeReactions(), audience, memberships
    ).execute(tenant_id=shalom, viewer_account_id=awa)

    assert [e.id for e in fil] == [dto.id]


async def test_a_church_out_of_range_never_sees_it():
    hozana, bouake, yao, kouassi = uuid4(), uuid4(), uuid4(), uuid4()
    events = _FakeEvents()
    audience = _FakeAudience(locations={hozana: _YOPOUGON, bouake: _BOUAKE})
    memberships = _FakeMemberships([_member(yao, hozana), _member(kouassi, bouake)])
    await _nearby(events, memberships).execute(
        actor_account_id=yao, tenant_id=hozana, category=EventCategory.OUTING,
        title="HozanaBouf", starts_at=_SOON, scope=EventScope.NEARBY,
        latitude=_YOPOUGON[0], longitude=_YOPOUGON[1],
    )

    fil = await ListVisibleEvents(
        events, _FakeParticipants(), _FakeReactions(), audience, memberships
    ).execute(tenant_id=bouake, viewer_account_id=kouassi)

    assert fil == []


async def test_opening_a_neighbourhood_event_is_judged_on_distance_not_denomination():
    """Le `else` de la visibilité valait « dénomination » tant qu'il n'existait que trois portées.

    Sans cette branche, un événement de voisinage aurait été jugé sur la dénomination de son
    auteur — donc invisible pour précisément ceux qu'il vise."""
    hozana, shalom, yao, awa = uuid4(), uuid4(), uuid4(), uuid4()
    events = _FakeEvents()
    audience = _FakeAudience(
        denomination="AD-CI",
        peers=[hozana],  # Shalom n'en fait PAS partie
        locations={hozana: _YOPOUGON, shalom: _YOPOUGON_BIS},
    )
    memberships = _FakeMemberships([_member(yao, hozana), _member(awa, shalom)])
    dto = await _nearby(events, memberships).execute(
        actor_account_id=yao, tenant_id=hozana, category=EventCategory.OUTING,
        title="HozanaBouf", starts_at=_SOON, scope=EventScope.NEARBY,
        latitude=_YOPOUGON[0], longitude=_YOPOUGON[1],
    )

    vu = await GetEvent(
        events, _FakeParticipants(), _FakeReactions(), audience, memberships
    ).execute(event_id=dto.id, viewer_account_id=awa)

    assert vu.id == dto.id


async def test_the_reach_follows_the_scope():
    """**Un taux dont le dénominateur est faux est pire qu'une absence de taux : il rassure.**

    `reach` ne comptait que l'église de l'auteur, quelle que soit la portée — un événement de
    voisinage aurait affiché « 40 vues sur 42 » en en atteignant 662."""
    hozana, shalom, yao = uuid4(), uuid4(), uuid4()
    voisins = [uuid4() for _ in range(200)]
    events = _FakeEvents()
    audience = _FakeAudience(
        member_count=42,  # l'église de l'auteur seule
        members=[yao, *voisins],  # ce que rendent les églises à portée
        locations={hozana: _YOPOUGON, shalom: _YOPOUGON_BIS},
    )
    memberships = _FakeMemberships([_member(yao, hozana)])
    dto = await _nearby(events, memberships).execute(
        actor_account_id=yao, tenant_id=hozana, category=EventCategory.OUTING,
        title="HozanaBouf", starts_at=_SOON, scope=EventScope.NEARBY,
        latitude=_YOPOUGON[0], longitude=_YOPOUGON[1],
    )

    stats = await GetEventStats(
        events, _FakeViews(), _FakeParticipants(), _FakeReactions(), audience
    ).execute(actor_account_id=yao, event_id=dto.id)

    assert stats.reach == 201  # les voisins, pas les 42 de Hozana


# --- La période : un début, une fin, et ce qui en découle --------------------------------


def _dated(tenant, author, *, jours, heures=0, fin=None):
    return Event.publish(
        id=uuid4(), tenant_id=tenant, author_account_id=author,
        category=EventCategory.OUTING, title=f"J{jours:+d}",
        starts_at=_NOW + timedelta(days=jours, hours=heures),
        ends_at=fin, now=_NOW,
    )


async def test_the_feed_opened_on_a_finished_event():
    """**Le tri existait, le filtre non** — et comme l'ordre est croissant, le plus ancien
    ouvrait le fil.

    Un membre voyait en premier une sortie de janvier terminée depuis sept mois, et devait faire
    défiler pour trouver ce qui a lieu demain. Le commentaire du code disait déjà « les prochains
    d'abord » : il décrivait une intention, pas le comportement."""
    tenant, author = uuid4(), uuid4()
    events = _FakeEvents([
        _dated(tenant, author, jours=-200),
        _dated(tenant, author, jours=-7),
        _dated(tenant, author, jours=1),
        _dated(tenant, author, jours=40),
    ])

    fil = await ListChurchEvents(
        events, _FakeParticipants(), _FakeReactions(), clock=lambda: _NOW
    ).execute(tenant_id=tenant, viewer_account_id=uuid4())

    assert [e.title for e in fil] == ["J+1", "J+40"]


async def test_an_event_lasts_until_the_end_of_its_day():
    """Prendre `starts_at` seul ferait disparaître du fil un repas de 18 h à 18 h 01, pendant que
    les gens s'y rendent. Une journée est la plus petite unité qu'un événement sans heure de fin
    puisse honnêtement revendiquer."""
    # `_NOW` est un minuit : on se place en milieu de journée pour que « ce soir » ait un sens.
    midi = _NOW + timedelta(hours=12)
    ce_soir = Event.publish(
        id=uuid4(), tenant_id=uuid4(), author_account_id=uuid4(),
        category=EventCategory.OUTING, title="Repas de ce soir",
        starts_at=midi + timedelta(hours=6), ends_at=None, now=_NOW,
    )

    assert ce_soir.is_over(midi + timedelta(hours=7)) is False  # commencé, encore en cours
    assert ce_soir.is_over(midi + timedelta(days=1)) is True  # le lendemain, terminé


async def test_ends_at_finally_serves_something():
    """`ends_at` était écrit, validé (`ends_at < starts_at` refusé), et lu nulle part."""
    tenant, author = uuid4(), uuid4()
    court = _dated(tenant, author, jours=0, heures=-4, fin=_NOW - timedelta(hours=1))
    long = _dated(tenant, author, jours=0, heures=-4, fin=_NOW + timedelta(days=3))

    assert court.is_over(_NOW) is True   # fini il y a une heure
    assert long.is_over(_NOW) is False   # une convention de trois jours court encore


async def test_the_one_who_committed_is_reminded():
    """**C'était le seul engagement du produit qui ne revenait jamais vers celui qui l'avait
    pris.**

    L'organisateur était prévenu à chaque confirmation ; le participant, jamais — sauf pour lui
    dire que ça n'aurait pas lieu. On ne lui parlait que pour annuler."""
    tenant, author, awa = uuid4(), uuid4(), uuid4()
    events = _FakeEvents([_dated(tenant, author, jours=10)])
    scheduler = _FakeScheduler()

    await ConfirmParticipation(
        events, _FakeParticipants(), _FakeMemberships([_member(awa, tenant)]),
        _FakeNotifier(), scheduler, clock=lambda: _NOW,
    ).execute(actor_account_id=awa, event_id=events._e[0].id)

    (cibles, notification, quand), = scheduler.calls
    assert cibles == [awa]
    assert notification.title == "C'est demain"
    assert quand == events._e[0].starts_at - timedelta(hours=REMINDER_LEAD_HOURS)


async def test_confirming_at_the_last_minute_schedules_nothing():
    """On confirme parfois le matin même : un rappel daté d'hier partirait immédiatement et
    ferait doublon avec le geste qu'on vient de poser."""
    tenant, author, awa = uuid4(), uuid4(), uuid4()
    events = _FakeEvents([_dated(tenant, author, jours=0, heures=3)])  # dans trois heures
    scheduler = _FakeScheduler()

    await ConfirmParticipation(
        events, _FakeParticipants(), _FakeMemberships([_member(awa, tenant)]),
        _FakeNotifier(), scheduler, clock=lambda: _NOW,
    ).execute(actor_account_id=awa, event_id=events._e[0].id)

    assert scheduler.calls == []


async def test_confirming_twice_does_not_remind_twice():
    """La confirmation est idempotente ; le rappel doit l'être avec elle."""
    tenant, author, awa = uuid4(), uuid4(), uuid4()
    events = _FakeEvents([_dated(tenant, author, jours=10)])
    scheduler = _FakeScheduler()
    confirmer = ConfirmParticipation(
        events, _FakeParticipants(), _FakeMemberships([_member(awa, tenant)]),
        _FakeNotifier(), scheduler, clock=lambda: _NOW,
    )

    await confirmer.execute(actor_account_id=awa, event_id=events._e[0].id)
    await confirmer.execute(actor_account_id=awa, event_id=events._e[0].id)

    assert len(scheduler.calls) == 1


async def test_a_member_can_publish_a_shared_meal():
    """« Agape » est le mot de l'Église pour un repas fraternel, en français comme en anglais.

    Il dit plus précisément que « repas » : on mange ensemble parce qu'on est frères, pas au
    restaurant. Le catalogue disait le formel — convention, séminaire, formation, culte — et rien
    du convivial, alors que c'est ce qu'un membre ordinaire publie le plus souvent."""
    tenant, yao = uuid4(), uuid4()
    publier = PublishEvent(
        _FakeEvents(), _FakeMemberships([_member(yao, tenant)]), _FakeBusiness(False),
        clock=lambda: _NOW,
    )

    dto = await publier.execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON,
    )

    assert dto.category == "agape"


# --- La cadence de publication, et sa contrepartie ---------------------------------------
#
# Publier fait sonner tous les téléphones de l'église. C'était le seul geste du produit qu'un
# compte sans aucun rôle pouvait répéter sans limite : cinq publications d'affilée, 205
# notifications en quelques secondes. La sanction n'est pas la désinstallation — c'est la coupure
# des notifications, après quoi le canal de veille ne passe plus non plus.


def _publisher(events, memberships, *, notifier=None, at=None):
    horloge = at or (lambda: _NOW)
    return PublishEvent(
        events, memberships, _FakeBusiness(False), None, _FakeAudience(members=[uuid4()]),
        notifier or _FakeNotifier(), _FakeScheduler(), clock=horloge,
    )


async def test_one_event_a_week_and_the_refusal_says_when():
    """**Un refus sans échéance se lit comme une panne, et on réessaie.**

    Le message porte la date à laquelle on pourra publier de nouveau — et rappelle la sortie de
    secours : le lien de l'événement en cours, lui, se partage sans limite."""
    tenant, yao = uuid4(), uuid4()
    events = _FakeEvents()
    publier = _publisher(events, _FakeMemberships([_member(yao, tenant)]))

    await publier.execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON,
    )

    with pytest.raises(PublicationCadenceError) as refus:
        await publier.execute(
            actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
            title="HozanaBouf 2", starts_at=_SOON,
        )

    assert "partagez le lien" in str(refus.value)
    assert refus.value.details["next_publication_at"].startswith("2026-01-08")


async def test_five_publications_in_a_row_send_one_notification():
    """La mesure qui avait révélé le trou : 5 publications, 205 notifications individuelles."""
    tenant, yao = uuid4(), uuid4()
    events, notifier = _FakeEvents(), _FakeNotifier()
    publier = _publisher(events, _FakeMemberships([_member(yao, tenant)]), notifier=notifier)

    publiés = 0
    for i in range(5):
        try:
            await publier.execute(
                actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
                title=f"HozanaBouf {i}", starts_at=_SOON,
            )
            publiés += 1
        except PublicationCadenceError:
            pass

    assert publiés == 1
    assert len(notifier.calls) == 1


async def test_cancelling_does_not_reset_the_week():
    """Sans cette règle, la cadence s'annulerait elle-même : publier, annuler, republier ferait
    sonner l'église autant de fois qu'on veut."""
    tenant, yao = uuid4(), uuid4()
    events = _FakeEvents()
    publier = _publisher(events, _FakeMemberships([_member(yao, tenant)]))
    dto = await publier.execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON,
    )
    await CancelEvent(events, clock=lambda: _NOW).execute(
        actor_account_id=yao, event_id=dto.id
    )

    with pytest.raises(PublicationCadenceError):
        await publier.execute(
            actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
            title="Encore", starts_at=_SOON,
        )


async def test_the_week_after_the_door_reopens():
    tenant, yao = uuid4(), uuid4()
    events = _FakeEvents()
    await _publisher(events, _FakeMemberships([_member(yao, tenant)])).execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON,
    )

    semaine_suivante = _NOW + timedelta(days=PUBLICATION_COOLDOWN_DAYS)
    dto = await _publisher(
        events, _FakeMemberships([_member(yao, tenant)]), at=lambda: semaine_suivante
    ).execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf 2", starts_at=_SOON + timedelta(days=30),
    )

    assert dto.status == "published"


async def test_the_cadence_is_personal_not_collective():
    """Elle borne une personne, pas l'église : Awa publie même si Yao vient de le faire."""
    tenant, yao, awa = uuid4(), uuid4(), uuid4()
    events = _FakeEvents()
    memberships = _FakeMemberships([_member(yao, tenant), _member(awa, tenant)])
    await _publisher(events, memberships).execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON,
    )

    dto = await _publisher(events, memberships).execute(
        actor_account_id=awa, tenant_id=tenant, category=EventCategory.CONCERT,
        title="Concert de louange", starts_at=_SOON,
    )

    assert dto.status == "published"


# --- Le lien externe : ce qui est rationné est la notification, jamais la diffusion -------


async def test_the_link_opens_without_an_account():
    """La contrepartie de la cadence. Sans elle, celui qui organise un repas ne pourrait plus
    inviter personne pendant sept jours."""
    tenant, yao = uuid4(), uuid4()
    events = _FakeEvents()
    dto = await _publisher(events, _FakeMemberships([_member(yao, tenant)])).execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON, place_label="Cour du temple, Yopougon",
        description="Chacun apporte un plat.",
    )

    carte = await GetPublicEvent(events).execute(event_id=dto.id)

    assert carte.title == "HozanaBouf"
    assert carte.place_label == "Cour du temple, Yopougon"


async def test_the_public_card_names_nobody_and_counts_nothing():
    """**La moitié de sa conception est ce qu'elle ne montre pas.**

    Ni organisateur, ni participants, ni compte : un événement est un *happening*, pas un
    annuaire. Et aucun nombre — l'invariant anti-compteur ne s'arrête pas à la frontière du
    produit ; « 24 intéressés » sur une page publique serait un score, exactement comme dedans."""
    from app.contexts.events.interface.schemas import PublicEventView

    champs = set(PublicEventView.model_fields)

    assert not any(
        mot in champ
        for champ in champs
        for mot in ("account", "author", "participant", "count", "reaction", "view")
    ), champs


async def test_a_cancelled_event_has_no_card():
    """Un lien qui survit à l'annulation fait déplacer quelqu'un pour rien."""
    tenant, yao = uuid4(), uuid4()
    events = _FakeEvents()
    dto = await _publisher(events, _FakeMemberships([_member(yao, tenant)])).execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON,
    )
    await CancelEvent(events, clock=lambda: _NOW).execute(
        actor_account_id=yao, event_id=dto.id
    )

    with pytest.raises(EventCancelledError):
        await GetPublicEvent(events).execute(event_id=dto.id)


async def test_a_taken_down_event_stops_circulating_outside_too():
    """Sinon la modération ne ferait disparaître l'événement que pour les membres, pendant qu'il
    continue de circuler librement à l'extérieur."""
    tenant, yao = uuid4(), uuid4()
    events = _FakeEvents()
    dto = await _publisher(events, _FakeMemberships([_member(yao, tenant)])).execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON,
    )
    await TakeDownEvent(events, clock=lambda: _NOW).execute(event_id=dto.id)

    with pytest.raises(EventTakenDownError):
        await GetPublicEvent(events).execute(event_id=dto.id)


def test_there_is_no_way_to_relaunch_an_event():
    """**Tant qu'un événement est en cours, on ne peut pas le relancer.**

    Il n'existe aucun bouton « faire remonter », et c'est la forme la plus solide de la règle :
    ce qui n'existe pas ne s'abuse pas. Ce test lit le module et refuse qu'on l'ajoute — un
    `relaunch`, un `boost`, un `bump` ou un renvoi de notification sur un événement déjà publié.

    La seule notification qui repart après la publication est l'annulation, et elle dit le
    contraire d'un rappel : elle décommande."""
    import pathlib

    from app.contexts.events.application import commands

    interdits = ("relaunch", "boost", "bump", "republish", "renotify")
    for source in pathlib.Path(commands.__file__).parent.glob("*.py"):
        texte = source.read_text(encoding="utf-8").lower()
        for mot in interdits:
            assert f"def {mot}" not in texte, f"{source.name} : {mot}"


# --- La couverture : une image, un texte, ou trente secondes de vidéo --------------------


async def _publish_cover(cover):
    tenant, yao = uuid4(), uuid4()
    return await PublishEvent(
        _FakeEvents(), _FakeMemberships([_member(yao, tenant)]), _FakeBusiness(False),
        clock=lambda: _NOW,
    ).execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON, cover=cover,
    )


async def test_an_event_wears_one_face():
    """Un événement n'a pas trois visages. Porter à la fois une image et un texte obligerait
    chaque client à trancher lequel afficher — et deux clients trancheraient différemment : la
    même soirée n'aurait pas la même tête sur deux téléphones."""
    dto = await _publish_cover(EventCover(kind=CoverKind.IMAGE, url="https://cdn/affiche.jpg"))

    assert dto.cover_kind == "image"
    assert dto.cover_url == "https://cdn/affiche.jpg"
    assert dto.cover_text is None


async def test_a_text_cover_is_a_first_class_face_not_a_fallback():
    """`IMAGE` et `VIDEO` supposent qu'on a de quoi photographier ou filmer. `TEXT` ne suppose
    rien : une phrase sur un aplat de couleur, et l'événement a un visage.

    C'est la forme qui rend le produit utilisable par celui qui organise un repas depuis un
    téléphone à faible connexion — et c'est pourquoi elle est un membre de l'enum, pas un repli
    silencieux du client."""
    dto = await _publish_cover(
        EventCover(kind=CoverKind.TEXT, text="Chacun apporte un plat. On mange à 19h.")
    )

    assert dto.cover_kind == "text"
    assert dto.cover_url is None


async def test_an_event_without_a_cover_is_legitimate():
    """Le client affiche alors le titre. Exiger une couverture ferait renoncer celui qui n'a
    ni photo ni idée de phrase — c'est-à-dire celui qu'on veut le plus voir publier."""
    dto = await _publish_cover(None)

    assert dto.cover_kind is None


@pytest.mark.parametrize(
    "cover",
    [
        pytest.param({"kind": CoverKind.TEXT}, id="un texte sans texte"),
        pytest.param({"kind": CoverKind.TEXT, "text": "   "}, id="un texte vide"),
        pytest.param(
            {"kind": CoverKind.TEXT, "text": "ok", "url": "https://cdn/x.jpg"},
            id="un texte qui porte aussi un fichier",
        ),
        pytest.param({"kind": CoverKind.IMAGE}, id="une image sans fichier"),
        pytest.param({"kind": CoverKind.VIDEO}, id="une video sans fichier"),
        pytest.param(
            {"kind": CoverKind.IMAGE, "url": "https://cdn/x.jpg", "text": "et un texte"},
            id="une image qui porte aussi un texte",
        ),
        pytest.param(
            {"kind": CoverKind.TEXT, "text": "x" * (MAX_COVER_TEXT + 1)},
            id="une phrase qui n'en est plus une",
        ),
    ],
)
def test_a_cover_that_says_two_things_is_refused(cover):
    """La cohérence est portée par l'objet lui-même : il n'existe pas de couverture mal formée
    quelque part dans le système, seulement des tentatives refusées à la construction."""
    with pytest.raises(InvalidEventError):
        EventCover(**cover)


async def test_the_cover_travels_to_the_public_card():
    """C'est là qu'elle sert le plus : la carte qu'on ouvre depuis un lien WhatsApp, sans compte."""
    from app.contexts.events.interface.schemas import PublicEventView

    tenant, yao = uuid4(), uuid4()
    events = _FakeEvents()
    dto = await PublishEvent(
        events, _FakeMemberships([_member(yao, tenant)]), _FakeBusiness(False),
        clock=lambda: _NOW,
    ).execute(
        actor_account_id=yao, tenant_id=tenant, category=EventCategory.AGAPE,
        title="HozanaBouf", starts_at=_SOON,
        cover=EventCover(kind=CoverKind.VIDEO, url="https://cdn/teaser.mp4"),
    )

    carte = PublicEventView.of(await GetPublicEvent(events).execute(event_id=dto.id))

    assert carte.cover.kind == "video"
    assert carte.cover.url == "https://cdn/teaser.mp4"


def test_the_thirty_seconds_are_not_enforced_here():
    """**La durée se mesure à l'upload, pas à la publication.**

    Ici on ne voit qu'une URL : refuser sur une durée déclarée dans la requête reviendrait à
    faire confiance au client. Elle est lue dans l'en-tête du MP4 au moment où les octets
    passent — c'est le seul endroit où on les a."""
    import inspect

    from app.contexts.events.domain import aggregates

    assert "duration" not in inspect.getsource(aggregates.EventCover)
