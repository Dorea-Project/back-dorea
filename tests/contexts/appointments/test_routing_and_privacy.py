"""Routage, relais, et le cloisonnement qui rend le canal privé.

Deux garanties se testent ici :

- **une demande sans réponse ne reste jamais silencieuse** — elle est relayée, ou son échec
  remonte à l'admin ;
- **le secrétariat ne voit jamais une demande en attente ni son motif** — sinon « on sait qu'il
  a demandé » circule dans l'église, et le coût social que le canal venait de supprimer revient
  par la porte administrative.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.appointments.application.assigned_pastor import (
    AssignedPastor,
    ResolveAssignedPastor,
)
from app.contexts.appointments.application.dtos import AgendaEntryDTO
from app.contexts.appointments.application.mapping import to_agenda_entry_dto
from app.contexts.appointments.application.queries.list_appointments import (
    ListMyPendingRequests,
)
from app.contexts.appointments.application.relay import (
    RelayUnansweredRequests,
    RouteAppointment,
)
from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.enums import AppointmentCategory, AppointmentStatus
from app.contexts.appointments.domain.repositories import AppointmentRepository
from app.contexts.watch.application.referent_ports import (
    CoverageGapStore,
    PeopleDirectory,
    WatchParameterRepository,
)
from app.contexts.watch.domain.effects import CoverageGap
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


# --- fakes -------------------------------------------------------------------------------


class _Appointments(AppointmentRepository):
    def __init__(self, rows=()):
        self.rows = list(rows)

    async def add(self, appointment):
        self.rows.append(appointment)

    async def get(self, appointment_id):
        return next((a for a in self.rows if a.id == appointment_id), None)

    async def save(self, appointment):
        pass  # agrégat muté en mémoire

    async def list_by_requester(self, account_id, tenant_id):
        return [a for a in self.rows if a.requester_account_id == account_id]

    async def list_open_for_tenant(self, tenant_id):
        return [a for a in self.rows if a.tenant_id == tenant_id]

    async def list_confirmed_between(self, tenant_id, frm, to):
        return []


class _People(PeopleDirectory):
    def __init__(self, pastors=()):
        self._pastors = list(pastors)

    async def is_eligible(self, account_id, tenant_id):
        return True

    async def member_since(self, account_id, tenant_id):
        return None

    async def church_admin(self, tenant_id):
        return None

    async def pastor(self, tenant_id):
        return self._pastors[0] if self._pastors else None

    async def pastors(self, tenant_id):
        return list(self._pastors)


class _Params(WatchParameterRepository):
    def __init__(self, overrides=None):
        self._o = overrides or {}

    async def get_int(self, tenant_id, param):
        return self._o.get(param, DEFAULTS[param])


class _Gaps(CoverageGapStore):
    def __init__(self):
        self.rows = []

    async def record_once(self, record):
        if any(r.gap is record.gap and r.is_open for r in self.rows):
            return False
        self.rows.append(record)
        return True

    async def open_gaps(self, tenant_id):
        return [r for r in self.rows if r.is_open]


class _Signals:
    def __init__(self, withdrawn=()):
        self._w = set(withdrawn)

    async def do_not_contact_ids(self, tenant_id):
        return set(self._w)


class _Pastors(ResolveAssignedPastor):
    """Doublure de la cascade : on contrôle qui est disponible, quand."""

    def __init__(self, available=None):
        self._available = list(available or [])

    async def execute(self, *, person_id, tenant_id, at):
        return AssignedPastor(self._available[0], "church") if self._available else None


def _requested(*, tenant, member, note="J'ai besoin de parler") -> Appointment:
    return Appointment.request(
        id=uuid4(), tenant_id=tenant, requester_account_id=member,
        subject="Un entretien confidentiel", category=AppointmentCategory.COUNSEL,
        now=_NOW, note=note,
    )


def _relay(appointments, *, pastors, people, gaps, params=None, signals=None, now=_NOW):
    return RelayUnansweredRequests(
        appointments, pastors, people, params or _Params(), gaps,
        signals or _Signals(), None, clock=lambda: now,
    )


# --- Le routage à la demande ---------------------------------------------------------------


async def test_a_request_is_addressed_to_someone_immediately():
    """Une absence déclarée est connue d'avance : on contourne tout de suite, sans attendre."""
    tenant, member, pastor = uuid4(), uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=member)

    await RouteAppointment(_Pastors([pastor])).initial(appointment, at=_NOW)

    assert appointment.routed_to_account_id == pastor
    assert appointment.routed_at == _NOW
    assert appointment.relay_count == 0


async def test_a_church_with_no_available_pastor_leaves_the_request_unrouted():
    """On n'invente pas de destinataire — mais la demande existe, et le relais la reprendra."""
    appointment = _requested(tenant=uuid4(), member=uuid4())

    await RouteAppointment(_Pastors([])).initial(appointment, at=_NOW)

    assert appointment.routed_to_account_id is None


# --- Le relais ------------------------------------------------------------------------------


async def test_nothing_moves_before_the_delay():
    """Le délai ne sert qu'à constater un **oubli** — qui, lui, ne se déclare pas."""
    tenant, member, first = uuid4(), uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=member)
    appointment.route_to(account_id=first, at=_NOW)
    repo, gaps = _Appointments([appointment]), _Gaps()

    report = await _relay(
        repo, pastors=_Pastors([uuid4()]), people=_People([first, uuid4()]), gaps=gaps,
        now=_NOW + timedelta(hours=12),
    ).execute(tenant_id=tenant)

    assert report.relayed == 0
    assert appointment.routed_to_account_id == first


async def test_an_unanswered_request_is_relayed_nominatively_with_a_stored_reason():
    """On ne libère jamais une demande, on la transfère — et le motif voyage avec elle."""
    tenant, member, first, second = uuid4(), uuid4(), uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=member)
    appointment.route_to(account_id=first, at=_NOW)
    repo, gaps = _Appointments([appointment]), _Gaps()

    report = await _relay(
        repo, pastors=_Pastors([second]), people=_People([first, second]), gaps=gaps,
        now=_NOW + timedelta(hours=72),
    ).execute(tenant_id=tenant)

    assert report.relayed == 1
    assert appointment.routed_to_account_id == second  # nominatif, jamais « libérée »
    assert appointment.relay_count == 1
    assert "Sans réponse depuis" in appointment.relay_reason


async def test_two_failed_relays_become_a_coverage_gap_not_a_third_reminder():
    """Ce n'est plus un problème de délai : l'église n'a personne pour recevoir."""
    tenant, member, only = uuid4(), uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=member)
    appointment.route_to(account_id=only, at=_NOW)
    appointment.relay_count = 2  # deux relais déjà tentés
    repo, gaps = _Appointments([appointment]), _Gaps()

    report = await _relay(
        repo, pastors=_Pastors([only]), people=_People([only]), gaps=gaps,
        now=_NOW + timedelta(hours=72),
    ).execute(tenant_id=tenant)

    assert report.gaps == 1
    (gap,) = await gaps.open_gaps(tenant)
    assert gap.gap is CoverageGap.NO_PASTORAL_RELAY
    assert "aucun relais pastoral disponible" in gap.reason


async def test_before_the_threshold_the_request_stays_visible_never_silent():
    """Elle reste en tête de file. Le pire serait qu'elle disparaisse sans que rien ne le dise."""
    tenant, only = uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=uuid4())
    appointment.route_to(account_id=only, at=_NOW)
    repo, gaps = _Appointments([appointment]), _Gaps()

    report = await _relay(
        repo, pastors=_Pastors([only]), people=_People([only]), gaps=gaps,
        now=_NOW + timedelta(hours=72),
    ).execute(tenant_id=tenant)

    assert (report.relayed, report.gaps) == (0, 0)
    assert appointment.status is AppointmentStatus.REQUESTED  # toujours là


async def test_the_delay_is_a_parameter_not_a_constant():
    """48 h est long dans une grande église ; dans une petite, deux jours ne sont pas un oubli."""
    tenant, first, second = uuid4(), uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=uuid4())
    appointment.route_to(account_id=first, at=_NOW)
    repo, gaps = _Appointments([appointment]), _Gaps()

    report = await _relay(
        repo, pastors=_Pastors([second]), people=_People([first, second]), gaps=gaps,
        params=_Params({WatchParam.RELAY_DELAY_HOURS: 6}),
        now=_NOW + timedelta(hours=8),
    ).execute(tenant_id=tenant)

    assert report.relayed == 1  # 8 h > 6 h, alors que le défaut de 48 h n'aurait rien fait


# --- Le retrait du contact -------------------------------------------------------------------


async def test_a_withdrawn_person_sees_her_pending_request_closed_in_silence():
    """La prévenir serait exactement le contact qu'elle a refusé.

    Une veille dont on ne peut pas sortir est un fichage — et le retrait vaut aussi pour les
    surfaces qui n'appartiennent pas au moteur."""
    tenant, member = uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=member)
    appointment.route_to(account_id=uuid4(), at=_NOW)
    repo, gaps = _Appointments([appointment]), _Gaps()

    report = await _relay(
        repo, pastors=_Pastors([]), people=_People([]), gaps=gaps,
        signals=_Signals({member}), now=_NOW,
    ).execute(tenant_id=tenant)

    assert report.withdrawn == 1
    assert appointment.status is AppointmentStatus.CANCELLED
    # Aucun `by_account_id` : ce n'est pas elle qui annule, donc aucun fait de veille n'est émis.
    assert appointment.cancelled_by_requester is False


async def test_withdrawal_stops_us_reaching_out_not_her_reaching_in():
    """Son retrait nous interdit d'aller vers elle. Il ne lui interdit pas de venir vers nous."""
    tenant, member = uuid4(), uuid4()
    fresh = _requested(tenant=tenant, member=member)  # elle redemande elle-même

    assert fresh.status is AppointmentStatus.REQUESTED
    assert fresh.requester_account_id == member


# --- Le cloisonnement -------------------------------------------------------------------------


def test_the_agenda_entry_type_cannot_carry_a_motive():
    """Ce n'est pas un DTO amputé : c'est un **type** qui ne porte pas les champs sensibles.

    Un filtrage conditionnel s'oublie ; un champ absent ne peut pas fuir."""
    fields = set(AgendaEntryDTO.__dataclass_fields__)

    assert "subject" not in fields
    assert "note" not in fields
    assert "decision_note" not in fields


def test_the_agenda_shows_a_slot_and_nothing_of_what_was_written():
    appointment = _requested(tenant=uuid4(), member=uuid4(), note="Ma vie conjugale")
    appointment.confirm(at=_NOW + timedelta(days=2), by_account_id=uuid4(), now=_NOW)

    entry = to_agenda_entry_dto(appointment)

    assert entry.scheduled_at == _NOW + timedelta(days=2)
    assert "Ma vie conjugale" not in str(entry)
    assert "Un entretien confidentiel" not in str(entry)


async def test_a_pending_request_belongs_to_its_recipient_alone():
    """Aucune permission d'église n'ouvre cette file : c'est le routage qui décide."""
    tenant, member, mine, someone_else = uuid4(), uuid4(), uuid4(), uuid4()
    a = _requested(tenant=tenant, member=member)
    a.route_to(account_id=mine, at=_NOW)
    b = _requested(tenant=tenant, member=uuid4())
    b.route_to(account_id=someone_else, at=_NOW)
    repo = _Appointments([a, b])

    mine_only = await ListMyPendingRequests(repo).execute(
        actor_account_id=mine, tenant_id=tenant
    )

    assert [d.id for d in mine_only] == [a.id]


async def test_a_confirmed_appointment_leaves_the_pending_queue():
    """Une fois le créneau posé, ce n'est plus une demande : c'est l'agenda qui la porte."""
    tenant, mine = uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=uuid4())
    appointment.route_to(account_id=mine, at=_NOW)
    appointment.confirm(at=_NOW + timedelta(days=1), by_account_id=mine, now=_NOW)

    remaining = await ListMyPendingRequests(_Appointments([appointment])).execute(
        actor_account_id=mine, tenant_id=tenant
    )

    assert remaining == []


def test_visibility_is_the_requester_and_the_recipient_only():
    tenant, member, recipient, secretary = uuid4(), uuid4(), uuid4(), uuid4()
    appointment = _requested(tenant=tenant, member=member)
    appointment.route_to(account_id=recipient, at=_NOW)

    assert appointment.visible_to(member) is True
    assert appointment.visible_to(recipient) is True
    assert appointment.visible_to(secretary) is False
