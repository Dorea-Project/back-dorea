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
from app.contexts.watch.application.interpreters.absence_watch import (
    ABSENCE_WATCH_KIND,
    arm_absence_watch,
)
from app.contexts.watch.domain.effects import (
    Extinguish,
    ExtinguishCause,
    ProposedEffect,
    RecordMemory,
)
from app.contexts.watch.domain.facts import Fact, FactKind
from app.contexts.watch.domain.signal import spoken_date

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)

# Réexporté : le régime d'échéance était nommé ici avant d'être partagé avec l'entrée en groupe.
__all__ = ["ABSENCE_WATCH_KIND", "PresenceRecordedV1", "PresenceRecordedV2"]


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

        # **Cette phrase-là est remise à la personne elle-même**, par la mémoire du
        # lien. Une date ISO dans une consolation serait le comble.
        came_back_on = spoken_date(fact.occurred_at)
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


class PresenceRecordedV2(PresenceRecordedV1):
    """V2 — la présence **repousse** le regard, en plus de constater le retour.

    C'est ici que naît la détection d'absence, et elle naît d'une **parole** : on ne constate
    jamais un silence, on pose un rendez-vous au moment où quelqu'un est là, et c'est ce
    rendez-vous qui, en tombant, regardera ce qui s'est passé depuis.

    **Tant qu'Awa vient, rien ne tombe jamais.** Chaque présence annule l'échéance précédente et en
    pose une nouvelle. L'annulation n'est pas une optimisation : sans elle, une personne revenue en
    février recevrait quand même le regard programmé en janvier.

    La date vient du fait — calculée par la Présence d'après le rythme du groupe, figée à
    l'émission. L'interpreter, lui, ne lit ni l'horloge ni la cadence : c'est ce qui rend le rejeu
    identique au direct, même si le groupe change de rythme entre-temps.
    """

    version = 2
    effective_from = datetime(2026, 7, 30, tzinfo=UTC)

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        return [
            *super().interpret(fact, state),
            *arm_absence_watch(fact, reason="Regarder si cette personne a reparu depuis."),
        ]
