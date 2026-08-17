"""Le relais — une demande sans réponse ne reste jamais silencieuse.

Une main levée à laquelle personne ne répond est pire qu'un canal fermé. Le relais est ce qui
empêche ça, et il obéit à trois règles :

- **Nominatif.** On ne libère jamais une demande, on la **transfère**. Une demande sans
  destinataire est une demande que personne ne traite, et personne ne s'en aperçoit.
- **Motivé.** Le motif est stocké et voyage avec elle : un pasteur qui reçoit une demande sans
  savoir pourquoi elle lui arrive l'ignore.
- **Borné.** Deux relais infructueux ne sont plus un problème de délai : c'est un **défaut de
  dispositif**, et ça se dit à l'admin. Pas une troisième relance.

Et il ne fait jamais attendre inutilement : une absence **déclarée** est connue d'avance, donc
contournée tout de suite (`resolve_assigned_pastor` consulte la disponibilité à chaque étage).
Le délai ne sert qu'à constater un **oubli**, qui lui ne se déclare pas.

**`DO_NOT_CONTACT`** est honoré ici : une demande en attente d'une personne qui a demandé qu'on
cesse de la contacter est annulée **sans notification** — la prévenir serait précisément le
contact qu'elle a refusé. Cela n'empêche pas cette personne de redemander elle-même : son retrait
nous interdit d'aller vers elle, il ne lui interdit pas de venir vers nous.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app._shared.messages import MessageKey
from app.contexts.appointments.application.assigned_pastor import ResolveAssignedPastor
from app.contexts.appointments.domain.repositories import AppointmentRepository
from app.contexts.notifications.application.notifier import Notifier, PushNotification
from app.contexts.watch.application.ports import SignalStore
from app.contexts.watch.application.referent_ports import (
    CoverageGapStore,
    PeopleDirectory,
    WatchParameterRepository,
)
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import CoverageGap, CoverageScope
from app.contexts.watch.domain.parameters import WatchParam


@dataclass(frozen=True)
class RelayReport:
    examined: int = 0
    relayed: int = 0
    gaps: int = 0  # défauts de dispositif remontés à l'admin
    withdrawn: int = 0  # demandes closes parce que la personne s'est retirée du contact


class RouteAppointment:
    """Adresse une demande à son destinataire, à la création comme au relais."""

    def __init__(self, pastors: ResolveAssignedPastor) -> None:
        self._pastors = pastors

    async def initial(self, appointment, *, at: datetime) -> UUID | None:
        assigned = await self._pastors.execute(
            person_id=appointment.requester_account_id,
            tenant_id=appointment.tenant_id,
            at=at,
        )
        if assigned is None:
            return None
        appointment.route_to(account_id=assigned.account_id, at=at)
        return assigned.account_id


class RelayUnansweredRequests:
    """Passe nocturne : rien de ce qui attend ne doit rester muet."""

    def __init__(
        self,
        appointments: AppointmentRepository,
        pastors: ResolveAssignedPastor,
        people: PeopleDirectory,
        params: WatchParameterRepository,
        gaps: CoverageGapStore,
        signals: SignalStore | None = None,
        notifier: Notifier | None = None,
        *,
        clock,
    ) -> None:
        self._appointments = appointments
        self._pastors = pastors
        self._people = people
        self._params = params
        self._gaps = gaps
        self._signals = signals
        self._notifier = notifier
        self._clock = clock

    async def execute(self, *, tenant_id: UUID) -> RelayReport:
        now = self._clock()
        delay = timedelta(
            hours=await self._params.get_int(tenant_id, WatchParam.RELAY_DELAY_HOURS)
        )
        limit = await self._params.get_int(
            tenant_id, WatchParam.RELAY_ATTEMPTS_BEFORE_GAP
        )
        withdrawn_ids = (
            await self._signals.do_not_contact_ids(tenant_id)
            if self._signals is not None
            else set()
        )

        report = RelayReport()
        for appointment in await self._appointments.list_open_for_tenant(tenant_id):
            if not appointment.is_awaiting_answer:
                continue
            report = _bump(report, examined=1)

            # Elle a demandé qu'on cesse de la contacter : on referme, sans rien lui dire.
            if appointment.requester_account_id in withdrawn_ids:
                appointment.cancel(now=now)  # sans `by_account_id` : aucun fait de veille
                await self._appointments.save(appointment)
                report = _bump(report, withdrawn=1)
                continue

            if appointment.waited_since(now) < delay:
                continue

            moved = await self._relay(appointment, now=now, limit=limit)
            report = _bump(report, relayed=int(moved is True), gaps=int(moved is False))

        return report

    async def _relay(self, appointment, *, now: datetime, limit: int) -> bool | None:
        """True = relayée, False = défaut remonté, None = laissée en tête de file."""
        current = appointment.routed_to_account_id
        candidates = await self._people.pastors(appointment.tenant_id)
        for candidate in candidates:
            if candidate == current:
                continue
            assigned = await self._pastors.execute(
                person_id=appointment.requester_account_id,
                tenant_id=appointment.tenant_id,
                at=now,
            )
            # On ne relaie que vers quelqu'un de réellement disponible.
            if assigned is not None and assigned.account_id == candidate:
                appointment.route_to(
                    account_id=candidate,
                    at=now,
                    reason=f"Sans réponse depuis {appointment.waited_since(now).days} jours.",
                )
                await self._appointments.save(appointment)
                await self._tell_the_member(appointment)
                return True

        # Aucun relais possible. **Ne pas échouer silencieusement** : au-delà du seuil, ce n'est
        # plus un problème de délai, c'est que l'église n'a personne pour recevoir.
        if appointment.relay_count >= limit:
            await self._gaps.record_once(
                CoverageGapRecord(
                    id=uuid4(),
                    tenant_id=appointment.tenant_id,
                    scope=CoverageScope.TENANT,
                    gap=CoverageGap.NO_PASTORAL_RELAY,
                    reason=(
                        "Une demande attend depuis "
                        f"{appointment.waited_since(now).days} jours, "
                        "aucun relais pastoral disponible."
                    ),
                    observed_at=now,
                )
            )
            return False
        return None  # elle reste en tête de file, visible — jamais silencieuse

    async def _tell_the_member(self, appointment) -> None:
        """Prévenir **une fois** qu'un autre pasteur le recevra. Avant l'entretien, et sans
        expliquer le relais — ce n'est pas son affaire."""
        if self._notifier is None or appointment.requester_account_id is None:
            return
        await self._notifier.notify(
            [appointment.requester_account_id],
            PushNotification(
                key=MessageKey.APPOINTMENT_RELAY,
                data={"type": "appointment_relay", "id": str(appointment.id)},
            ),
        )


def _bump(report: RelayReport, **deltas: int) -> RelayReport:
    return RelayReport(
        examined=report.examined + deltas.get("examined", 0),
        relayed=report.relayed + deltas.get("relayed", 0),
        gaps=report.gaps + deltas.get("gaps", 0),
        withdrawn=report.withdrawn + deltas.get("withdrawn", 0),
    )
