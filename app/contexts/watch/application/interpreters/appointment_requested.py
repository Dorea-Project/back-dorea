"""Interpreter `APPOINTMENT_REQUESTED` — un rendez-vous demandé est **une main levée**.

L'agenda n'est que ce qui se passe après. Ce qui compte pour la veille, ce sont les chemins que
le module d'agenda perdait : décliné, réorienté, annulé par le demandeur, non honoré. Ils
portent bien plus d'information qu'un créneau posé.

**L'annulation par le demandeur est le signal le plus urgent que ce moteur sache produire.**
Quelqu'un a franchi le pas le plus difficile — demander — puis a fait demi-tour. Rien d'autre
dans le produit ne dit cela.

Quatre règles portées ici :

- **Origine `DECLARED` partout.** C'est la personne elle-même qui a parlé, à tous les états qui
  en découlent. Le déclaré est exempt du plafond de débit : on ne fait pas attendre quelqu'un
  qui a levé la main.
- **Aucun état ne ferme le cas.** Planifier n'est pas rencontrer, rencontrer n'est pas résoudre.
  `HONORED` annote ; un humain ferme. Sans cette règle, on obtiendrait un excellent taux de
  résolution et personne de rencontré — la même erreur que le retour qui fermait le deuil.
- **La demande n'ouvre rien** (30/07/2026). Elle reste au ledger, et le devoir d'y répondre est
  déjà tenu par le relais. Un cas ouvert sur *« A demandé à rencontrer un pasteur. « … » »*
  finissait, faute de destinataire, sur le responsable de cellule du membre — qui lisait le sujet
  au passage. Le cas d'usage le plus légitime était le pire : quelqu'un en conflit avec son
  responsable demande le pasteur, et c'est ce responsable qui reçoit le cas.
- **Chaque issue d'échec nomme son destinataire.** Le pasteur à qui la main était tendue pour une
  annulation ou un lapin ; qui tient l'agenda pour un refus. L'interpreter reste pur : la source
  joint l'identité au fait, et l'interpreter ne renvoie qu'un titre en repli.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import (
    CasePriority,
    EnrichCase,
    OpenCase,
    OwnerKind,
    ProposedEffect,
)
from app.contexts.watch.domain.facts import Fact, FactKind
from app.contexts.watch.domain.signal import spoken_date

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

        # La demande entre au ledger et n'ouvre rien : le devoir de répondre est tenu par le
        # relais, et le sujet de la demande n'a rien à faire sur l'écran d'un tiers.
        if appointment_state is AppointmentState.REQUESTED:
            return []

        opening = _OPENINGS.get(appointment_state)
        if opening is not None:
            reason, owner_kind = opening
            if appointment_state is AppointmentState.DECLINED:
                motive = (fact.payload.get("motive") or "").strip()
                reason = f"{reason} {motive}".strip() if motive else reason
            return [
                OpenCase(
                    subject_id=fact.subject_id,
                    reason=reason,
                    origin=CasePriority.DECLARED,
                    opened_at=fact.occurred_at,
                    # Le destinataire est celui que la **source** désigne ; le titre n'est qu'un
                    # repli, résolu hors de cet interpreter (étage 02bis).
                    owner_account_id=_owner_from(fact, owner_kind),
                    owner_kind=owner_kind,
                )
            ]

        annotation, priority = _ANNOTATIONS[appointment_state]
        if appointment_state is AppointmentState.HONORED:
            annotation = f"{annotation} le {spoken_date(fact.occurred_at)}."

        return [
            EnrichCase(
                subject_id=fact.subject_id,
                reason=annotation,
                origin=CasePriority.DECLARED,
                annotation=annotation,
                priority=priority,
            )
        ]


# Les trois issues qui **ouvrent** un cas, et à qui il revient. Le texte est écrit ici une fois et
# voyage tel quel jusqu'à l'écran : un responsable lit une phrase, pas un code d'état.
#
# Si la personne a déjà un cas ouvert, l'arbitrage fusionne : la phrase s'ajoute à sa fiche et
# l'urgence remonte. Rien n'est dupliqué, rien n'est perdu.
_OPENINGS: dict[AppointmentState, tuple[str, OwnerKind]] = {
    # Il a demandé de l'aide, puis a reculé. Rien de plus urgent dans tout le produit — et ça
    # revient au pasteur à qui la main avait été tendue, pas à son responsable de cellule.
    AppointmentState.CANCELLED_BY_MEMBER: (
        "A annulé le rendez-vous qu'il avait demandé.",
        OwnerKind.PASTOR,
    ),
    AppointmentState.NO_SHOW: (
        "N'est pas venu au rendez-vous qu'il avait demandé.",
        OwnerKind.PASTOR,
    ),
    # Il a demandé, on n'a pas pu. C'est **notre** dette, et elle appartient à qui tient
    # l'agenda : le référent n'a rien décliné.
    AppointmentState.DECLINED: ("Rendez-vous décliné :", OwnerKind.AGENDA_KEEPER),
}

# Ce qui n'ouvre rien mais annote : le cas existe déjà (ou il n'y a pas lieu d'en ouvrir un).
_ANNOTATIONS: dict[AppointmentState, tuple[str, CasePriority | None]] = {
    # Servi autrement : changement de main, pas fermeture.
    AppointmentState.ORIENTED: ("Orienté vers un accompagnement.", None),
    # Le rendez-vous a eu lieu. Ça n'a rien résolu en soi — un humain jugera.
    AppointmentState.HONORED: ("Rendez-vous honoré", None),
}

# Quel champ du payload porte le destinataire, selon le titre auquel il est appelé.
_OWNER_KEYS: dict[OwnerKind, str] = {
    OwnerKind.PASTOR: "pastor_account_id",
    OwnerKind.AGENDA_KEEPER: "handled_by_account_id",
}


def _owner_from(fact: Fact, kind: OwnerKind) -> UUID | None:
    """Le destinataire désigné par la source, ou None — l'étage 02bis prendra le relais."""
    value = fact.payload.get(_OWNER_KEYS[kind])
    return UUID(str(value)) if value else None
