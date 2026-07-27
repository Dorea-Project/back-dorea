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
from datetime import UTC, datetime
from enum import StrEnum

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import CasePriority, OpenCase, ProposedEffect
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

        # Choisir son rythme n'ouvre pas un cas : ça pose une échéance. Elle attend le worker.
        if declaration is DeclarationKind.RHYTHM:
            return []

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
