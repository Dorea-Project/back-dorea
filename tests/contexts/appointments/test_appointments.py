"""Module Rendez-vous — l'agenda du pasteur, gardé par la secrétaire.

Le membre demande ; la secrétaire (MANAGE_APPOINTMENTS) confirme/décline/marque honoré ; le
demandeur annule. Confidentialité + « l'humain décide » (un déclin porte un mot doux).
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.appointments.application.commands.availability import (
    AddAvailabilityRule,
    DeactivateAvailabilityRule,
)
from app.contexts.appointments.application.commands.book_slot import BookSlot
from app.contexts.appointments.application.commands.manage import (
    CloseAppointment,
    CompleteAppointment,
    ConfirmAppointment,
    DeclineAppointment,
    OpenAppointment,
)
from app.contexts.appointments.application.commands.request import (
    CancelAppointment,
    RequestAppointment,
)
from app.contexts.appointments.application.queries.list_appointments import (
    ListMyAppointments,
    ListTenantAgenda,
)
from app.contexts.appointments.application.queries.open_slots import ListOpenSlots
from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.availability import AvailabilityRule
from app.contexts.appointments.domain.enums import AppointmentCategory, AppointmentStatus
from app.contexts.appointments.domain.errors import (
    AppointmentClosedError,
    AppointmentNotFoundError,
    AppointmentSubjectRequiredError,
    InvalidAvailabilityError,
    NotAPastorError,
    NotAppointmentRequesterError,
    RequesterIdentityRequiredError,
    RequesterNotMemberError,
    SlotNotAvailableError,
)
from app.contexts.appointments.domain.repositories import (
    AppointmentRepository,
    AvailabilityRuleRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import MembershipStatus, RoleCode
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.notifications.application.notifier import NotificationScheduler, Notifier

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_SLOT = _NOW + timedelta(days=3)


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


class _FakeAppointments(AppointmentRepository):
    def __init__(self, items=()):
        self._a = list(items)

    async def add(self, appointment):
        self._a.append(appointment)

    async def get(self, appointment_id):
        return next((a for a in self._a if a.id == appointment_id), None)

    async def save(self, appointment):
        pass  # muté en mémoire (même instance)

    async def list_by_requester(self, requester_account_id, tenant_id):
        return [
            a for a in self._a
            if a.requester_account_id == requester_account_id and a.tenant_id == tenant_id
        ]

    async def list_open_for_tenant(self, tenant_id):
        return [
            a for a in self._a
            if a.tenant_id == tenant_id
            and a.status in (AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)
        ]

    async def list_confirmed_between(self, tenant_id, from_dt, to_dt):
        return [
            a for a in self._a
            if a.tenant_id == tenant_id
            and a.status is AppointmentStatus.CONFIRMED
            and a.scheduled_at is not None
            and from_dt <= a.scheduled_at <= to_dt
        ]


class _FakeRules(AvailabilityRuleRepository):
    def __init__(self, items=()):
        self._r = list(items)

    async def add(self, rule):
        self._r.append(rule)

    async def get(self, rule_id):
        return next((r for r in self._r if r.id == rule_id), None)

    async def save(self, rule):
        pass  # muté en mémoire

    async def list_active_by_tenant(self, tenant_id):
        return [r for r in self._r if r.tenant_id == tenant_id and r.active]

    async def list_active_by_pastor(self, pastor_account_id, tenant_id):
        return [
            r for r in self._r
            if r.pastor_account_id == pastor_account_id and r.tenant_id == tenant_id and r.active
        ]


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


def _appt(tenant, *, requester=None, status=AppointmentStatus.REQUESTED) -> Appointment:
    a = Appointment.request(
        id=uuid4(), tenant_id=tenant, requester_account_id=requester or uuid4(),
        subject="Prière et conseil", category=AppointmentCategory.PRAYER, now=_NOW,
    )
    if status is AppointmentStatus.CONFIRMED:
        a.confirm(at=_SLOT, by_account_id=uuid4(), now=_NOW)
    return a


# --- Le domaine : le parcours d'une demande ---


def test_request_requires_a_subject():
    with pytest.raises(AppointmentSubjectRequiredError):
        Appointment.request(
            id=uuid4(), tenant_id=uuid4(), requester_account_id=uuid4(), subject="   ",
            category=AppointmentCategory.OTHER, now=_NOW,
        )


def test_office_opens_a_walk_in_with_just_a_name():
    keeper = uuid4()
    a = Appointment.open_at_office(
        id=uuid4(), tenant_id=uuid4(), opened_by_account_id=keeper,
        subject="Préparation de mariage", category=AppointmentCategory.MARRIAGE, now=_NOW,
        requester_name="Awa & Kofi",
    )
    assert a.requester_account_id is None and a.requester_name == "Awa & Kofi"
    assert a.category is AppointmentCategory.MARRIAGE and a.status is AppointmentStatus.REQUESTED


def test_office_open_with_a_slot_is_born_confirmed():
    keeper = uuid4()
    a = Appointment.open_at_office(
        id=uuid4(), tenant_id=uuid4(), opened_by_account_id=keeper,
        subject="Visite", category=AppointmentCategory.VISIT, now=_NOW,
        requester_name="Mme Diallo", scheduled_at=_SLOT,
    )
    assert a.status is AppointmentStatus.CONFIRMED and a.scheduled_at == _SLOT
    assert a.handled_by_account_id == keeper


def test_office_open_needs_a_requester_identity():
    with pytest.raises(RequesterIdentityRequiredError):  # ni compte ni nom
        Appointment.open_at_office(
            id=uuid4(), tenant_id=uuid4(), opened_by_account_id=uuid4(),
            subject="x", category=AppointmentCategory.OTHER, now=_NOW,
        )


def test_confirm_poses_the_slot_and_handler():
    keeper = uuid4()
    a = _appt(uuid4())
    a.confirm(at=_SLOT, by_account_id=keeper, now=_NOW)
    assert a.status is AppointmentStatus.CONFIRMED
    assert a.scheduled_at == _SLOT and a.handled_by_account_id == keeper


def test_decline_only_a_pending_request_and_carries_a_word():
    a = _appt(uuid4())
    a.decline(by_account_id=uuid4(), reason="Le pasteur est en déplacement ce mois-ci", now=_NOW)
    assert a.status is AppointmentStatus.DECLINED
    assert a.decision_note == "Le pasteur est en déplacement ce mois-ci"


def test_cannot_decline_a_confirmed_appointment():
    a = _appt(uuid4(), status=AppointmentStatus.CONFIRMED)
    with pytest.raises(AppointmentClosedError):
        a.decline(by_account_id=uuid4(), reason=None, now=_NOW)


def test_complete_only_a_confirmed_appointment():
    a = _appt(uuid4())  # requested
    with pytest.raises(AppointmentClosedError):
        a.complete(by_account_id=uuid4(), now=_NOW)
    a.confirm(at=_SLOT, by_account_id=uuid4(), now=_NOW)
    a.complete(by_account_id=uuid4(), now=_NOW)
    assert a.status is AppointmentStatus.COMPLETED


def test_cannot_cancel_a_resolved_appointment():
    a = _appt(uuid4())
    a.cancel(now=_NOW)
    assert a.status is AppointmentStatus.CANCELLED
    with pytest.raises(AppointmentClosedError):  # déjà résolu
        a.cancel(now=_NOW)


# --- Le demandeur (mobile) ---


async def test_member_requests_an_appointment():
    member, tenant = uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    cmd = RequestAppointment(_FakeAppointments(), ms, clock=lambda: _NOW)
    dto = await cmd.execute(
        actor_account_id=member, tenant_id=tenant, subject="Un temps de prière"
    )
    assert dto.status == "requested" and dto.requester_account_id == member


async def test_a_non_member_cannot_request():
    cmd = RequestAppointment(_FakeAppointments(), _FakeMemberships(), clock=lambda: _NOW)
    with pytest.raises(RequesterNotMemberError):
        await cmd.execute(actor_account_id=uuid4(), tenant_id=uuid4(), subject="x")


async def test_requester_cancels_their_own_request():
    requester, tenant = uuid4(), uuid4()
    a = _appt(tenant, requester=requester)
    cmd = CancelAppointment(_FakeAppointments([a]), clock=lambda: _NOW)
    dto = await cmd.execute(actor_account_id=requester, appointment_id=a.id)
    assert dto.status == "cancelled"


async def test_only_the_requester_can_cancel():
    a = _appt(uuid4(), requester=uuid4())
    cmd = CancelAppointment(_FakeAppointments([a]), clock=lambda: _NOW)
    with pytest.raises(NotAppointmentRequesterError):
        await cmd.execute(actor_account_id=uuid4(), appointment_id=a.id)


async def test_my_appointments_lists_only_mine():
    me, other, tenant = uuid4(), uuid4(), uuid4()
    appts = _FakeAppointments([_appt(tenant, requester=me), _appt(tenant, requester=other)])
    dtos = await ListMyAppointments(appts).execute(actor_account_id=me, tenant_id=tenant)
    assert len(dtos) == 1 and dtos[0].requester_account_id == me


# --- La secrétaire, gardienne de l'agenda (backoffice) ---


def _secretary(tenant):
    keeper = uuid4()
    ms = _FakeMemberships([_member(keeper, tenant, (RoleCode.SECRETARY, None))])
    return keeper, ms


async def test_secretary_confirms_a_slot():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    a = _appt(tenant)
    cmd = ConfirmAppointment(_FakeAppointments([a]), _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(actor_account_id=keeper, appointment_id=a.id, scheduled_at=_SLOT)
    assert dto.status == "confirmed" and dto.scheduled_at == _SLOT


async def test_an_ordinary_member_cannot_keep_the_agenda():
    tenant = uuid4()
    stranger = uuid4()
    ms = _FakeMemberships([_member(stranger, tenant)])  # aucun rôle → pas d'autorité
    a = _appt(tenant)
    cmd = ConfirmAppointment(_FakeAppointments([a]), _access(ms), clock=lambda: _NOW)
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(actor_account_id=stranger, appointment_id=a.id, scheduled_at=_SLOT)


async def test_secretary_declines_with_a_gentle_word():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    a = _appt(tenant)
    cmd = DeclineAppointment(_FakeAppointments([a]), _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(
        actor_account_id=keeper, appointment_id=a.id, reason="Voyons cela le mois prochain"
    )
    assert dto.status == "declined" and dto.decision_note == "Voyons cela le mois prochain"


async def test_secretary_marks_an_appointment_honored():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    a = _appt(tenant, status=AppointmentStatus.CONFIRMED)
    cmd = CompleteAppointment(_FakeAppointments([a]), _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(actor_account_id=keeper, appointment_id=a.id)
    assert dto.status == "completed"


async def test_confirm_unknown_appointment_is_404():
    keeper, ms = _secretary(uuid4())
    cmd = ConfirmAppointment(_FakeAppointments(), _access(ms), clock=lambda: _NOW)
    with pytest.raises(AppointmentNotFoundError):
        await cmd.execute(actor_account_id=keeper, appointment_id=uuid4(), scheduled_at=_SLOT)


async def test_the_agenda_shows_slots_to_organise_never_pending_requests():
    """Le secrétariat organise des créneaux. Il ne voit **ni** les demandes en attente, **ni**
    leur motif.

    C'est ce qui permet de demander sans que « on sait qu'il a demandé » circule dans l'église.
    Le coût social est exactement ce que le canal venait de supprimer : le faire revenir par la
    porte administrative annulerait tout le bénéfice."""
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    pending = _appt(tenant)  # une main levée — pas l'affaire du secrétariat
    confirmed = _appt(tenant, status=AppointmentStatus.CONFIRMED)
    confirmed.scheduled_at = _SLOT
    resolved = _appt(tenant)
    resolved.cancel(now=_NOW)
    appts = _FakeAppointments([confirmed, pending, resolved])

    entries = await ListTenantAgenda(appts, _access(ms)).execute(
        actor_account_id=keeper, tenant_id=tenant
    )

    assert [e.id for e in entries] == [confirmed.id]
    # Le type de sortie ne porte tout simplement pas ces champs.
    assert not hasattr(entries[0], "subject")
    assert not hasattr(entries[0], "note")


async def test_agenda_is_refused_to_a_non_keeper():
    tenant = uuid4()
    stranger = uuid4()
    ms = _FakeMemberships([_member(stranger, tenant)])
    with pytest.raises(UnauthorizedGroupActionError):
        await ListTenantAgenda(_FakeAppointments(), _access(ms)).execute(
            actor_account_id=stranger, tenant_id=tenant
        )


# --- La secrétaire émet au bureau (walk-in) + ferme + le pasteur gère ---


async def test_secretary_opens_a_walk_in_appointment():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    appts = _FakeAppointments()
    cmd = OpenAppointment(appts, _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(
        actor_account_id=keeper, tenant_id=tenant, subject="Préparation de mariage",
        category=AppointmentCategory.MARRIAGE, requester_name="Awa & Kofi",
    )
    assert dto.requester_account_id is None and dto.requester_name == "Awa & Kofi"
    assert dto.category == "marriage" and dto.status == "requested"
    assert len(appts._a) == 1


async def test_secretary_opens_and_confirms_a_slot_in_one_act():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    cmd = OpenAppointment(_FakeAppointments(), _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(
        actor_account_id=keeper, tenant_id=tenant, subject="Visite",
        requester_name="Mme Diallo", scheduled_at=_SLOT,
    )
    assert dto.status == "confirmed" and dto.scheduled_at == _SLOT


async def test_an_ordinary_member_cannot_open_at_the_office():
    tenant = uuid4()
    stranger = uuid4()
    ms = _FakeMemberships([_member(stranger, tenant)])
    cmd = OpenAppointment(_FakeAppointments(), _access(ms), clock=lambda: _NOW)
    with pytest.raises(UnauthorizedGroupActionError):
        await cmd.execute(
            actor_account_id=stranger, tenant_id=tenant, subject="x", requester_name="X"
        )


async def test_keeper_closes_an_appointment_that_wont_happen():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    a = _appt(tenant, status=AppointmentStatus.CONFIRMED)
    cmd = CloseAppointment(_FakeAppointments([a]), _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(actor_account_id=keeper, appointment_id=a.id)
    assert dto.status == "cancelled"


class _FakeNotifier(Notifier):
    def __init__(self):
        self.calls = []

    async def notify(self, account_ids, notification):
        self.calls.append((list(account_ids), notification))


async def test_confirming_notifies_the_requester():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    requester = uuid4()
    a = _appt(tenant, requester=requester)
    notifier = _FakeNotifier()
    cmd = ConfirmAppointment(_FakeAppointments([a]), _access(ms), notifier, clock=lambda: _NOW)
    await cmd.execute(actor_account_id=keeper, appointment_id=a.id, scheduled_at=_SLOT)
    assert notifier.calls and notifier.calls[0][0] == [requester]


async def test_a_walk_in_appointment_notifies_no_one():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    a = Appointment.open_at_office(
        id=uuid4(), tenant_id=tenant, opened_by_account_id=keeper,
        subject="Visite", category=AppointmentCategory.VISIT, now=_NOW, requester_name="Passant",
    )
    notifier = _FakeNotifier()
    cmd = ConfirmAppointment(_FakeAppointments([a]), _access(ms), notifier, clock=lambda: _NOW)
    await cmd.execute(actor_account_id=keeper, appointment_id=a.id, scheduled_at=_SLOT)
    assert notifier.calls == []  # walk-in sans compte → personne à prévenir


class _FakeScheduler(NotificationScheduler):
    def __init__(self):
        self.calls = []

    async def schedule(self, account_ids, notification, *, at):
        self.calls.append((list(account_ids), notification, at))


async def test_confirming_schedules_a_reminder_before_the_slot():
    from app.contexts.appointments.application.commands.manage import REMINDER_LEAD

    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    requester = uuid4()
    a = _appt(tenant, requester=requester)
    scheduler = _FakeScheduler()
    cmd = ConfirmAppointment(
        _FakeAppointments([a]), _access(ms), None, scheduler, clock=lambda: _NOW
    )
    await cmd.execute(actor_account_id=keeper, appointment_id=a.id, scheduled_at=_SLOT)
    assert scheduler.calls
    targets, _notif, at = scheduler.calls[0]
    assert targets == [requester] and at == _SLOT - REMINDER_LEAD


async def test_a_walk_in_gets_no_reminder():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    a = Appointment.open_at_office(
        id=uuid4(), tenant_id=tenant, opened_by_account_id=keeper,
        subject="Visite", category=AppointmentCategory.VISIT, now=_NOW, requester_name="Passant",
    )
    scheduler = _FakeScheduler()
    cmd = ConfirmAppointment(
        _FakeAppointments([a]), _access(ms), None, scheduler, clock=lambda: _NOW
    )
    await cmd.execute(actor_account_id=keeper, appointment_id=a.id, scheduled_at=_SLOT)
    assert scheduler.calls == []  # walk-in sans compte → personne à rappeler


async def test_pastor_manages_his_own_agenda():
    tenant = uuid4()
    pastor = uuid4()
    ms = _FakeMemberships([_member(pastor, tenant, (RoleCode.PASTOR, None))])
    a = _appt(tenant)
    cmd = ConfirmAppointment(_FakeAppointments([a]), _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(actor_account_id=pastor, appointment_id=a.id, scheduled_at=_SLOT)
    assert dto.status == "confirmed"


# --- Disponibilités (récurrence hebdomadaire) + réservation de créneaux ---

_THU_10H = datetime(2026, 1, 8, 10, 0, tzinfo=UTC)  # un jeudi futur, 10h UTC


def _rule(tenant, pastor, *, weekday=3, start=600, end=660, slot=30) -> AvailabilityRule:
    return AvailabilityRule.create(
        id=uuid4(), tenant_id=tenant, pastor_account_id=pastor,
        weekday=weekday, start_minute=start, end_minute=end, slot_minutes=slot, now=_NOW,
    )


def test_availability_rule_generates_weekly_slots():
    rule = _rule(uuid4(), uuid4())  # jeudi 10h-11h, creneaux 30 min -> 2 par jeudi
    slots = rule.generate(from_date=date(2026, 1, 2), to_date=date(2026, 1, 31))
    # 4 jeudis dans la plage, 2 creneaux chacun
    assert len(slots) == 8 and slots[0].starts_at == _THU_10H


def test_availability_rule_rejects_a_bad_window():
    with pytest.raises(InvalidAvailabilityError):
        _rule(uuid4(), uuid4(), start=660, end=600)  # fin avant début
    with pytest.raises(InvalidAvailabilityError):
        _rule(uuid4(), uuid4(), weekday=9)  # jour hors 0-6


async def test_keeper_sets_availability_for_a_pastor():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    pastor = uuid4()
    ms._m.append(_member(pastor, tenant, (RoleCode.PASTOR, None)))
    rules = _FakeRules()
    cmd = AddAvailabilityRule(rules, ms, _access(ms), clock=lambda: _NOW)
    dto = await cmd.execute(
        actor_account_id=keeper, tenant_id=tenant, pastor_account_id=pastor,
        weekday=3, start_minute=600, end_minute=660, slot_minutes=30,
    )
    assert dto.pastor_account_id == pastor and len(rules._r) == 1


async def test_cannot_set_availability_for_a_non_pastor():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    not_pastor = uuid4()
    ms._m.append(_member(not_pastor, tenant))  # membre ordinaire, pas pasteur
    cmd = AddAvailabilityRule(_FakeRules(), ms, _access(ms), clock=lambda: _NOW)
    with pytest.raises(NotAPastorError):
        await cmd.execute(
            actor_account_id=keeper, tenant_id=tenant, pastor_account_id=not_pastor,
            weekday=3, start_minute=600, end_minute=660, slot_minutes=30,
        )


async def test_deactivate_availability_removes_it_from_the_offer():
    tenant = uuid4()
    keeper, ms = _secretary(tenant)
    pastor = uuid4()
    ms._m.append(_member(pastor, tenant))
    rule = _rule(tenant, pastor)
    rules = _FakeRules([rule])
    await DeactivateAvailabilityRule(rules, _access(ms)).execute(
        actor_account_id=keeper, rule_id=rule.id
    )
    assert rule.active is False


async def test_open_slots_lists_future_free_slots_across_pastors():
    tenant, member, pastor = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    q = ListOpenSlots(
        _FakeRules([_rule(tenant, pastor)]), _FakeAppointments(), ms, clock=lambda: _NOW
    )
    slots = await q.execute(
        actor_account_id=member, tenant_id=tenant,
        from_date=date(2026, 1, 2), to_date=date(2026, 1, 31),
    )
    assert len(slots) == 8 and slots[0].starts_at == _THU_10H
    assert slots[0].pastor_account_id == pastor


async def test_member_books_an_open_slot_and_it_disappears_from_the_offer():
    tenant, member, pastor = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    rules, appts = _FakeRules([_rule(tenant, pastor)]), _FakeAppointments()
    dto = await BookSlot(rules, appts, ms, clock=lambda: _NOW).execute(
        actor_account_id=member, tenant_id=tenant,
        with_pastor_account_id=pastor, starts_at=_THU_10H, subject="Prière",
    )
    assert dto.status == "confirmed" and dto.with_pastor_account_id == pastor
    slots = await ListOpenSlots(rules, appts, ms, clock=lambda: _NOW).execute(
        actor_account_id=member, tenant_id=tenant,
        from_date=date(2026, 1, 2), to_date=date(2026, 1, 31),
    )
    assert all(s.starts_at != _THU_10H for s in slots)  # le créneau pris n'est plus offert


async def test_cannot_book_the_same_slot_twice():
    tenant, m1, m2, pastor = uuid4(), uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(m1, tenant), _member(m2, tenant)])
    rules, appts = _FakeRules([_rule(tenant, pastor)]), _FakeAppointments()
    book = BookSlot(rules, appts, ms, clock=lambda: _NOW)
    await book.execute(actor_account_id=m1, tenant_id=tenant,
                       with_pastor_account_id=pastor, starts_at=_THU_10H, subject="x")
    with pytest.raises(SlotNotAvailableError):
        await book.execute(actor_account_id=m2, tenant_id=tenant,
                           with_pastor_account_id=pastor, starts_at=_THU_10H, subject="y")


async def test_cannot_book_a_time_outside_availability():
    tenant, member, pastor = uuid4(), uuid4(), uuid4()
    ms = _FakeMemberships([_member(member, tenant)])
    book = BookSlot(
        _FakeRules([_rule(tenant, pastor)]), _FakeAppointments(), ms, clock=lambda: _NOW
    )
    off = datetime(2026, 1, 8, 15, 0, tzinfo=UTC)  # 15h : hors de la fenêtre 10h-11h
    with pytest.raises(SlotNotAvailableError):
        await book.execute(actor_account_id=member, tenant_id=tenant,
                           with_pastor_account_id=pastor, starts_at=off, subject="x")


async def test_a_non_member_cannot_see_slots():
    q = ListOpenSlots(_FakeRules(), _FakeAppointments(), _FakeMemberships(), clock=lambda: _NOW)
    with pytest.raises(RequesterNotMemberError):
        await q.execute(actor_account_id=uuid4(), tenant_id=uuid4(),
                        from_date=date(2026, 1, 2), to_date=date(2026, 1, 31))
