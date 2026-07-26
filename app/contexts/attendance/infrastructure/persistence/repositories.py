"""Implémentations SQLAlchemy des dépôts Présence (M6)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.attendance.domain.aggregates import AttendanceRecord, Gathering
from app.contexts.attendance.domain.enums import (
    AttendanceMark,
    AttendanceSource,
    GatheringStatus,
    GatheringType,
)
from app.contexts.attendance.domain.repositories import (
    AttendanceRecordRepository,
    GatheringRepository,
)
from app.contexts.attendance.infrastructure.persistence.models import (
    AttendanceRecordModel,
    GatheringModel,
)


def _aware(dt):
    """SQLite rend des datetimes naïfs — on rattache UTC pour les comparaisons Python (M7)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_gathering(row: GatheringModel) -> Gathering:
    return Gathering(
        id=row.id,
        tenant_id=row.tenant_id,
        group_id=row.group_id,
        type=GatheringType(row.type),
        title=row.title,
        scheduled_at=_aware(row.scheduled_at),
        status=GatheringStatus(row.status),
        created_by_account_id=row.created_by_account_id,
        created_at=_aware(row.created_at),
        check_in_code=row.check_in_code,
        closed_at=_aware(row.closed_at),
    )


class SqlGatheringRepository(GatheringRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, gathering: Gathering) -> None:
        self._session.add(
            GatheringModel(
                id=gathering.id,
                tenant_id=gathering.tenant_id,
                group_id=gathering.group_id,
                type=gathering.type.value,
                title=gathering.title,
                scheduled_at=gathering.scheduled_at,
                status=gathering.status.value,
                created_by_account_id=gathering.created_by_account_id,
                created_at=gathering.created_at,
                check_in_code=gathering.check_in_code,
                closed_at=gathering.closed_at,
            )
        )
        await self._session.flush()

    async def get(self, gathering_id: UUID) -> Gathering | None:
        row = await self._session.get(GatheringModel, gathering_id)
        return _to_gathering(row) if row is not None else None

    async def get_open_by_check_in_code(self, code: str) -> Gathering | None:
        stmt = select(GatheringModel).where(
            GatheringModel.check_in_code == code,
            GatheringModel.status == GatheringStatus.OPEN.value,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_gathering(row) if row is not None else None

    async def list_by_group(self, group_id: UUID) -> list[Gathering]:
        stmt = (
            select(GatheringModel)
            .where(GatheringModel.group_id == group_id)
            .order_by(GatheringModel.scheduled_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_gathering(r) for r in rows]

    async def save(self, gathering: Gathering) -> None:
        await self._session.execute(
            update(GatheringModel)
            .where(GatheringModel.id == gathering.id)
            .values(status=gathering.status.value, closed_at=gathering.closed_at)
        )


def _to_record(row: AttendanceRecordModel) -> AttendanceRecord:
    return AttendanceRecord(
        id=row.id,
        gathering_id=row.gathering_id,
        account_id=row.account_id,
        mark=AttendanceMark(row.mark),
        source=AttendanceSource(row.source),
        recorded_at=row.recorded_at,
        recorded_by_account_id=row.recorded_by_account_id,
        reason=row.reason,
    )


class SqlAttendanceRecordRepository(AttendanceRecordRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: AttendanceRecord) -> None:
        self._session.add(
            AttendanceRecordModel(
                id=record.id,
                gathering_id=record.gathering_id,
                account_id=record.account_id,
                mark=record.mark.value,
                source=record.source.value,
                reason=record.reason,
                recorded_at=record.recorded_at,
                recorded_by_account_id=record.recorded_by_account_id,
            )
        )
        await self._session.flush()

    async def get_for(self, gathering_id: UUID, account_id: UUID) -> AttendanceRecord | None:
        stmt = select(AttendanceRecordModel).where(
            AttendanceRecordModel.gathering_id == gathering_id,
            AttendanceRecordModel.account_id == account_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_record(row) if row is not None else None

    async def remove(self, gathering_id: UUID, account_id: UUID) -> None:
        await self._session.execute(
            delete(AttendanceRecordModel).where(
                AttendanceRecordModel.gathering_id == gathering_id,
                AttendanceRecordModel.account_id == account_id,
            )
        )

    async def list_for_gathering(self, gathering_id: UUID) -> list[AttendanceRecord]:
        stmt = select(AttendanceRecordModel).where(
            AttendanceRecordModel.gathering_id == gathering_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_record(r) for r in rows]

    async def list_present_for_gatherings(
        self, gathering_ids: list[UUID]
    ) -> list[AttendanceRecord]:
        if not gathering_ids:
            return []
        stmt = select(AttendanceRecordModel).where(
            AttendanceRecordModel.gathering_id.in_(gathering_ids),
            AttendanceRecordModel.mark == AttendanceMark.PRESENT.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_record(r) for r in rows]

    async def has_present_in_other_tenant_since(
        self, account_id: UUID, tenant_id: UUID, since: datetime
    ) -> bool:
        # Présent dans une AUTRE église du réseau depuis `since` (signal « actif ailleurs »).
        stmt = (
            select(AttendanceRecordModel.id)
            .join(GatheringModel, AttendanceRecordModel.gathering_id == GatheringModel.id)
            .where(
                AttendanceRecordModel.account_id == account_id,
                AttendanceRecordModel.mark == AttendanceMark.PRESENT.value,
                GatheringModel.tenant_id != tenant_id,
                GatheringModel.scheduled_at > since,
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).first() is not None
