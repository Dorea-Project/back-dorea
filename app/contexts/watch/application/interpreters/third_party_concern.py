"""Interpreter `THIRD_PARTY_CONCERN` — quelqu'un pense à quelqu'un d'autre.

Un seul interpreter pour deux usages qui n'en font qu'un : l'intuition du responsable et le
signalement du membre. La seule différence — le rôle de l'émetteur — **se dissout ici**, dans la
comparaison entre le propriétaire du cas et le déclarant :

| L'émetteur… | Le cas revient à… | Et lit… |
|---|---|---|
| est le propriétaire du cas | lui-même | « Tu as pris l'engagement… » |
| ne l'est pas | au propriétaire | « Quelqu'un de l'église pense à cette personne. » |

Le cas du responsable n'est que le cas général replié sur lui-même. Deux interpreters auraient
divergé dans six mois.

**Le nom du déclarant n'apparaît nulle part**, et il ne peut pas apparaître : cet interpreter ne
sait pas écrire de nom, seulement choisir entre deux phrases fixes. C'est ce qui sépare une
passation d'une dénonciation, et ce n'est pas une consigne de relecture — c'est ce que le code
sait faire.

Le propriétaire est résolu **à l'émission** et voyage dans le payload : un interpreter est pur,
il n'appelle rien. Ce n'est pas une concession — c'est plus juste. Le référent d'il y a six
semaines n'est pas celui d'aujourd'hui, et rejouer le ledger doit rendre exactement ce que le
direct a produit.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.concern import Nuance, quote
from app.contexts.watch.domain.effects import CasePriority, OpenCase, ProposedEffect
from app.contexts.watch.domain.facts import Fact, FactKind

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)

# Les deux seules phrases que cette source sait produire. Aucune n'est genrée et aucune ne nomme
# quiconque : le motif est stocké tel quel et voyagera jusqu'à l'écran sans être recalculé.
SELF_ENGAGEMENT = "Tu as pris l'engagement de prendre de ses nouvelles."
SOMEONE_THINKS_OF_THEM = "Quelqu'un de l'église pense à cette personne."


def _owner_of(fact: Fact) -> UUID | None:
    owner = fact.payload.get("owner_account_id")
    return UUID(str(owner)) if owner else None


class ThirdPartyConcernV1:
    kind = FactKind.THIRD_PARTY_CONCERN
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        owner = _owner_of(fact)
        emitter = fact.consent.given_by if fact.consent is not None else None
        raw = fact.payload.get("nuance")
        nuance = Nuance(raw) if raw else None

        # Le seul usage de l'identité du déclarant dans tout l'aval : un test d'égalité, dont il
        # ne sort qu'un booléen. Rien de ce qui est écrit ensuite ne permet de la retrouver.
        engaged_himself = owner is not None and owner == emitter
        reason = SELF_ENGAGEMENT if engaged_himself else SOMEONE_THINKS_OF_THEM

        return [
            OpenCase(
                subject_id=fact.subject_id,
                reason=reason + quote(nuance),
                origin=CasePriority.CONCERN,  # soumise au plafond, contrairement au déclaré
                opened_at=fact.occurred_at,
                owner_account_id=owner,
            )
        ]
