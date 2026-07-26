"""Implémentation SQLAlchemy de `PlannedAbsenceRepository` (M6-2) et `WatchExclusionRepository`.

La couverture par date est filtrée **en mémoire** (`PlannedAbsence.covers`) pour éviter les
comparaisons de datetimes en SQL (naïf SQLite vs aware) ; on rattache UTC à la lecture.
"""

from __future__ import annotations

from datetime import UTC
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.contexts.attendance.infrastructure.persistence.models import (
    PlannedAbsenceModel,
    WatchExclusionModel,
)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_absence(row: PlannedAbsenceModel) -> PlannedAbsence:
    return PlannedAbsence(
        id=row.id,
        account_id=row.account_id,
        tenant_id=row.tenant_id,
        reason=AbsenceReason(row.reason),
        from_date=_aware(row.from_date),
        to_date=_aware(row.to_date),
        declared_by_account_id=row.declared_by_account_id,
        declared_at=_aware(row.declared_at),
        note=row.note,
        canceled_at=_aware(row.canceled_at),
        source=AbsenceSource(row.source or AbsenceSource.SELF_DECLARED.value),
        source_ref=row.source_ref,
        returned_at=_aware(row.returned_at),
        outcome=AbsenceOutcome(row.outcome) if row.outcome else None,
    )


class SqlPlannedAbsenceRepository(PlannedAbsenceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, absence: PlannedAbsence) -> None:
        self._session.add(
            PlannedAbsenceModel(
                id=absence.id,
                account_id=absence.account_id,
                tenant_id=absence.tenant_id,
                reason=absence.reason.value,
                note=absence.note,
                from_date=absence.from_date,
                to_date=absence.to_date,
                declared_by_account_id=absence.declared_by_account_id,
                declared_at=absence.declared_at,
                canceled_at=absence.canceled_at,
                source=absence.source.value,
                source_ref=absence.source_ref,
                returned_at=absence.returned_at,
                outcome=absence.outcome.value if absence.outcome else None,
            )
        )
        await self._session.flush()

    async def get(self, absence_id: UUID) -> PlannedAbsence | None:
        row = await self._session.get(PlannedAbsenceModel, absence_id)
        return _to_absence(row) if row is not None else None

    async def save(self, absence: PlannedAbsence) -> None:
        row = await self._session.get(PlannedAbsenceModel, absence.id)
        if row is None:
            return
        # Une prolongation déplace `to_date` ; une clôture pose l'issue et date le retour.
        row.to_date = absence.to_date
        row.canceled_at = absence.canceled_at
        row.returned_at = absence.returned_at
        row.outcome = absence.outcome.value if absence.outcome else None
        await self._session.flush()

    async def list_active_by_tenant(self, tenant_id: UUID) -> list[PlannedAbsence]:
        stmt = select(PlannedAbsenceModel).where(
            PlannedAbsenceModel.tenant_id == tenant_id,
            PlannedAbsenceModel.canceled_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_absence(r) for r in rows]

    async def list_active_by_account(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[PlannedAbsence]:
        stmt = select(PlannedAbsenceModel).where(
            PlannedAbsenceModel.account_id == account_id,
            PlannedAbsenceModel.tenant_id == tenant_id,
            PlannedAbsenceModel.canceled_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_absence(r) for r in rows]

    async def get_by_source(self, account_id: UUID, source_ref: UUID) -> PlannedAbsence | None:
        stmt = select(PlannedAbsenceModel).where(
            PlannedAbsenceModel.account_id == account_id,
            PlannedAbsenceModel.source_ref == source_ref,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_absence(row) if row is not None else None

    async def list_open_neutralizations(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[PlannedAbsence]:
        stmt = select(PlannedAbsenceModel).where(
            PlannedAbsenceModel.account_id == account_id,
            PlannedAbsenceModel.tenant_id == tenant_id,
            PlannedAbsenceModel.source == AbsenceSource.ANNOUNCEMENT.value,
            PlannedAbsenceModel.canceled_at.is_(None),
            PlannedAbsenceModel.outcome.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_absence(r) for r in rows]

    async def list_open_neutralizations_by_tenant(
        self, tenant_id: UUID
    ) -> list[PlannedAbsence]:
        stmt = select(PlannedAbsenceModel).where(
            PlannedAbsenceModel.tenant_id == tenant_id,
            PlannedAbsenceModel.source == AbsenceSource.ANNOUNCEMENT.value,
            PlannedAbsenceModel.canceled_at.is_(None),
            PlannedAbsenceModel.outcome.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_absence(r) for r in rows]

    async def delete_projected(self, tenant_id: UUID) -> None:
        """Le filtre sur `source` est la garantie : la parole du membre n'est pas effaçable."""
        await self._session.execute(
            delete(PlannedAbsenceModel).where(
                PlannedAbsenceModel.tenant_id == tenant_id,
                PlannedAbsenceModel.source == AbsenceSource.ANNOUNCEMENT.value,
            )
        )
        await self._session.flush()


class SqlWatchExclusionRepository(WatchExclusionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, exclusion: WatchExclusion) -> None:
        self._session.add(
            WatchExclusionModel(
                id=exclusion.id,
                account_id=exclusion.account_id,
                tenant_id=exclusion.tenant_id,
                reason=exclusion.reason.value,
                excluded_at=exclusion.excluded_at,
                declared_by_account_id=exclusion.declared_by_account_id,
                source_ref=exclusion.source_ref,
                note=exclusion.note,
            )
        )
        await self._session.flush()

    async def get_for(self, account_id: UUID, tenant_id: UUID) -> WatchExclusion | None:
        stmt = select(WatchExclusionModel).where(
            WatchExclusionModel.account_id == account_id,
            WatchExclusionModel.tenant_id == tenant_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return WatchExclusion(
            id=row.id,
            account_id=row.account_id,
            tenant_id=row.tenant_id,
            reason=WatchExclusionReason(row.reason),
            excluded_at=_aware(row.excluded_at),
            declared_by_account_id=row.declared_by_account_id,
            source_ref=row.source_ref,
            note=row.note,
        )

    async def excluded_account_ids(self, tenant_id: UUID) -> set[UUID]:
        stmt = select(WatchExclusionModel.account_id).where(
            WatchExclusionModel.tenant_id == tenant_id
        )
        return set((await self._session.execute(stmt)).scalars().all())

    async def delete_all(self, tenant_id: UUID) -> None:
        """Réservé à la reprojection : l'exclusion se reconstruit intégralement du ledger."""
        await self._session.execute(
            delete(WatchExclusionModel).where(WatchExclusionModel.tenant_id == tenant_id)
        )
        await self._session.flush()
