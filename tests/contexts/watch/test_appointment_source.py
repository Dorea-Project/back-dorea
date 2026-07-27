"""Le rendez-vous comme source de veille — les chemins d'échec cessent de se perdre.

*Un rendez-vous demandé est une main levée. L'agenda n'est que ce qui se passe après.*
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.appointments.application.watch_facts import (
    EmitAppointmentFacts,
    fact_id_for,
    state_of,
)
from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.enums import AppointmentCategory, AppointmentStatus
from app.contexts.appointments.domain.unavailability import (
    PastorUnavailability,
    is_available,
)
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.appointment_requested import (
    AppointmentRequestedV1,
    AppointmentState,
)
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.facts import FactKind
from app.contexts.watch.domain.registry import APPOINTMENTS, default_registry
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


def _engine():
    ledger, signals = FakeLedger(), FakeSignals()
    interpreters = InterpreterRegistry()
    interpreters.register(AppointmentRequestedV1())
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    intake = Intake(ledger, default_registry(), interpreters, store, signals)
    return intake, signals, ledger


def _requested(*, tenant, member, note=None) -> Appointment:
    return Appointment.request(
        id=uuid4(), tenant_id=tenant, requester_account_id=member,
        subject="Un entretien", category=AppointmentCategory.COUNSEL,
        now=_NOW, note=note,
    )


async def _emit(intake, appointment):
    return await EmitAppointmentFacts(intake, clock=lambda: _NOW).execute(appointment)


# --- Aucun nouveau type de fait ---------------------------------------------------------


def test_the_appointment_adds_no_fact_kind_to_the_registry():
    """Le greffon le plus lourd du produit se pose sans rouvrir le contrat."""
    registry = default_registry()
    assert registry.accepts(APPOINTMENTS, FactKind.APPOINTMENT_REQUESTED) is True
    # Et il ne peut dire que cela : pas de présence, pas d'annonce.
    assert registry.accepts(APPOINTMENTS, FactKind.PRESENCE_RECORDED) is False


# --- La demande : une main levée --------------------------------------------------------


async def test_a_request_opens_a_declared_case_at_the_moment_of_the_gesture():
    """Le fait naît **à la demande**, pas à la confirmation du créneau.

    L'enregistrer trois jours plus tard, c'est perdre l'antériorité — la preuve que le produit
    a vu venir avant de calculer."""
    tenant, member = uuid4(), uuid4()
    intake, signals, ledger = _engine()

    await _emit(intake, _requested(tenant=tenant, member=member, note="J'ai besoin de parler"))

    (fact,) = ledger.rows
    assert fact.kind is FactKind.APPOINTMENT_REQUESTED
    assert fact.occurred_at == _NOW  # daté du geste

    (case,) = signals.rows
    assert case.origin is CasePriority.DECLARED  # exempt du plafond de débit
    assert "rencontrer un pasteur" in case.reason
    assert "J'ai besoin de parler" in case.reason


async def test_a_walk_in_without_an_account_emits_nothing():
    """Sans compte, il n'y a pas de sujet de veille — le fait n'aurait personne sur qui porter."""
    intake, _, ledger = _engine()
    walk_in = Appointment.open_at_office(
        id=uuid4(), tenant_id=uuid4(), opened_by_account_id=uuid4(),
        subject="Une question", category=AppointmentCategory.ADMINISTRATIVE,
        now=_NOW, requester_name="Un visiteur",
    )

    assert await _emit(intake, walk_in) is False
    assert ledger.rows == []


def test_confirming_a_slot_says_nothing_to_the_engine():
    """Poser un créneau, c'est notre organisation — pas le mouvement de la personne."""
    appointment = _requested(tenant=uuid4(), member=uuid4())
    appointment.confirm(at=_NOW + timedelta(days=3), by_account_id=uuid4(), now=_NOW)

    assert state_of(appointment) is None


# --- Les chemins d'échec, qui portent le plus d'information -----------------------------


async def test_cancelling_ones_own_request_is_the_most_urgent_signal():
    """Il a franchi le pas le plus difficile, puis a fait demi-tour."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()
    appointment = _requested(tenant=tenant, member=member)
    await _emit(intake, appointment)

    appointment.cancel(now=_NOW + timedelta(days=1), by_account_id=member)
    await _emit(intake, appointment)

    (case,) = signals.rows  # un seul cas : on enrichit, on ne duplique pas
    assert case.priority is CasePriority.DECLARED
    assert "A annulé le rendez-vous qu'il avait demandé." in case.annotations
    # La raison d'origine n'a pas bougé — on lit une trajectoire, pas un instantané.
    assert "rencontrer un pasteur" in case.reason


async def test_the_church_closing_a_stale_appointment_says_nothing():
    """L'église qui range son agenda ne dit rien de la personne."""
    tenant, member, secretary = uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine()
    appointment = _requested(tenant=tenant, member=member)
    await _emit(intake, appointment)
    before = list(signals.rows[0].annotations)

    appointment.cancel(now=_NOW + timedelta(days=1), by_account_id=secretary)

    assert state_of(appointment) is None
    assert signals.rows[0].annotations == before


async def test_a_no_show_reopens_at_maximum_priority():
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()
    appointment = _requested(tenant=tenant, member=member)
    await _emit(intake, appointment)
    appointment.confirm(at=_NOW + timedelta(days=2), by_account_id=uuid4(), now=_NOW)

    appointment.mark_no_show(by_account_id=uuid4(), now=_NOW + timedelta(days=2))
    await _emit(intake, appointment)

    assert "N'est pas venu au rendez-vous qu'il avait demandé." in signals.rows[0].annotations


async def test_a_decline_keeps_the_case_open_and_carries_the_motive():
    """Il a demandé, on n'a pas pu : c'est **notre** dette. Le cas ne se ferme pas."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()
    appointment = _requested(tenant=tenant, member=member)
    await _emit(intake, appointment)

    appointment.decline(
        by_account_id=uuid4(), reason="Le pasteur est en déplacement", now=_NOW
    )
    await _emit(intake, appointment)

    (case,) = signals.rows
    assert case.is_live is True  # rien n'a fermé
    assert any("déplacement" in a for a in case.annotations)


async def test_orienting_is_not_a_disguised_refusal():
    """Servi autrement : le cas reste ouvert et change de main."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()
    appointment = _requested(tenant=tenant, member=member)
    await _emit(intake, appointment)

    appointment.orient(to_account_id=uuid4(), by_account_id=uuid4(), now=_NOW)
    await _emit(intake, appointment)

    (case,) = signals.rows
    assert case.is_live is True
    assert any("Orienté" in a for a in case.annotations)


async def test_honouring_annotates_but_never_closes():
    """Planifier n'est pas rencontrer ; rencontrer n'est pas résoudre.

    Sans cette règle on obtiendrait un excellent taux de résolution et personne de rencontré."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()
    appointment = _requested(tenant=tenant, member=member)
    await _emit(intake, appointment)
    appointment.confirm(at=_NOW + timedelta(days=2), by_account_id=uuid4(), now=_NOW)

    appointment.complete(by_account_id=uuid4(), now=_NOW + timedelta(days=2))
    await _emit(intake, appointment)

    (case,) = signals.rows
    assert case.is_live is True  # un humain fermera
    assert case.outcome is None
    assert any("honoré" in a for a in case.annotations)


# --- Idempotence ------------------------------------------------------------------------


async def test_replaying_a_transition_changes_nothing():
    """`fact_id` est dérivé de (rendez-vous, état)."""
    tenant, member = uuid4(), uuid4()
    intake, signals, ledger = _engine()
    appointment = _requested(tenant=tenant, member=member)

    await _emit(intake, appointment)
    await _emit(intake, appointment)
    await _emit(intake, appointment)

    assert len(ledger.rows) == 1
    assert len(signals.rows) == 1
    assert ledger.rows[0].fact_id == fact_id_for(appointment.id, AppointmentState.REQUESTED)


# --- L'absence n'est pas un oubli -------------------------------------------------------


def test_a_declared_absence_is_known_in_advance():
    """Un pasteur en voyage trois semaines ne doit pas faire attendre chaque demande.

    L'absence est prévisible et se consulte **avant** d'assigner ; l'oubli se constate après."""
    pastor, tenant = uuid4(), uuid4()
    voyage = PastorUnavailability(
        id=uuid4(), tenant_id=tenant, pastor_account_id=pastor,
        unavailable_from=_NOW, unavailable_until=_NOW + timedelta(days=21),
        declared_by_account_id=pastor, declared_at=_NOW,
    )

    assert is_available([voyage], _NOW + timedelta(days=10)) is False
    assert is_available([voyage], _NOW + timedelta(days=30)) is True
    assert is_available([], _NOW) is True


def test_a_cancelled_absence_stops_blocking():
    pastor, tenant = uuid4(), uuid4()
    voyage = PastorUnavailability(
        id=uuid4(), tenant_id=tenant, pastor_account_id=pastor,
        unavailable_from=_NOW, unavailable_until=_NOW + timedelta(days=21),
        declared_by_account_id=pastor, declared_at=_NOW,
    )
    voyage.cancel(now=_NOW + timedelta(days=2))

    assert is_available([voyage], _NOW + timedelta(days=10)) is True


def test_no_reason_is_ever_required():
    """Un pasteur n'a pas à justifier son absence pour que le système sache l'anticiper."""
    absence = PastorUnavailability(
        id=uuid4(), tenant_id=uuid4(), pastor_account_id=uuid4(),
        unavailable_from=_NOW, unavailable_until=_NOW + timedelta(days=3),
        declared_by_account_id=uuid4(), declared_at=_NOW,
    )
    assert absence.reason is None


# --- Les transitions refusées -----------------------------------------------------------


def test_you_cannot_orient_something_already_resolved():
    from app.contexts.appointments.domain.errors import AppointmentClosedError

    appointment = _requested(tenant=uuid4(), member=uuid4())
    appointment.decline(by_account_id=uuid4(), reason=None, now=_NOW)

    with pytest.raises(AppointmentClosedError):
        appointment.orient(to_account_id=uuid4(), by_account_id=uuid4(), now=_NOW)


def test_only_a_confirmed_appointment_can_be_a_no_show():
    from app.contexts.appointments.domain.errors import AppointmentClosedError

    appointment = _requested(tenant=uuid4(), member=uuid4())

    with pytest.raises(AppointmentClosedError):
        appointment.mark_no_show(by_account_id=uuid4(), now=_NOW)
    assert appointment.status is AppointmentStatus.REQUESTED
