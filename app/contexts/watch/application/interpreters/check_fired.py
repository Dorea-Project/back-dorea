"""Interpreter `CHECK_FIRED` — **le chaînon qui manquait**.

Le worker écrivait des échéances tombées au ledger depuis le premier jour, et aucun interpreter
n'était enregistré pour ce type de fait : le registre renvoyait une liste vide, et le temps entrait
dans le moteur sans jamais rien produire. Toute la mécanique existait — la table, la pose,
l'annulation, le garde anti-orage — et elle tirait dans le vide.

**Pourquoi le temps passe par un fait plutôt que par un service.** Un interpreter ne lit jamais
l'horloge. S'il le faisait, rejouer le journal demain donnerait un autre résultat qu'aujourd'hui, et
l'invariant de déterminisme — celui sur lequel repose toute la reprojection — tomberait sans bruit.
L'échéance qui tombe devient donc un fait comme un autre, daté de son échéance et non de la passe
qui l'a ramassée.

**Ce que cet interpreter n'a pas le droit de faire.** Constater un silence. Rien ici ne dit « cette
personne n'est pas venue » : une échéance qui tombe dit *« le moment de reprendre des nouvelles est
arrivé »*, ce qui est une décision de dispositif, pas une observation sur quelqu'un. La nuance n'est
pas rhétorique — c'est elle qui empêche le produit de devenir un détecteur d'inactivité.

Deux régimes d'échéance aujourd'hui, tous deux nés d'une **parole** :

- `rhythm` — la personne a choisi qu'on prenne de ses nouvelles tous les N jours. L'échéance qui
  tombe ouvre un cas déclaré et **repose la suivante** : un rythme qu'on honore une fois puis qu'on
  oublie est pire que pas de rythme du tout ;
- `return` — un retour attendu après une neutralisation, qui n'est pas venu. Le cas reste ouvert et
  l'échéance ne se repose pas : à un moment, il faut un humain, pas un rappel de plus.

Un régime inconnu ne produit **rien**, et c'est volontaire : une échéance d'un type qu'on ne sait
pas encore lire reste au journal, et une reprojection lui donnera son sens le jour où l'interpreter
arrivera.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.contexts.watch.application.interpretation import WatchStateView
from app.contexts.watch.domain.effects import (
    CasePriority,
    OpenCase,
    ProposedEffect,
    ScheduleCheck,
)
from app.contexts.watch.domain.facts import Fact, FactKind

_GENESIS = datetime(2026, 1, 1, tzinfo=UTC)


class CheckKind(StrEnum):
    """Les régimes d'échéance que le moteur sait poser. Liste close, comme les issues."""

    RHYTHM = "rhythm"  # « prenez de mes nouvelles tous les N jours »
    RETURN = "return"  # un retour attendu qui n'est pas constaté
    ABSENCE_WATCH = "absence_watch"  # la détection d'absence (émetteur au chantier suivant)


class CheckFiredV1:
    kind = FactKind.CHECK_FIRED
    version = 1
    effective_from = _GENESIS

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]:
        check_kind = fact.payload.get("kind")
        reason = (fact.payload.get("reason") or "").strip() or "Échéance de veille arrivée à terme."

        if check_kind == CheckKind.RHYTHM:
            return self._rhythm(fact, reason)
        if check_kind == CheckKind.RETURN:
            return [
                OpenCase(
                    subject_id=fact.subject_id,
                    reason=reason,
                    # L'échéance, pas la personne : c'est le dispositif qui a posé une date, et
                    # cette date est passée. Distincte du déclaré — elle ne vient pas d'une parole
                    # d'aujourd'hui — et plus haute qu'une absence calculée.
                    origin=CasePriority.DEADLINE,
                    opened_at=fact.occurred_at,
                )
            ]
        return []

    def _rhythm(self, fact: Fact, reason: str) -> Sequence[ProposedEffect]:
        """Le rythme choisi par la personne : on ouvre, **et on repose la suivante**.

        La cadence voyage dans le payload de l'échéance, écrite au moment où la personne l'a
        choisie. L'interpreter ne relit donc aucun état : la même entrée donnera le même résultat
        dans trois ans, et le rejeu reconstruit la chaîne entière."""
        effects: list[ProposedEffect] = [
            OpenCase(
                subject_id=fact.subject_id,
                reason=reason,
                # C'est **sa** parole qui a posé cette date : le déclaré, exempt du plafond.
                origin=CasePriority.DECLARED,
                opened_at=fact.occurred_at,
            )
        ]
        every_days = fact.payload.get("every_days")
        if every_days:
            effects.append(
                ScheduleCheck(
                    subject_id=fact.subject_id,
                    reason=reason,
                    at=fact.occurred_at + timedelta(days=int(every_days)),
                    kind=CheckKind.RHYTHM.value,
                    payload={"every_days": int(every_days)},
                )
            )
        return effects
