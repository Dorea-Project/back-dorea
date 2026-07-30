"""Interpreter `SELF_DECLARATION` — quelqu'un a parlé **pour lui-même**.

C'est la seule origine qui passe devant tout et qui n'est **jamais** retenue par le plafond de
débit. On ne fait pas attendre quelqu'un qui a levé la main : c'est l'invariant 7 du moteur, et
c'est ce qui distingue un produit de soin d'un système de tri.

Plusieurs gestes portent ce type de fait — le payload dit lequel :

| `kind` | Le geste |
|---|---|
| `capsule_accepted` | a laissé son contact après une invitation — **une main tendue en retour** |
| `prayer` | a demandé qu'on le porte |
| `contact_request` | a demandé qu'on l'appelle |
| `rhythm` | a choisi la cadence à laquelle on prend de ses nouvelles |

Aucun de ces gestes n'est déduit d'un contenu : le membre choisit lui-même le bouton. Router
selon ce qu'il aurait écrit serait de l'analyse de contenu — l'interdit fondateur, et il n'est
pas contournable par une astuce technique.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import (
    CancelScheduledChecks,
    CasePriority,
    OpenCase,
    ProposedEffect,
    ScheduleCheck,
)
from app.contexts.watch.domain.facts import Fact, FactKind

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


class DeclarationKind(StrEnum):
    CAPSULE_ACCEPTED = "capsule_accepted"
    PRAYER = "prayer"
    CONTACT_REQUEST = "contact_request"
    RHYTHM = "rhythm"


# Ce que chaque geste dit, en clair, une fois pour toutes. La phrase voyage telle quelle
# jusqu'à l'écran du responsable : il lit une personne, pas un code d'état.
_REASONS: dict[DeclarationKind, str] = {
    DeclarationKind.CAPSULE_ACCEPTED: "A répondu à une invitation et laissé son contact.",
    DeclarationKind.PRAYER: "A demandé la prière.",
    DeclarationKind.CONTACT_REQUEST: "A demandé qu'on l'appelle.",
}


class SelfDeclarationV1:
    kind = FactKind.SELF_DECLARATION
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        declaration = DeclarationKind(fact.payload["kind"])

        # Choisir son rythme n'ouvre pas un cas : ça règle la cadence des relances.
        if declaration is DeclarationKind.RHYTHM:
            return _rhythm(fact)

        reason = _REASONS[declaration]
        note = (fact.payload.get("note") or "").strip()
        if note:
            reason = f"{reason} « {note} »"

        return [
            OpenCase(
                subject_id=fact.subject_id,
                reason=reason,
                origin=CasePriority.DECLARED,  # exempt du plafond, toujours
                opened_at=fact.occurred_at,
            )
        ]


# Le rythme qu'un membre choisit pour lui-même. `ON_DEMAND` n'est pas « moins de suivi » : c'est
# quelqu'un qui dit *« je vous appellerai »*, et le produit doit savoir l'entendre.
ON_DEMAND = "on_demand"
RHYTHM_KIND = "rhythm"


def _rhythm(fact: Fact) -> Sequence[ProposedEffect]:
    """« Ne me relancez plus » coupe les échéances ; un rythme choisi en pose une.

    Sans l'annulation, le membre qui reprend la main sur son propre rythme continuerait de
    recevoir ce qu'il vient précisément de demander d'arrêter."""
    if fact.payload.get("cadence") == ON_DEMAND:
        return [
            CancelScheduledChecks(
                subject_id=fact.subject_id,
                reason="A choisi d'être recontacté à sa demande.",
                kind=RHYTHM_KIND,
            )
        ]

    every_days = fact.payload.get("every_days")
    if not every_days:
        return []
    return [
        ScheduleCheck(
            subject_id=fact.subject_id,
            reason=f"Rythme choisi : prendre de ses nouvelles tous les {every_days} jours.",
            at=fact.occurred_at + timedelta(days=int(every_days)),
            kind=RHYTHM_KIND,
        )
    ]
