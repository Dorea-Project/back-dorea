"""Le Rendez-vous comme **source** du moteur de veille — il émet, il ne décide pas.

Le module d'agenda se terminait sur lui-même : une demande produisait un créneau, et les chemins
d'échec — décliné, annulé, non honoré — disparaissaient sans laisser de trace. Ce sont pourtant
eux qui portent le plus d'information.

**Le fait est émis à la demande, pas à la confirmation du créneau.** L'information de veille
naît quand quelqu'un demande ; l'enregistrer trois jours plus tard, c'est perdre l'antériorité
qui fait toute la valeur du canal — la preuve que le produit a vu venir avant de calculer.

**Un walk-in n'émet rien.** Sans compte, il n'y a pas de sujet de veille : le fait n'aurait
personne sur qui porter. Le rendez-vous existe quand même, il vit dans l'agenda.

**Le sujet écrit par le membre ne suit jamais.** Seule la note, s'il en a écrit une en sachant
qu'elle serait transmise, voyage avec le fait.

**La demande n'ouvre aucun cas** (décision du 30/07/2026). Le devoir de répondre à quelqu'un qui a
levé la main est déjà tenu par `scripts/relay_appointments.py` et `WatchParam.RELAY_DELAY_HOURS` :
un cas de plus, c'était deux mécanismes pour une seule obligation, dont un qui laissait lire au
responsable de cellule que son membre voulait voir un pasteur. Le **fait reste au ledger** — on ne
perd ni l'antériorité, ni la narration d'épisode, ni le déterminisme du rejeu.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.enums import AppointmentStatus
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpreters.appointment_requested import (
    AppointmentState,
)
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import APPOINTMENTS

_FACT_NAMESPACE = uuid5(NAMESPACE_URL, "dorea:watch:appointment")


def fact_id_for(appointment_id: UUID, state: AppointmentState) -> UUID:
    """Identité **dérivée** de (rendez-vous, état) : rejouer une transition ne duplique rien."""
    return uuid5(_FACT_NAMESPACE, f"{appointment_id}:{state.value}")


def state_of(appointment: Appointment) -> AppointmentState | None:
    """L'état de veille correspondant, ou None si cette transition ne dit rien au moteur.

    `CONFIRMED` n'y figure pas : poser un créneau n'apprend rien de nouveau sur la personne —
    c'est notre organisation, pas son mouvement à elle."""
    match appointment.status:
        case AppointmentStatus.REQUESTED:
            return AppointmentState.REQUESTED
        case AppointmentStatus.DECLINED:
            return AppointmentState.DECLINED
        case AppointmentStatus.ORIENTED:
            return AppointmentState.ORIENTED
        case AppointmentStatus.NO_SHOW:
            return AppointmentState.NO_SHOW
        case AppointmentStatus.COMPLETED:
            return AppointmentState.HONORED
        case AppointmentStatus.CANCELLED:
            # Seul le **demandeur** qui recule est un signal. L'église qui ferme un rendez-vous
            # caduc range son agenda, elle ne dit rien de la personne.
            return (
                AppointmentState.CANCELLED_BY_MEMBER
                if appointment.cancelled_by_requester
                else None
            )
        case _:
            return None


class EmitAppointmentFacts:
    def __init__(self, intake: Intake | None, *, clock) -> None:
        self._intake = intake
        self._clock = clock

    async def execute(self, appointment: Appointment) -> bool:
        """Fait entrer l'état courant du rendez-vous. Renvoie True s'il a été admis."""
        if self._intake is None or appointment.requester_account_id is None:
            return False  # walk-in sans compte : aucun sujet de veille

        state = state_of(appointment)
        if state is None:
            return False

        payload: dict[str, object] = {
            "appointment_id": str(appointment.id),
            "state": state.value,
            "actor_account_id": str(appointment.requester_account_id),
        }
        # **Le destinataire du cas voyage avec le fait.** C'est ce qui permet à l'interpreter de
        # rester pur tout en adressant le cas exactement : le pasteur à qui *cette* main était
        # tendue, et celui qui a réellement décliné — pas un détenteur de rôle choisi par une
        # cascade, et surtout pas le responsable de cellule, qui n'a rien demandé et n'a rien
        # décliné.
        if appointment.with_pastor_account_id is not None:
            payload["pastor_account_id"] = str(appointment.with_pastor_account_id)
        if appointment.handled_by_account_id is not None:
            payload["handled_by_account_id"] = str(appointment.handled_by_account_id)
        if appointment.note:
            payload["note"] = appointment.note
        if state is AppointmentState.DECLINED and appointment.decision_note:
            payload["motive"] = appointment.decision_note

        result = await self._intake.submit(
            Fact(
                fact_id=fact_id_for(appointment.id, state),
                tenant_id=appointment.tenant_id,
                # La demande est datée du geste ; les issues, du moment où elles surviennent.
                occurred_at=(
                    appointment.created_at
                    if state is AppointmentState.REQUESTED
                    else appointment.updated_at
                ),
                recorded_at=self._clock(),
                source=APPOINTMENTS,
                kind=FactKind.APPOINTMENT_REQUESTED,
                subject_kind=SubjectKind.PERSON,
                subject_id=appointment.requester_account_id,
                payload=payload,
            )
        )
        return result.accepted
