"""Interpreter `APPOINTMENT_REQUESTED` — un rendez-vous demandé est **une main levée**.

L'agenda n'est que ce qui se passe après. Ce qui compte pour la veille, ce sont les chemins que
le module d'agenda perdait : décliné, réorienté, annulé par le demandeur, non honoré. Ils
portent bien plus d'information qu'un créneau posé.

**L'annulation par le demandeur est le signal le plus urgent que ce moteur sache produire.**
Quelqu'un a franchi le pas le plus difficile — demander — puis a fait demi-tour. Rien d'autre
dans le produit ne dit cela.

Deux règles portées ici :

- **Origine `DECLARED` partout.** C'est la personne elle-même qui a parlé, à tous les états qui
  en découlent. Le déclaré est exempt du plafond de débit : on ne fait pas attendre quelqu'un
  qui a levé la main.
- **Aucun état ne ferme le cas.** Planifier n'est pas rencontrer, rencontrer n'est pas résoudre.
  `HONORED` annote ; un humain ferme. Sans cette règle, on obtiendrait un excellent taux de
  résolution et personne de rencontré — la même erreur que le retour qui fermait le deuil.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import (
    CasePriority,
    EnrichCase,
    OpenCase,
    ProposedEffect,
)
from app.contexts.watch.domain.facts import Fact, FactKind

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


class AppointmentState(StrEnum):
    """L'état porté par le payload. Aucun nouveau `FactKind` : le contrat n'a pas bougé."""

    REQUESTED = "requested"
    DECLINED = "declined"
    ORIENTED = "oriented"
    CANCELLED_BY_MEMBER = "cancelled_by_member"
    NO_SHOW = "no_show"
    HONORED = "honored"


class AppointmentRequestedV1:
    kind = FactKind.APPOINTMENT_REQUESTED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        appointment_state = AppointmentState(fact.payload["state"])
        note = (fact.payload.get("note") or "").strip()

        if appointment_state is AppointmentState.REQUESTED:
            reason = "A demandé à rencontrer un pasteur."
            if note:
                reason = f"{reason} « {note} »"
            return [
                OpenCase(
                    subject_id=fact.subject_id,
                    reason=reason,
                    origin=CasePriority.DECLARED,
                    opened_at=fact.occurred_at,
                )
            ]

        annotation, priority = _ANNOTATIONS[appointment_state]
        if appointment_state is AppointmentState.DECLINED:
            motive = (fact.payload.get("motive") or "").strip()
            annotation = f"{annotation} {motive}".strip() if motive else annotation
        if appointment_state is AppointmentState.HONORED:
            annotation = f"{annotation} le {fact.occurred_at.date().isoformat()}."

        return [
            EnrichCase(
                subject_id=fact.subject_id,
                reason=annotation,
                origin=CasePriority.DECLARED,
                annotation=annotation,
                priority=priority,
            )
        ]


# Ce que chaque issue **dit**, et ce qu'elle change à l'urgence. Le texte est écrit ici une fois
# et voyage tel quel jusqu'à l'écran : un responsable lit une phrase, pas un code d'état.
_ANNOTATIONS: dict[AppointmentState, tuple[str, CasePriority | None]] = {
    # Il a demandé de l'aide, puis a reculé. Rien de plus urgent dans tout le produit.
    AppointmentState.CANCELLED_BY_MEMBER: (
        "A annulé le rendez-vous qu'il avait demandé.",
        CasePriority.DECLARED,
    ),
    AppointmentState.NO_SHOW: (
        "N'est pas venu au rendez-vous qu'il avait demandé.",
        CasePriority.DECLARED,
    ),
    # Il a demandé, on n'a pas pu. C'est **notre** dette : le cas reste ouvert et retombe sur
    # le référent — on ne renvoie pas quelqu'un qui a levé la main.
    AppointmentState.DECLINED: ("Rendez-vous décliné :", None),
    # Servi autrement : changement de main, pas fermeture.
    AppointmentState.ORIENTED: ("Orienté vers un accompagnement.", None),
    # Le rendez-vous a eu lieu. Ça n'a rien résolu en soi — un humain jugera.
    AppointmentState.HONORED: ("Rendez-vous honoré", None),
}
