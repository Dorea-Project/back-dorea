"""Implémentations SQLAlchemy des repositories de cadence (P1 — Fondation A).

Comme `absence_repository`, les dates sont rendues *aware* à la lecture (UTC) pour éviter le
piège naïf/aware SQLite ; les filtres par date sont faits en mémoire par les fonctions pures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.attendance.domain.cadence import (
    AcknowledgementReason,
    CadenceAcknowledgement,
    CadenceFrequency,
    ChurchSuspension,
    GroupCadence,
    SuspensionReason,
)
from app.contexts.attendance.domain.repositories import (
    CadenceAcknowledgementRepository,
    ChurchSuspensionRepository,
    GroupCadenceRepository,
)
from app.contexts.attendance.infrastructure.persistence.models import (
    CadenceAcknowledgementModel,
    ChurchSuspensionModel,
    GroupCadenceModel,
)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_cadence(row: GroupCadenceModel) -> GroupCadence:
    return GroupCadence(
        id=row.id,
        tenant_id=row.tenant_id,
        group_id=row.group_id,
        frequency=CadenceFrequency(row.frequency),
        anchor_date=_aware(row.anchor_date),
        active_from=_aware(row.active_from),
        created_at=_aware(row.created_at),
        created_by_account_id=row.created_by_account_id,
        weekday=row.weekday,
        day_of_month=row.day_of_month,
        active_until=_aware(row.active_until),
        canceled_at=_aware(row.canceled_at),
    )


def _to_ack(row: CadenceAcknowledgementModel) -> CadenceAcknowledgement:
    return CadenceAcknowledgement(
        id=row.id,
        tenant_id=row.tenant_id,
        group_id=row.group_id,
        occurrence_date=_aware(row.occurrence_date),
        reason=AcknowledgementReason(row.reason),
        acknowledged_by_account_id=row.acknowledged_by_account_id,
        acknowledged_at=_aware(row.acknowledged_at),
        suspension_id=row.suspension_id,
    )


def _to_suspension(row: ChurchSuspensionModel) -> ChurchSuspension:
    return ChurchSuspension(
        id=row.id,
        tenant_id=row.tenant_id,
        reason=SuspensionReason(row.reason),
        from_date=_aware(row.from_date),
        to_date=_aware(row.to_date),
        declared_by_account_id=row.declared_by_account_id,
        declared_at=_aware(row.declared_at),
        canceled_at=_aware(row.canceled_at),
    )


class SqlGroupCadenceRepository(GroupCadenceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, cadence: GroupCadence) -> None:
        self._session.add(
            GroupCadenceModel(
                id=cadence.id,
                tenant_id=cadence.tenant_id,
                group_id=cadence.group_id,
                frequency=cadence.frequency.value,
                weekday=cadence.weekday,
                day_of_month=cadence.day_of_month,
                anchor_date=cadence.anchor_date,
                active_from=cadence.active_from,
                active_until=cadence.active_until,
                created_at=cadence.created_at,
                created_by_account_id=cadence.created_by_account_id,
                canceled_at=cadence.canceled_at,
            )
        )
        await self._session.flush()

    async def get_active_by_group(self, group_id: UUID) -> GroupCadence | None:
        stmt = select(GroupCadenceModel).where(
            GroupCadenceModel.group_id == group_id,
            GroupCadenceModel.canceled_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_cadence(row) if row is not None else None

    async def save(self, cadence: GroupCadence) -> None:
        await self._session.execute(
            update(GroupCadenceModel)
            .where(GroupCadenceModel.id == cadence.id)
            .values(
                active_until=cadence.active_until,
                canceled_at=cadence.canceled_at,
            )
        )


class SqlCadenceAcknowledgementRepository(CadenceAcknowledgementRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, ack: CadenceAcknowledgement) -> None:
        self._session.add(
            CadenceAcknowledgementModel(
                id=ack.id,
                tenant_id=ack.tenant_id,
                group_id=ack.group_id,
                occurrence_date=ack.occurrence_date,
                reason=ack.reason.value,
                suspension_id=ack.suspension_id,
                acknowledged_by_account_id=ack.acknowledged_by_account_id,
                acknowledged_at=ack.acknowledged_at,
            )
        )
        await self._session.flush()

    async def get_for(
        self, group_id: UUID, occurrence_date: datetime
    ) -> CadenceAcknowledgement | None:
        stmt = select(CadenceAcknowledgementModel).where(
            CadenceAcknowledgementModel.group_id == group_id,
            CadenceAcknowledgementModel.occurrence_date == occurrence_date,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_ack(row) if row is not None else None

    async def list_by_group(self, group_id: UUID) -> list[CadenceAcknowledgement]:
        stmt = select(CadenceAcknowledgementModel).where(
            CadenceAcknowledgementModel.group_id == group_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_ack(r) for r in rows]


class SqlChurchSuspensionRepository(ChurchSuspensionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, suspension: ChurchSuspension) -> None:
        self._session.add(
            ChurchSuspensionModel(
                id=suspension.id,
                tenant_id=suspension.tenant_id,
                reason=suspension.reason.value,
                from_date=suspension.from_date,
                to_date=suspension.to_date,
                declared_by_account_id=suspension.declared_by_account_id,
                declared_at=suspension.declared_at,
                canceled_at=suspension.canceled_at,
            )
        )
        await self._session.flush()

    async def get(self, suspension_id: UUID) -> ChurchSuspension | None:
        row = await self._session.get(ChurchSuspensionModel, suspension_id)
        return _to_suspension(row) if row is not None else None

    async def save(self, suspension: ChurchSuspension) -> None:
        await self._session.execute(
            update(ChurchSuspensionModel)
            .where(ChurchSuspensionModel.id == suspension.id)
            .values(canceled_at=suspension.canceled_at)
        )

    async def list_active_by_tenant(self, tenant_id: UUID) -> list[ChurchSuspension]:
        stmt = select(ChurchSuspensionModel).where(
            ChurchSuspensionModel.tenant_id == tenant_id,
            ChurchSuspensionModel.canceled_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_suspension(r) for r in rows]
