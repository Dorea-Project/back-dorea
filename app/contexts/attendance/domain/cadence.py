"""Cadence attendue d'un groupe — le `Programme` (fondation de la veille par couverture).

Ce module matérialise le **rythme attendu** d'un groupe, jamais son roster : on stocke la règle
(`GroupCadence`) et les **annulations** d'occurrence (`CadenceAcknowledgement`, `ChurchSuspension`),
pas les présences attendues. L'invariant M6 tient — l'absence reste déduite.

Une occurrence attendue a **trois** états, pas deux :
- `SAISIE` — une rencontre a été tenue et saisie (couverture positive) ;
- `ACQUITTEE` — non tenue mais **motif connu** (fête, responsable absent, local indispo, ou
  suspension église) : couverture positive **et** hors du dénominateur d'absence (V8) ;
- `SILENCIEUSE` — ni l'un ni l'autre : **trou de veille**.

Seule `SILENCIEUSE` est un trou. `ACQUITTEE` n'est pas « l'absence d'un trou » : c'est une donnée
de couverture au même titre que `SAISIE`. Et une occurrence `ACQUITTEE` **sort du calcul d'absence**
des membres — sinon Noël génèrerait une salve d'absences fictives (le vrai faux positif, de
détection). Le calcul de seuil (V8), de couverture et de rupture de rythme (O6) consomme ces états ;
il n'est pas construit ici (P2).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app._shared.domain.entity import AggregateRoot

DEFAULT_MATCH_TOLERANCE_DAYS = 3  # une rencontre tenue la veille/le lendemain compte comme saisie


class CadenceFrequency(StrEnum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class AcknowledgementReason(StrEnum):
    """Motif d'acquittement — enum court, jamais de texte libre (pas de surface de jugement)."""

    HOLIDAY = "holiday"  # fête / jour férié
    LEADER_ABSENT = "leader_absent"  # le responsable est absent
    VENUE_UNAVAILABLE = "venue_unavailable"  # local indispo
    OTHER = "other"


class SuspensionReason(StrEnum):
    HOLIDAY = "holiday"
    NATIONAL_MOURNING = "national_mourning"
    OTHER = "other"


class OccurrenceState(StrEnum):
    SAISIE = "saisie"
    ACQUITTEE = "acquittee"
    SILENCIEUSE = "silencieuse"


# `ACQUITTEE` couvre, mais **sort** du dénominateur d'absence (V8) : couvert ≠ rencontre comptée.
COVERED_STATES = frozenset({OccurrenceState.SAISIE, OccurrenceState.ACQUITTEE})


class GroupCadence(AggregateRoot):
    """La règle de rythme d'un groupe (une cadence active par groupe). On ne stocke que la règle."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        frequency: CadenceFrequency,
        anchor_date: datetime,
        active_from: datetime,
        created_at: datetime,
        created_by_account_id: UUID,
        weekday: int | None = None,  # 0-6, pour weekly/biweekly (métadonnée d'affichage)
        day_of_month: int | None = None,  # 1-28, pour monthly
        active_until: datetime | None = None,
        canceled_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.group_id = group_id
        self.frequency = frequency
        self.anchor_date = anchor_date
        self.active_from = active_from
        self.created_at = created_at
        self.created_by_account_id = created_by_account_id
        self.weekday = weekday
        self.day_of_month = day_of_month
        self.active_until = active_until
        self.canceled_at = canceled_at

    @property
    def is_active(self) -> bool:
        return self.canceled_at is None

    def cancel(self, *, now: datetime) -> None:
        if self.canceled_at is None:
            self.canceled_at = now


class CadenceAcknowledgement(AggregateRoot):
    """Une occurrence attendue **non tenue, motif connu** (ACQUITTEE). Motif enum, sans note."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        occurrence_date: datetime,
        reason: AcknowledgementReason,
        acknowledged_by_account_id: UUID,
        acknowledged_at: datetime,
        suspension_id: UUID | None = None,  # renseigné si issu d'une cascade de suspension
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.group_id = group_id
        self.occurrence_date = occurrence_date
        self.reason = reason
        self.acknowledged_by_account_id = acknowledged_by_account_id
        self.acknowledged_at = acknowledged_at
        self.suspension_id = suspension_id


class ChurchSuspension(AggregateRoot):
    """Période église (Noël, deuil national) qui **acquitte en cascade** toutes les occurrences.

    La cascade n'est **pas** matérialisée : `occurrence_state` considère une occurrence tombant
    dans une suspension active comme ACQUITTEE — zéro ligne générée pour N groupes.
    """

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        reason: SuspensionReason,
        from_date: datetime,
        to_date: datetime,
        declared_by_account_id: UUID,
        declared_at: datetime,
        canceled_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.reason = reason
        self.from_date = from_date
        self.to_date = to_date
        self.declared_by_account_id = declared_by_account_id
        self.declared_at = declared_at
        self.canceled_at = canceled_at

    @property
    def is_active(self) -> bool:
        return self.canceled_at is None

    def covers(self, moment: datetime) -> bool:
        return self.is_active and self.from_date <= moment <= self.to_date

    def cancel(self, *, now: datetime) -> None:
        if self.canceled_at is None:
            self.canceled_at = now


_STEP_DAYS = {CadenceFrequency.WEEKLY: 7, CadenceFrequency.BIWEEKLY: 14}


def _add_month(dt: datetime) -> datetime:
    """Mois suivant, jour 1 (le jour cible est réappliqué par `_at_day`)."""
    year = dt.year + dt.month // 12
    month = dt.month % 12 + 1
    return dt.replace(year=year, month=month, day=1)


def _at_day(dt: datetime, day: int) -> datetime:
    return dt.replace(day=day)


def expected_occurrences(cadence: GroupCadence, frm: datetime, to: datetime) -> list[datetime]:
    """Occurrences attendues (dérivées de la règle) dans [frm, to] ∩ fenêtre d'activité.

    Fonction **pure** — aucune I/O, aucun roster. L'occurrence porte l'heure de l'ancre.
    """
    start = max(frm, cadence.active_from)
    end = to if cadence.active_until is None else min(to, cadence.active_until)
    if start > end:
        return []

    if cadence.frequency in _STEP_DAYS:
        step = timedelta(days=_STEP_DAYS[cadence.frequency])
        occ = cadence.anchor_date
        if occ < start:
            occ = occ + step * ((start - occ) // step)  # saut aligné sur la parité de l'ancre
            while occ < start:
                occ += step
        result: list[datetime] = []
        while occ <= end:
            result.append(occ)
            occ += step
        return result

    # MONTHLY — le jour du mois (day_of_month, sinon jour de l'ancre), à l'heure de l'ancre.
    day = cadence.day_of_month or cadence.anchor_date.day
    occ = _at_day(cadence.anchor_date, day)
    result = []
    while occ < start:
        occ = _at_day(_add_month(occ), day)
    while occ <= end:
        result.append(occ)
        occ = _at_day(_add_month(occ), day)
    return result


def occurrence_state(
    occurrence: datetime,
    *,
    gathering_dates: list[datetime],
    acknowledged_dates: list[datetime],
    suspensions: list[tuple[datetime, datetime]],
    tolerance_days: int = DEFAULT_MATCH_TOLERANCE_DAYS,
) -> OccurrenceState:
    """Classe une occurrence attendue. Fonction **pure**.

    Précédence : une rencontre **tenue** l'emporte (SAISIE), même pendant une suspension — on a
    la preuve qu'elle a eu lieu. Sinon acquittement/suspension → ACQUITTEE ; sinon SILENCIEUSE.
    """
    tol = timedelta(days=tolerance_days)
    if any(abs(g - occurrence) <= tol for g in gathering_dates):
        return OccurrenceState.SAISIE
    if any(abs(a - occurrence) <= tol for a in acknowledged_dates):
        return OccurrenceState.ACQUITTEE
    if any(frm <= occurrence <= to for frm, to in suspensions):
        return OccurrenceState.ACQUITTEE
    return OccurrenceState.SILENCIEUSE
