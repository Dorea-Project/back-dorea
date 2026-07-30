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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.contexts.watch.domain.effects import ProposedEffect
from app.contexts.watch.domain.errors import NoInterpreterError, StateScopeError
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
    """Un cas en cours, en lecture seule.

    `owner_id` est nullable pour relire une ligne d'avant le 30/07/2026 ; plus aucun chemin n'en
    écrit. « Personne ne connaît cette personne » est une donnée du **référent**, pas du
    destinataire d'un cas."""

    id: UUID
    subject_id: UUID
    owner_id: UUID | None
    origin: str
    is_held: bool = False


@dataclass(frozen=True)
class WatchStateView:
    """L'état projeté, tel qu'un interpreter a le droit de le voir : rien qu'à lire.

    Chargé par la couche applicative **avant** l'appel, pour que l'interpreter reste pur.

    Deux régimes, une seule interface :

    - **borné au sujet** (`subject_id` renseigné) — le régime de production. Trois lectures
      ponctuelles et indexées au lieu de trois requêtes à l'échelle de l'église : le coût d'un fait
      cesse de dépendre du nombre de membres. Toute question posée sur quelqu'un d'autre lève
      `StateScopeError` — sans quoi elle recevrait une réponse vide et se tromperait en silence ;
    - **complet** (`subject_id` nul) — la vue matérialisée d'origine, conservée pour les tests
      d'équivalence et les usages qui lisent réellement toute une église.

    `owner_case_counts` est préchargé **après** la résolution des destinataires : le plafond de
    débit compte les cas du propriétaire, qui n'est presque jamais le sujet du fait.
    """

    excluded_subject_ids: frozenset[UUID] = frozenset()
    open_neutralizations: tuple[NeutralizationView, ...] = ()
    open_cases: tuple[OpenCaseView, ...] = ()
    subject_id: UUID | None = None  # None = vue complète
    owner_case_counts: Mapping[UUID | None, int] | None = None

    @classmethod
    def for_subject(
        cls,
        subject_id: UUID,
        *,
        excluded: bool,
        neutralizations: tuple[NeutralizationView, ...] = (),
        case: OpenCaseView | None = None,
    ) -> WatchStateView:
        """La vue **réduite** : ce qu'on sait de cette personne-là, et rien d'autre."""
        return cls(
            excluded_subject_ids=frozenset({subject_id}) if excluded else frozenset(),
            open_neutralizations=neutralizations,
            open_cases=(case,) if case is not None else (),
            subject_id=subject_id,
        )

    def with_owner_counts(self, counts: Mapping[UUID | None, int]) -> WatchStateView:
        """La même vue, augmentée du budget des propriétaires que l'arbitrage va interroger."""
        return replace(self, owner_case_counts=dict(counts))

    def _in_scope(self, subject_id: UUID) -> None:
        if self.subject_id is not None and subject_id != self.subject_id:
            raise StateScopeError(
                "Cet état est borné au sujet de son fait : il ne sait rien de quelqu'un d'autre.",
                details={"asked": str(subject_id), "scope": str(self.subject_id)},
            )

    def is_excluded(self, subject_id: UUID) -> bool:
        self._in_scope(subject_id)
        return subject_id in self.excluded_subject_ids

    def neutralizations_of(self, subject_id: UUID) -> tuple[NeutralizationView, ...]:
        self._in_scope(subject_id)
        return tuple(n for n in self.open_neutralizations if n.subject_id == subject_id)

    def has_open_case(self, subject_id: UUID) -> bool:
        self._in_scope(subject_id)
        return any(c.subject_id == subject_id for c in self.open_cases)

    def case_of(self, subject_id: UUID) -> OpenCaseView | None:
        self._in_scope(subject_id)
        return next((c for c in self.open_cases if c.subject_id == subject_id), None)

    def owner_of(self, subject_id: UUID) -> UUID | None:
        """À qui reviendrait un cas sur cette personne — celui de son cas en cours, s'il existe."""
        case = self.case_of(subject_id)
        return case.owner_id if case is not None else None

    def open_cases_of_owner(self, owner_id: UUID | None) -> int:
        """Combien de cas **émis** pèsent déjà sur ce responsable. Les retenus ne comptent pas :
        ils ne sont, précisément, pas encore sur ses épaules.

        **Hors portée du garde** : la question porte sur un propriétaire, pas sur un sujet. C'est
        la seule chose que l'arbitrage a besoin de savoir de quelqu'un d'autre — et un compteur
        n'apprend rien sur personne."""
        if self.owner_case_counts is not None:
            return self.owner_case_counts.get(owner_id, 0)
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
