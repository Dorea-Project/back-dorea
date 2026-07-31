"""Interpreter des **gestes du responsable** — ce qu'un humain a fait sur un cas.

Le journal ne contenait que ce que les sources disent du monde. Ce qu'un responsable *faisait* —
ouvrir un cas, le fermer avec une issue — vivait uniquement sur la projection, donc une
reprojection l'effaçait sans pouvoir le reconstruire. On perdait les issues qu'il avait conclues,
le premier regard, la chaîne d'épisode qui évite de rappeler quelqu'un en repartant de zéro : très
exactement la trace du soin apporté, au nom de la réparation.

**Le geste vise la personne, pas un identifiant de cas.** Un rejeu recrée les cas avec de nouveaux
identifiants ; un effet qui pointerait vers l'ancien ne retrouverait rien. Il y a au plus un cas
vivant par personne — c'est un invariant de l'arbitrage — et c'est celui-là qu'on vise. Le
`signal_id` voyage quand même dans le payload : il ne sert pas à retrouver le cas, il sert à
raconter lequel a été fermé, ce jour-là.

**L'interpreter ne rejoue aucune règle.** Il ne vérifie ni l'autorité (faite à l'émission, par
`_OwnedCase`), ni la légitimité de la transition : c'est l'agrégat `Signal` qui refuse tout seul
une clôture sans humain, une issue absorbante déjà posée, une transition qui n'existe pas.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import MarkCaseSeen, ProposedEffect, ResolveCase
from app.contexts.watch.domain.facts import Fact, FactKind

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


def _actor(fact: Fact) -> UUID:
    return UUID(str(fact.payload["actor_account_id"]))


class CaseSeenV1:
    kind = FactKind.CASE_SEEN
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        return [
            MarkCaseSeen(
                subject_id=fact.subject_id,
                reason="Le cas a été ouvert par son destinataire.",
                at=fact.occurred_at,
                by_account_id=_actor(fact),
            )
        ]


class CaseClosedV1:
    kind = FactKind.CASE_CLOSED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        return [
            ResolveCase(
                subject_id=fact.subject_id,
                reason="Le cas a été fermé, avec une issue choisie.",
                at=fact.occurred_at,
                by_account_id=_actor(fact),
                outcome=str(fact.payload["outcome"]),
            )
        ]
