"""Agrégat `PlannedAbsence` — la dignité de prévenir (M6-2), et la **neutralisation** (M8).

Le membre **annonce une période** d'absence avec un **tag** (raison), pas une réunion.
Tenant-large : un voyage te retire de *toutes* tes rencontres. Le roster **déduit** l'excusé
(rencontre dont la date tombe dans la période) — les rencontres futures n'ont pas à exister.

Deux origines, un seul objet — parce que le roster et M7 ne doivent connaître qu'une vérité sur
« cette personne est attendue plus tard » :
- `SELF_DECLARED` — le membre a prévenu ;
- `ANNOUNCEMENT` — une annonce l'a posée pour lui (deuil, maladie, voyage). C'est la
  **neutralisation** : son silence cesse d'être un silence, parce qu'on sait pourquoi.

Deux neutralisations successives **prolongent**, elles ne cumulent pas : `to_date` est le retour
attendu le plus lointain, jamais la somme des durées.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.attendance.domain.enums import (
    AbsenceOutcome,
    AbsenceReason,
    AbsenceSource,
)


class PlannedAbsence(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        account_id: UUID,
        tenant_id: UUID,
        reason: AbsenceReason,
        from_date: datetime,
        to_date: datetime,
        declared_by_account_id: UUID,
        declared_at: datetime,
        note: str | None = None,
        canceled_at: datetime | None = None,
        source: AbsenceSource = AbsenceSource.SELF_DECLARED,
        source_ref: UUID | None = None,  # l'annonce d'origine — clé d'idempotence du rejeu
        returned_at: datetime | None = None,
        outcome: AbsenceOutcome | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.account_id = account_id
        self.tenant_id = tenant_id
        self.reason = reason
        self.from_date = from_date
        self.to_date = to_date
        self.declared_by_account_id = declared_by_account_id
        self.declared_at = declared_at
        self.note = note  # facultatif, surtout pour `other`
        self.canceled_at = canceled_at
        self.source = source
        self.source_ref = source_ref
        self.returned_at = returned_at
        self.outcome = outcome

    @property
    def is_active(self) -> bool:
        return self.canceled_at is None

    @property
    def is_open(self) -> bool:
        """Encore en attente d'une issue — c'est celle-là qu'une nouvelle annonce prolonge."""
        return self.canceled_at is None and self.outcome is None

    @property
    def is_neutralization(self) -> bool:
        """Posée par une annonce, pas déclarée par l'intéressé."""
        return self.source is AbsenceSource.ANNOUNCEMENT

    @property
    def expected_return_at(self) -> datetime:
        """Le nom de `to_date` du point de vue de la veille : quand on la ou le réattend."""
        return self.to_date

    def covers(self, moment: datetime) -> bool:
        return self.is_active and self.from_date <= moment <= self.to_date

    def cancel(self, *, now: datetime) -> None:
        if self.canceled_at is None:
            self.canceled_at = now

    def extend_to(self, expected_return_at: datetime) -> bool:
        """**Prolonge** jusqu'à cette date si elle est plus lointaine. Ne cumule jamais.

        Renvoie True si la période a bougé — une seconde annonce couvrant une période déjà
        couverte ne doit rien changer du tout (idempotence)."""
        if expected_return_at <= self.to_date:
            return False
        self.to_date = expected_return_at
        return True

    def close(self, *, outcome: AbsenceOutcome, at: datetime) -> None:
        """Clôt l'absence sur une issue **stockée**, jamais recalculée à l'affichage.

        Un retour anticipé **raccourcit** la période au lieu de l'effacer : les rencontres
        manquées avant le retour restent excusées. Réécrire l'histoire d'un membre revenu plus
        tôt en absences non justifiées serait exactement le faux positif qu'on veut éviter.
        """
        if self.outcome is not None:
            return  # déjà close : rejouer ne réécrit pas l'histoire
        self.outcome = outcome
        if outcome is AbsenceOutcome.RETURNED:
            self.returned_at = at
            if at < self.to_date:
                self.to_date = max(at, self.from_date)
