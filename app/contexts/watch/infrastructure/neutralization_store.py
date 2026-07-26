"""Adaptateur `NeutralizationStore` — le moteur écrit dans la Présence (M6).

Une **neutralisation** s'écrit comme une `PlannedAbsence` d'origine `ANNOUNCEMENT`. C'est
délibéré : l'absence planifiée est le seul objet que le roster et les sept lectures pastorales
de M7 consultent déjà. Une table de projection séparée les obligerait à unir deux sources — et
en oublier une seule ferait réapparaître un endeuillé comme absent silencieux, exactement la
panne qu'on veut supprimer.

La pureté « projection » n'exige pas une table à part : elle exige un **chemin d'écriture
unique** et une purge sûre. Ce fichier est ce chemin ; `purge_projected` est cette purge, et
elle ne touche jamais à ce qu'un membre a déclaré lui-même.

Une **exclusion** s'écrit comme un `WatchExclusion` : un statut de veille, jamais un statut
d'appartenance — publier une annonce ne ferme pas l'adhésion de quelqu'un.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.attendance.domain.enums import (
    AbsenceOutcome,
    AbsenceReason,
    AbsenceSource,
    WatchExclusionReason,
)
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.attendance.domain.repositories import (
    PlannedAbsenceRepository,
    WatchExclusionRepository,
)
from app.contexts.attendance.domain.watch_exclusion import WatchExclusion
from app.contexts.watch.application.ports import NeutralizationStore
from app.contexts.watch.domain.role_rules import SubjectRole

# Le rôle → le tag d'absence de M6. La gravité (M7) en découle : tous ces tags disent
# « elle revient », aucun ne sort quelqu'un de l'effectif.
_REASON_OF_ROLE: dict[str, AbsenceReason] = {
    SubjectRole.SICK.value: AbsenceReason.SICK,
    SubjectRole.TRAVELER.value: AbsenceReason.TRAVEL,
    SubjectRole.NEW_PARENT.value: AbsenceReason.FAMILY,
    SubjectRole.NEWLYWED.value: AbsenceReason.FAMILY,
    SubjectRole.BEREAVED.value: AbsenceReason.FAMILY,
}

_OUTCOME_OF_CAUSE: dict[str, AbsenceOutcome] = {
    "returned": AbsenceOutcome.RETURNED,
    "deceased": AbsenceOutcome.DECEASED,
    "explained_by_announcement": AbsenceOutcome.RETURNED,
}


class AttendanceNeutralizationStore(NeutralizationStore):
    def __init__(
        self,
        absences: PlannedAbsenceRepository,
        exclusions: WatchExclusionRepository,
    ) -> None:
        self._absences = absences
        self._exclusions = exclusions

    async def neutralize(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        role: str | None,
        starts_at: datetime,
        expected_return_at: datetime,
        source_ref: UUID,
        declared_by_account_id: UUID,
        reason: str,
    ) -> None:
        # Idempotence (source, personne) : rejouer le même fait ne crée pas un doublon.
        if await self._absences.get_by_source(subject_id, source_ref) is not None:
            return

        # Prolongation, jamais cumul : si une neutralisation en cours va déjà aussi loin, on ne
        # touche à rien ; sinon on repousse **sa** date de retour attendu.
        open_ones = await self._absences.list_open_neutralizations(subject_id, tenant_id)
        if open_ones:
            existing = min(open_ones, key=lambda a: a.from_date)
            if existing.extend_to(expected_return_at):
                await self._absences.save(existing)
            return

        await self._absences.add(
            PlannedAbsence(
                id=uuid4(),
                account_id=subject_id,
                tenant_id=tenant_id,
                reason=_REASON_OF_ROLE.get(role or "", AbsenceReason.OTHER),
                from_date=starts_at,
                to_date=expected_return_at,
                declared_by_account_id=declared_by_account_id,
                declared_at=starts_at,
                note=reason,  # la raison **en clair**, stockée, jamais recalculée à l'affichage
                source=AbsenceSource.ANNOUNCEMENT,
                source_ref=source_ref,
            )
        )

    async def extinguish(
        self, *, subject_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None:
        outcome = _OUTCOME_OF_CAUSE.get(cause, AbsenceOutcome.RETURNED)
        for absence in await self._absences.list_open_neutralizations(subject_id, tenant_id):
            absence.close(outcome=outcome, at=at)
            await self._absences.save(absence)

    async def exclude_forever(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        source_ref: UUID,
        declared_by_account_id: UUID,
        reason: str,
        at: datetime,
    ) -> None:
        if await self._exclusions.get_for(subject_id, tenant_id) is not None:
            return  # l'absorbant est idempotent
        await self._exclusions.add(
            WatchExclusion(
                id=uuid4(),
                account_id=subject_id,
                tenant_id=tenant_id,
                reason=WatchExclusionReason.DECEASED,
                excluded_at=at,
                declared_by_account_id=declared_by_account_id,
                source_ref=source_ref,
                note=reason,
            )
        )

    async def excluded_subject_ids(self, tenant_id: UUID) -> set[UUID]:
        return await self._exclusions.excluded_account_ids(tenant_id)

    async def open_neutralizations(
        self, tenant_id: UUID
    ) -> list[tuple[UUID, UUID, datetime, datetime]]:
        rows = await self._absences.list_open_neutralizations_by_tenant(tenant_id)
        return [(a.id, a.account_id, a.from_date, a.to_date) for a in rows]

    async def purge_projected_neutralizations(self, tenant_id: UUID) -> None:
        """Efface **uniquement** le projeté : les neutralisations posées par le moteur et les
        exclusions. Ce qu'un membre a déclaré lui-même reste — sa parole n'est pas une projection.
        """
        await self._absences.delete_projected(tenant_id)
        await self._exclusions.delete_all(tenant_id)
