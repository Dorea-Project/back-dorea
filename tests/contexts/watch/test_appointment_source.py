"""Le rendez-vous comme source de veille — les chemins d'échec cessent de se perdre.

*Un rendez-vous demandé est une main levée. L'agenda n'est que ce qui se passe après.*

**Ce que ce module protège avant tout (30/07/2026) :** le sujet d'une demande de rendez-vous ne
doit jamais atteindre le responsable de cellule du demandeur. La demande n'ouvre donc aucun cas,
et chaque issue d'échec nomme elle-même son destinataire.
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
from app.contexts.watch.application.owner_assignment import ResolveOwners
from app.contexts.watch.application.projections import RebuildProjections
from app.contexts.watch.application.referent_resolution import SignalOwner
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.facts import FactKind
from app.contexts.watch.domain.registry import APPOINTMENTS, default_registry
from app.contexts.watch.domain.signal import Signal, SignalStatus
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


class _Cascade:
    """La cascade du référent, réduite à ce qu'elle renvoie.

    Elle rend **toujours** le responsable de cellule : c'est exactement le destinataire que la
    correction doit écarter pour les rendez-vous. Si un test voit ce compte comme propriétaire
    d'un cas de rendez-vous, la fuite est de retour."""

    def __init__(self, group_lead):
        self.group_lead = group_lead

    async def execute(self, *, person_id, tenant_id, at):
        return SignalOwner(self.group_lead)


class _People:
    """L'annuaire, réduit aux deux questions que l'étage 02bis lui pose."""

    def __init__(self, *, keeper=None, pastor=None, owner=None):
        self._keeper, self._pastor, self._owner = keeper, pastor, owner

    async def agenda_keeper(self, tenant_id):
        return self._keeper

    async def pastor(self, tenant_id):
        return self._pastor

    async def tenant_owner(self, tenant_id):
        return self._owner


def _engine(*, group_lead=None, keeper=None, pastor=None, owner=None):
    """Le moteur avec son étage 02bis — comme en production."""
    ledger, signals = FakeLedger(), FakeSignals()
    interpreters = InterpreterRegistry()
    interpreters.register(AppointmentRequestedV1())
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    owners = ResolveOwners(
        _Cascade(group_lead or uuid4()),
        _People(keeper=keeper, pastor=pastor, owner=owner),
    )
    intake = Intake(
        ledger, default_registry(), interpreters, store, signals, None, owners
    )
    return intake, signals, ledger


def _requested(*, tenant, member, note=None) -> Appointment:
    return Appointment.request(
        id=uuid4(), tenant_id=tenant, requester_account_id=member,
        subject="Un entretien", category=AppointmentCategory.COUNSEL,
        now=_NOW, note=note,
    )


async def _emit(intake, appointment):
    return await EmitAppointmentFacts(intake, clock=lambda: _NOW).execute(appointment)


def _seed_absence_case(signals, *, tenant, member, owner):
    """Un cas d'absence déjà ouvert, appartenant à son responsable — le terrain de la fusion."""
    signals.rows.append(
        Signal(
            id=uuid4(), tenant_id=tenant, subject_id=member,
            origin=CasePriority.ABSENCE, reason="Sans nouvelles depuis 4 semaines.",
            opened_at=_NOW - timedelta(days=28), status=SignalStatus.ASSIGNED,
            owner_account_id=owner,
        )
    )
    return signals.rows[-1]


# --- Aucun nouveau type de fait ---------------------------------------------------------


def test_the_appointment_adds_no_fact_kind_to_the_registry():
    """Le greffon le plus lourd du produit se pose sans rouvrir le contrat."""
    registry = default_registry()
    assert registry.accepts(APPOINTMENTS, FactKind.APPOINTMENT_REQUESTED) is True
    # Et il ne peut dire que cela : pas de présence, pas d'annonce.
    assert registry.accepts(APPOINTMENTS, FactKind.PRESENCE_RECORDED) is False


# --- La demande : au ledger, et nulle part ailleurs -------------------------------------


async def test_a_request_enters_the_ledger_and_opens_no_case():
    """Le fait naît **à la demande** — mais il n'ouvre rien.

    L'antériorité est conservée (« la preuve que le produit a vu venir »), et le sujet écrit par
    le membre ne peut plus atteindre l'écran de personne. Le devoir de répondre est tenu par le
    relais, pas par un cas."""
    tenant, member, lead = uuid4(), uuid4(), uuid4()
    intake, signals, ledger = _engine(group_lead=lead)

    await _emit(intake, _requested(tenant=tenant, member=member, note="J'ai besoin de parler"))

    (fact,) = ledger.rows
    assert fact.kind is FactKind.APPOINTMENT_REQUESTED
    assert fact.occurred_at == _NOW  # daté du geste
    assert signals.rows == []  # et rien, chez personne


async def test_the_private_note_never_reaches_a_case():
    """La note du membre voyage au ledger, jamais sur une fiche de cas.

    C'est la fuite qui existait : le responsable de cellule lisait « A demandé à rencontrer un
    pasteur. « … » » — y compris quand c'était de lui que le membre voulait parler."""
    tenant, member, lead = uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(group_lead=lead, pastor=uuid4())
    appointment = _requested(tenant=tenant, member=member, note="Je suis en conflit avec Paul")
    await _emit(intake, appointment)

    appointment.cancel(now=_NOW + timedelta(days=1), by_account_id=member)
    await _emit(intake, appointment)

    (case,) = signals.rows
    everything = " ".join([case.reason, *case.annotations])
    assert "conflit" not in everything
    assert "Paul" not in everything


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


# --- Les chemins d'échec : chacun nomme son destinataire --------------------------------


async def test_cancelling_ones_own_request_goes_to_the_pastor_never_to_the_group_lead():
    """Il a franchi le pas le plus difficile, puis a fait demi-tour.

    On ne supprime pas le signal le plus urgent du produit — on le remet à celui à qui la main
    avait été tendue. Et **jamais** au responsable de cellule, même quand la cascade le désigne."""
    tenant, member, lead, pastor = uuid4(), uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(group_lead=lead)
    appointment = _requested(tenant=tenant, member=member)
    appointment.confirm(at=_NOW + timedelta(days=3), by_account_id=uuid4(), now=_NOW)
    appointment.with_pastor_account_id = pastor

    appointment.cancel(now=_NOW + timedelta(days=1), by_account_id=member)
    await _emit(intake, appointment)

    (case,) = signals.rows
    assert case.owner_account_id == pastor
    assert case.owner_account_id != lead
    assert case.priority is CasePriority.DECLARED  # hors plafond : la personne a parlé
    assert "A annulé le rendez-vous qu'il avait demandé." in case.reason


async def test_the_pastor_of_the_slot_wins_over_any_pastor_of_the_church():
    """Le destinataire est le pasteur de **ce** rendez-vous, pas le premier pasteur du tenant."""
    tenant, member = uuid4(), uuid4()
    his_pastor, another_pastor = uuid4(), uuid4()
    intake, signals, _ = _engine(pastor=another_pastor)
    appointment = _requested(tenant=tenant, member=member)
    appointment.confirm(at=_NOW + timedelta(days=2), by_account_id=uuid4(), now=_NOW)
    appointment.with_pastor_account_id = his_pastor

    appointment.mark_no_show(by_account_id=uuid4(), now=_NOW + timedelta(days=2))
    await _emit(intake, appointment)

    (case,) = signals.rows
    assert case.owner_account_id == his_pastor


async def test_a_cancellation_without_a_slot_falls_back_to_a_pastor():
    """Annulée avant qu'un créneau existe : il n'y a pas de pasteur nommé, mais il en faut un."""
    tenant, member, lead, pastor = uuid4(), uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(group_lead=lead, pastor=pastor)
    appointment = _requested(tenant=tenant, member=member)

    appointment.cancel(now=_NOW + timedelta(days=1), by_account_id=member)
    await _emit(intake, appointment)

    (case,) = signals.rows
    assert case.owner_account_id == pastor


async def test_a_no_show_opens_at_maximum_priority():
    tenant, member, pastor = uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(pastor=pastor)
    appointment = _requested(tenant=tenant, member=member)
    appointment.confirm(at=_NOW + timedelta(days=2), by_account_id=uuid4(), now=_NOW)

    appointment.mark_no_show(by_account_id=uuid4(), now=_NOW + timedelta(days=2))
    await _emit(intake, appointment)

    (case,) = signals.rows
    assert "N'est pas venu au rendez-vous qu'il avait demandé." in case.reason
    assert case.priority is CasePriority.DECLARED


async def test_a_decline_belongs_to_whoever_declined():
    """Il a demandé, on n'a pas pu : c'est **notre** dette — celle de l'agenda, pas du référent.

    Le référent n'a rien décliné. La dette appartient à qui tient l'agenda, et le plus exact est
    celui qui a effectivement refusé."""
    tenant, member, lead, secretary = uuid4(), uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(group_lead=lead)
    appointment = _requested(tenant=tenant, member=member)

    appointment.decline(
        by_account_id=secretary, reason="Le pasteur est en déplacement", now=_NOW
    )
    await _emit(intake, appointment)

    (case,) = signals.rows
    assert case.owner_account_id == secretary
    assert case.owner_account_id != lead
    assert case.is_live is True  # rien n'a fermé : on ne renvoie pas une main levée
    assert "déplacement" in case.reason


async def test_a_decline_without_a_handler_goes_to_the_agenda_keeper():
    """Personne n'est nommé sur le refus : le cas va au détenteur de `MANAGE_APPOINTMENTS`."""
    tenant, member, lead, keeper = uuid4(), uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(group_lead=lead, keeper=keeper)
    appointment = _requested(tenant=tenant, member=member)
    appointment.decline(by_account_id=uuid4(), reason=None, now=_NOW)
    appointment.handled_by_account_id = None  # refus sans auteur enregistré

    await _emit(intake, appointment)

    (case,) = signals.rows
    assert case.owner_account_id == keeper


# --- Ce qui annote sans ouvrir ----------------------------------------------------------


async def test_orienting_annotates_an_existing_case_and_opens_none():
    """Servi autrement : changement de main, pas fermeture — et pas un cas de plus."""
    tenant, member, lead = uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(group_lead=lead)
    case = _seed_absence_case(signals, tenant=tenant, member=member, owner=lead)
    appointment = _requested(tenant=tenant, member=member)

    appointment.orient(to_account_id=uuid4(), by_account_id=uuid4(), now=_NOW)
    await _emit(intake, appointment)

    assert len(signals.rows) == 1
    assert case.is_live is True
    assert any("Orienté" in a for a in case.annotations)


async def test_honouring_annotates_but_never_closes():
    """Planifier n'est pas rencontrer ; rencontrer n'est pas résoudre.

    Sans cette règle on obtiendrait un excellent taux de résolution et personne de rencontré."""
    tenant, member, lead = uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(group_lead=lead)
    case = _seed_absence_case(signals, tenant=tenant, member=member, owner=lead)
    appointment = _requested(tenant=tenant, member=member)
    appointment.confirm(at=_NOW + timedelta(days=2), by_account_id=uuid4(), now=_NOW)

    appointment.complete(by_account_id=uuid4(), now=_NOW + timedelta(days=2))
    await _emit(intake, appointment)

    assert case.is_live is True  # un humain fermera
    assert case.outcome is None
    assert any("honoré" in a for a in case.annotations)


async def test_a_honoured_appointment_alone_opens_nothing():
    """Rencontrer quelqu'un qui n'a pas de cas n'en ouvre pas un : il n'y a rien à signaler."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()
    appointment = _requested(tenant=tenant, member=member)
    appointment.confirm(at=_NOW + timedelta(days=2), by_account_id=uuid4(), now=_NOW)

    appointment.complete(by_account_id=uuid4(), now=_NOW + timedelta(days=2))
    await _emit(intake, appointment)

    assert signals.rows == []


async def test_the_church_closing_a_stale_appointment_says_nothing():
    """L'église qui range son agenda ne dit rien de la personne."""
    tenant, member, secretary = uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine()
    appointment = _requested(tenant=tenant, member=member)
    await _emit(intake, appointment)

    appointment.cancel(now=_NOW + timedelta(days=1), by_account_id=secretary)

    assert state_of(appointment) is None
    assert signals.rows == []


# --- La fusion : ce qu'on apprend s'ajoute, et l'urgence monte --------------------------


async def test_a_cancellation_on_an_open_case_keeps_its_annotation_and_raises_priority():
    """Le cas existe déjà : on enrichit, on ne duplique pas — **et on ne perd rien**.

    Sans cette garantie, l'arbitrage fusionnait l'ouverture en jetant l'annotation et la
    priorité : le responsable ne verrait jamais que la personne a annulé le rendez-vous qu'elle
    avait demandé, et le signal le plus urgent du produit se dissoudrait en une source de plus."""
    tenant, member, lead, pastor = uuid4(), uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine(group_lead=lead, pastor=pastor)
    case = _seed_absence_case(signals, tenant=tenant, member=member, owner=lead)
    appointment = _requested(tenant=tenant, member=member)

    appointment.cancel(now=_NOW + timedelta(days=1), by_account_id=member)
    await _emit(intake, appointment)

    assert len(signals.rows) == 1
    assert "A annulé le rendez-vous qu'il avait demandé." in case.annotations
    assert case.priority is CasePriority.DECLARED  # l'urgence est montée
    # La raison d'origine n'a pas bougé — on lit une trajectoire, pas un instantané.
    assert "Sans nouvelles" in case.reason
    # Et le cas reste chez son propriétaire : enrichir n'est pas réattribuer.
    assert case.owner_account_id == lead


# --- Le propriétaire n'est jamais nul ---------------------------------------------------


async def test_no_case_from_the_appointments_source_is_ever_ownerless():
    """Sur une séquence complète, aucun cas n'arrive sans destinataire.

    C'est l'invariant qui autorise `owner_account_id` à être NOT NULL en base — et qui referme la
    règle « un cas sans propriétaire est prenable », par laquelle n'importe quel responsable
    pouvait s'attribuer un cas de rendez-vous, donc le lire."""
    tenant = uuid4()
    intake, signals, _ = _engine(pastor=uuid4(), keeper=uuid4(), owner=uuid4())

    for by_member in (True, False):
        appointment = _requested(tenant=tenant, member=uuid4())
        await _emit(intake, appointment)
        appointment.confirm(at=_NOW + timedelta(days=2), by_account_id=uuid4(), now=_NOW)
        if by_member:
            appointment.cancel(
                now=_NOW + timedelta(days=1), by_account_id=appointment.requester_account_id
            )
        else:
            appointment.mark_no_show(by_account_id=uuid4(), now=_NOW + timedelta(days=2))
        await _emit(intake, appointment)

    declined = _requested(tenant=tenant, member=uuid4())
    declined.decline(by_account_id=uuid4(), reason="Indisponible", now=_NOW)
    await _emit(intake, declined)

    assert len(signals.rows) == 3
    assert all(case.owner_account_id is not None for case in signals.rows)


async def test_a_church_with_nobody_configured_opens_no_case_rather_than_a_readable_one():
    """Aucun échelon, pas même un propriétaire : on n'invente pas de destinataire.

    Le trou est consigné par la cascade au niveau du tenant. Mieux vaut un cas non émis et un
    défaut visible qu'un cas adressé à quelqu'un choisi au hasard."""

    class _Empty:
        async def execute(self, *, person_id, tenant_id, at):
            return None

    ledger, signals = FakeLedger(), FakeSignals()
    interpreters = InterpreterRegistry()
    interpreters.register(AppointmentRequestedV1())
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    intake = Intake(
        ledger, default_registry(), interpreters, store, signals, None,
        ResolveOwners(_Empty(), _People()),
    )
    appointment = _requested(tenant=uuid4(), member=uuid4())
    appointment.decline(by_account_id=uuid4(), reason=None, now=_NOW)
    appointment.handled_by_account_id = None

    result = await _emit(intake, appointment)

    assert result is True  # le fait est au ledger : rien n'est perdu
    assert len(ledger.rows) == 1
    assert signals.rows == []  # mais aucun cas n'est adressé au hasard


# --- Idempotence et déterminisme --------------------------------------------------------


async def test_replaying_a_transition_changes_nothing():
    """`fact_id` est dérivé de (rendez-vous, état)."""
    tenant, member = uuid4(), uuid4()
    intake, signals, ledger = _engine(pastor=uuid4())
    appointment = _requested(tenant=tenant, member=member)
    appointment.decline(by_account_id=uuid4(), reason=None, now=_NOW)

    await _emit(intake, appointment)
    await _emit(intake, appointment)
    await _emit(intake, appointment)

    assert len(ledger.rows) == 1
    assert len(signals.rows) == 1
    assert ledger.rows[0].fact_id == fact_id_for(appointment.id, AppointmentState.DECLINED)


async def test_replaying_the_ledger_rebuilds_an_identical_state():
    """La résolution du destinataire vit hors interpreter — elle ne casse pas le déterminisme.

    C'est l'invariant 15 appliqué au chantier : rejouer le journal doit reconstruire le même
    état, propriétaires compris. Sans l'étage 02bis dans la reprojection, le rejeu réécrirait des
    cas sans destinataire sur une colonne qui n'en accepte plus."""
    tenant, member, pastor, keeper = uuid4(), uuid4(), uuid4(), uuid4()
    intake, signals, ledger = _engine(pastor=pastor, keeper=keeper)

    first = _requested(tenant=tenant, member=member)
    await _emit(intake, first)
    first.decline(by_account_id=keeper, reason="Indisponible", now=_NOW)
    await _emit(intake, first)

    before = [
        (c.subject_id, c.reason, c.owner_account_id, c.priority, c.status)
        for c in signals.rows
    ]

    owners = ResolveOwners(_Cascade(uuid4()), _People(keeper=keeper, pastor=pastor))
    interpreters = InterpreterRegistry()
    interpreters.register(AppointmentRequestedV1())
    await RebuildProjections(
        ledger,
        interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals,
        owners,
    ).execute(tenant_id=tenant)

    after = [
        (c.subject_id, c.reason, c.owner_account_id, c.priority, c.status)
        for c in signals.rows
    ]
    assert after == before


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
