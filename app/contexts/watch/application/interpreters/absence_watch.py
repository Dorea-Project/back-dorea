"""Armer le regard — **une seule définition**, deux façons d'y entrer.

Deux gestes arment la détection d'absence, et ils disent la même chose au moteur : *à partir de
maintenant, quelqu'un est attendu quelque part.*

- **une présence** — elle était là, on regardera si elle revient ;
- **une entrée dans un groupe** — elle vient d'arriver, on regardera si elle vient.

Le second n'est pas un raffinement. Sans lui, seule une présence arme le regard : le nouveau
inscrit qu'on ne revoit jamais reste invisible, alors que c'est précisément la personne qu'il
fallait voir. Le silence de quelqu'un qui n'est jamais venu est le plus difficile à entendre, parce
qu'il ne succède à rien.

Le geste est écrit ici une fois pour que les deux interpreters ne puissent pas diverger : le jour
où l'on change ce qu'arme une présence, on change aussi ce qu'arme une adhésion, sans y penser.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.contexts.watch.domain.effects import (
    CancelScheduledChecks,
    ProposedEffect,
    ScheduleCheck,
)
from app.contexts.watch.domain.facts import Fact

# Le régime d'échéance de la détection d'absence.
ABSENCE_WATCH_KIND = "absence_watch"


def arm_absence_watch(fact: Fact, *, reason: str) -> Sequence[ProposedEffect]:
    """Annule le regard précédent et en pose un nouveau, d'après ce que le fait porte.

    La date (`check_absence_at`) et le groupe viennent du **fait** : calculés par la couche
    applicative au moment du geste, d'après le rythme déclaré du groupe, et figés. L'interpreter ne
    lit ni l'horloge ni la cadence — c'est ce qui rend le rejeu identique au direct, même si le
    groupe change de rythme entre-temps.

    Sans ces deux clés, on ne renvoie **rien** : un groupe sans cadence déclarée n'attend personne,
    et on ne pose pas une échéance sur une intuition."""
    due = fact.payload.get("check_absence_at")
    group_id = fact.payload.get("group_id")
    if not due or not group_id:
        return []

    return [
        # D'abord annuler : une seule échéance d'absence à la fois par personne. Sans ça, une
        # personne revenue en février recevrait quand même le regard programmé en janvier.
        CancelScheduledChecks(
            subject_id=fact.subject_id,
            reason="Un nouveau regard remplace le précédent.",
            kind=ABSENCE_WATCH_KIND,
        ),
        ScheduleCheck(
            subject_id=fact.subject_id,
            reason=reason,
            at=datetime.fromisoformat(str(due)),
            kind=ABSENCE_WATCH_KIND,
            # Ce que le tir aura besoin de savoir : depuis quand, et dans quel groupe.
            payload={"group_id": str(group_id), "since": fact.occurred_at.isoformat()},
        ),
    ]
