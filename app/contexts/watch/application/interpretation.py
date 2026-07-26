"""Étage 02 — l'interprétation : transformer un fait en **propositions** d'effet.

Un interpreter reçoit un fait et une vue en **lecture seule** de l'état projeté, et renvoie des
propositions. Trois contraintes en font une brique remplaçable sans danger :

- **pur** — pas d'I/O, pas de dépôt, pas d'horloge. Toute l'information dont il a besoin lui est
  passée. C'est ce qui rend le rejeu du ledger déterministe : la même entrée donne toujours la
  même sortie, aujourd'hui comme dans trois ans ;
- **sans écriture** — il ne peut que proposer. L'arbitrage décide, la matérialisation écrit ;
- **versionné** — changer une règle métier, c'est publier une V2 à côté de la V1 avec une date
  d'effet. Les faits entrés avant gardent leur version : **le passé ne change jamais de sens**.

La version est choisie sur `recorded_at` (quand le système a appris), pas sur `occurred_at` :
sinon une saisie tardive ressusciterait un interpreter retiré depuis longtemps.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.contexts.watch.domain.effects import ProposedEffect
from app.contexts.watch.domain.errors import NoInterpreterError
from app.contexts.watch.domain.facts import Fact, FactKind


@dataclass(frozen=True)
class NeutralizationView:
    """Ce que l'engine sait d'une neutralisation en cours, en lecture seule."""

    id: UUID
    subject_id: UUID
    starts_at: datetime
    expected_return_at: datetime


@dataclass(frozen=True)
class OpenCaseView:
    """Un cas en cours, en lecture seule. `owner_id` peut être NULL — c'est une donnée, pas un
    blocage : « personne ne connaît cette personne » est précisément ce qu'il faut savoir."""

    id: UUID
    subject_id: UUID
    owner_id: UUID | None
    origin: str
    is_held: bool = False


@dataclass(frozen=True)
class WatchStateView:
    """L'état projeté, tel qu'un interpreter a le droit de le voir : rien qu'à lire.

    Chargé par la couche applicative **avant** l'appel, pour que l'interpreter reste pur."""

    excluded_subject_ids: frozenset[UUID] = frozenset()
    open_neutralizations: tuple[NeutralizationView, ...] = ()
    open_cases: tuple[OpenCaseView, ...] = ()

    def is_excluded(self, subject_id: UUID) -> bool:
        return subject_id in self.excluded_subject_ids

    def neutralizations_of(self, subject_id: UUID) -> tuple[NeutralizationView, ...]:
        return tuple(n for n in self.open_neutralizations if n.subject_id == subject_id)

    def has_open_case(self, subject_id: UUID) -> bool:
        return any(c.subject_id == subject_id for c in self.open_cases)

    def case_of(self, subject_id: UUID) -> OpenCaseView | None:
        return next((c for c in self.open_cases if c.subject_id == subject_id), None)

    def owner_of(self, subject_id: UUID) -> UUID | None:
        """À qui reviendrait un cas sur cette personne. NULL tant que `Referent` n'existe pas —
        tous les cas sans propriétaire partagent alors le même budget, ce qui est le
        comportement prudent : on ne fait pas semblant d'avoir réparti."""
        case = self.case_of(subject_id)
        return case.owner_id if case is not None else None

    def open_cases_of_owner(self, owner_id: UUID | None) -> int:
        """Combien de cas **émis** pèsent déjà sur ce responsable. Les retenus ne comptent pas :
        ils ne sont, précisément, pas encore sur ses épaules."""
        return sum(1 for c in self.open_cases if c.owner_id == owner_id and not c.is_held)


class Interpreter(Protocol):
    """Le contrat. Tout greffon futur s'y conforme, sans exception."""

    kind: FactKind
    version: int
    effective_from: datetime

    def interpret(self, fact: Fact, state: WatchStateView) -> Sequence[ProposedEffect]: ...


@dataclass
class InterpreterRegistry:
    """Les interpreters enregistrés, par type de fait et par version."""

    _by_kind: dict[FactKind, list[Interpreter]] = field(default_factory=dict)

    def register(self, interpreter: Interpreter) -> Interpreter:
        versions = self._by_kind.setdefault(interpreter.kind, [])
        versions.append(interpreter)
        # Plus récent d'abord : la première version dont la date d'effet est atteinte gagne.
        versions.sort(key=lambda i: i.effective_from, reverse=True)
        return interpreter

    def for_fact(self, fact: Fact) -> Interpreter:
        for interpreter in self._by_kind.get(fact.kind, ()):
            if interpreter.effective_from <= fact.recorded_at:
                return interpreter
        raise NoInterpreterError(
            "Aucun interpreter pour ce type de fait à cette date.",
            details={"kind": fact.kind.value, "recorded_at": fact.recorded_at.isoformat()},
        )

    def has(self, kind: FactKind) -> bool:
        return bool(self._by_kind.get(kind))

    def interpret(self, fact: Fact, state: WatchStateView) -> list[ProposedEffect]:
        """Interprète, ou **ne renvoie rien** si aucun interpreter n'existe encore pour ce kind.

        Un fait sans interpreter n'est pas une erreur : il reste au ledger, et le jour où
        l'interpreter arrive, une reprojection lui donne rétroactivement son sens. C'est le
        bénéfice du journal — on n'a jamais besoin de deviner à l'avance."""
        if not self.has(fact.kind):
            return []
        return list(self.for_fact(fact).interpret(fact, state))
