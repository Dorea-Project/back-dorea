"""Interpreter `PRESENCE_RECORDED` — la personne reparaît.

Sans lui, une neutralisation court jusqu'au bout de sa durée même si l'intéressé est revenu le
troisième jour : on continuerait à l'excuser pendant sept semaines, et l'échéance conclurait
« pas revenu » alors qu'il est là depuis un mois.

Ce qui compte comme retour est décidé en amont, par le **type de fait** : seule une présence
réellement enregistrée émet `PRESENCE_RECORDED`. Réagir à une annonce n'en émet pas — c'est un
signe de vie, pas un retour, et le fil d'actualité n'est pas une source de présence.

Une présence **antérieure** au début de la neutralisation ne prouve rien : elle est simplement
plus vieille que l'événement qui l'a posée.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import (
    Extinguish,
    ExtinguishCause,
    ProposedEffect,
    RecordMemory,
)
from app.contexts.watch.domain.facts import Fact, FactKind

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


class PresenceRecordedV1:
    kind = FactKind.PRESENCE_RECORDED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        running = [
            n
            for n in state.neutralizations_of(fact.subject_id)
            if fact.occurred_at >= n.starts_at
        ]
        if not running:
            return []

        came_back_on = fact.occurred_at.date().isoformat()
        return [
            Extinguish(
                subject_id=fact.subject_id,
                reason=f"Revenu(e) le {came_back_on}.",
                cause=ExtinguishCause.RETURNED,
                at=fact.occurred_at,  # daté de la rencontre, pas de la saisie
            ),
            # La seule notification positive du produit part de là : elle ne demande rien, ne
            # s'accumule pas, ne se traite pas. Elle attend seulement le référent pour être
            # remise à quelqu'un.
            RecordMemory(
                subject_id=fact.subject_id,
                reason=f"Revenu(e) le {came_back_on}.",
                at=fact.occurred_at,
                item="return_confirmed",
            ),
        ]
