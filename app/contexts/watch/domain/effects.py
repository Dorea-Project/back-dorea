"""Les effets **proposés** — tout ce qu'un interpreter a le droit de dire.

Un interpreter lit un fait et une vue en lecture seule, puis renvoie des propositions. Il n'a
aucun accès en écriture, et ce module est la liste close de ce qu'il peut demander. Ajouter une
source demain, c'est écrire un interpreter qui produit ces mêmes formes — jamais en inventer une
nouvelle, jamais toucher à l'état.

C'est l'arbitrage (étage 03) qui décide lesquelles deviennent visibles, et la matérialisation
(étage 04) qui les écrit. Une proposition n'est pas une décision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class EffectKind(StrEnum):
    OPEN_CASE = "open_case"
    ENRICH_CASE = "enrich_case"
    NEUTRALISE = "neutralise"
    EXTINGUISH = "extinguish"
    EXCLUDE_FOREVER = "exclude_forever"
    RECORD_MEMORY = "record_memory"
    SCHEDULE_CHECK = "schedule_check"
    CANCEL_SCHEDULED_CHECKS = "cancel_scheduled_checks"
    COVERAGE_SIGNAL = "coverage_signal"


class CasePriority(StrEnum):
    """La priorité vient de l'**origine du dire**, pas de la gravité supposée.

    Ce qu'une personne demande pour elle-même passe avant tout, et sort du plafond de débit :
    on ne fait pas attendre quelqu'un qui a levé la main."""

    DECLARED = "declared"  # la personne elle-même — hors plafond
    DEADLINE = "deadline"
    ANNOUNCEMENT = "announcement"
    ABSENCE = "absence"


class ExtinguishCause(StrEnum):
    EXPLAINED_BY_ANNOUNCEMENT = "explained_by_announcement"
    RETURNED = "returned"
    DECEASED = "deceased"
    # Une reconnaissance déposée : la personne a parlé, le doute n'a plus lieu d'être.
    # **Le vocabulaire existe, la permission de clore sans humain n'est PAS accordée** — voir
    # `SYSTEM_CLOSURE_CAUSES`. C'est une décision produit en attente, pas un oubli.
    LIFE_SIGN = "life_sign"


# Les seules causes qui autorisent une clôture **sans acte humain**. Toute autre exige un
# `closed_by`. La justification commune : le cas n'était pas réel, et on ne demande pas à un
# responsable de fermer à la main une erreur du système.
SYSTEM_CLOSURE_CAUSES: frozenset[ExtinguishCause] = frozenset(
    {
        ExtinguishCause.EXPLAINED_BY_ANNOUNCEMENT,
        ExtinguishCause.RETURNED,
        ExtinguishCause.DECEASED,
    }
)


class CoverageGap(StrEnum):
    """Ce qui manque pour veiller — un défaut de dispositif, jamais un reproche à quelqu'un."""

    NO_REFERENT = "no_referent"  # personne ne connaît cette personne
    BLIND = "blind"  # aucune rencontre saisie : on ne sait rien


class ExclusionCause(StrEnum):
    DECEASED = "deceased"


@dataclass(frozen=True)
class _Effect:
    """Socle commun : sur qui, et **pourquoi en clair**.

    La raison est écrite ici, une fois, et voyagera telle quelle jusqu'à l'affichage. On ne la
    recalcule jamais : un motif reconstruit six semaines plus tard ne dit plus la même chose."""

    subject_id: UUID
    reason: str


@dataclass(frozen=True)
class OpenCase(_Effect):
    origin: CasePriority
    opened_at: datetime
    expires_at: datetime | None = None
    role: str | None = None


@dataclass(frozen=True)
class EnrichCase(_Effect):
    origin: CasePriority
    extend_to: datetime | None = None


@dataclass(frozen=True)
class Neutralise(_Effect):
    starts_at: datetime
    expected_return_at: datetime
    role: str | None = None


@dataclass(frozen=True)
class Extinguish(_Effect):
    cause: ExtinguishCause
    at: datetime


@dataclass(frozen=True)
class ExcludeForever(_Effect):
    cause: ExclusionCause
    at: datetime


@dataclass(frozen=True)
class RecordMemory(_Effect):
    """La mémoire du lien — restituée au référent seul, jamais agrégée par membre."""

    at: datetime
    item: str


@dataclass(frozen=True)
class ScheduleCheck(_Effect):
    """Une échéance. Quand elle tombera, le worker écrira un `CHECK_FIRED` au ledger — c'est
    ainsi que le temps entre dans le moteur sans casser la rejouabilité."""

    at: datetime
    kind: str


@dataclass(frozen=True)
class CancelScheduledChecks(_Effect):
    """« Ne me relancez plus » — le membre reprend la main sur son propre rythme."""

    kind: str | None = None  # None = toutes


@dataclass(frozen=True)
class CoverageSignal(_Effect):
    """Un trou dans le dispositif, adressé au responsable et au pasteur — jamais au référent.

    Sa sortie n'est pas un contact mais une **désignation** : il ne s'agit pas d'aller voir
    quelqu'un, il s'agit que quelqu'un lui soit donné."""

    gap: CoverageGap
    at: datetime


ProposedEffect = (
    OpenCase
    | EnrichCase
    | Neutralise
    | Extinguish
    | ExcludeForever
    | RecordMemory
    | ScheduleCheck
    | CancelScheduledChecks
    | CoverageSignal
)
