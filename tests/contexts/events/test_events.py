"""Module Event (E-0, portée église) : publier, réagir, confirmer sa présence.

Tout membre publie pour son église (au-delà = compte Business, à venir) ; réactions comptées ;
liste des présents réservée à l'organisateur.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.events.application.commands.engage_event import (
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
    ListParticipants,
    ListVisibleEvents,
)
from app.contexts.events.domain.aggregates import Event
from app.contexts.events.domain.enums import EventCategory, EventReaction, EventScope
from app.contexts.events.domain.errors import (
    EventCancelledError,
    EventTakenDownError,
    InvalidEventError,
    NotAChurchMemberError,
    NotEventAuthorError,
    WiderReachRequiresBusinessError,
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
        self, denomination=None, member_count=0, peers=(), members=(), all_tenants=()
    ):
        self._denomination = denomination
        self._member_count = member_count
        self._peers = list(peers)
        self._members = list(members)
        self._all_tenants = list(all_tenants)

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
    assert dto.participant_count == 1 and dto.i_confirmed is True


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


async def test_publishing_a_church_event_broadcasts_to_the_church():
    tenant, author, m1, m2 = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(author, tenant)])
    audience = _FakeAudience(members=[author, m1, m2])
    notifier = _FakeNotifier()
    cmd = PublishEvent(_FakeEvents(), ms, _FakeBusiness(), audience, notifier, clock=lambda: _NOW)
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
        _FakeEvents(), ms, _FakeBusiness(is_business=True), audience, notifier, clock=lambda: _NOW
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
        _FakeEvents(), ms, _FakeBusiness(is_business=True), audience, notifier, scheduler,
        clock=lambda: _NOW,
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
