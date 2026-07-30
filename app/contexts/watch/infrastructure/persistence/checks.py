"""Implémentation SQLAlchemy de `ScheduledCheckStore` — les échéances du moteur."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.ports import ScheduledCheckStore
from app.contexts.watch.infrastructure.persistence.models import ScheduledCheckModel


@dataclass(frozen=True)
class DueCheck:
    """Une échéance arrivée à terme. `reason` voyage jusqu'au fait émis."""

    id: UUID
    tenant_id: UUID
    subject_id: UUID
    kind: str
    reason: str
    due_at: datetime


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SqlScheduledCheckStore(ScheduledCheckStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def schedule(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        kind: str,
        reason: str,
        due_at: datetime,
        at: datetime,
    ) -> None:
        # Idempotence : rejouer le ledger ne doit pas empiler trois fois la même échéance.
        existing = await self._session.execute(
            select(ScheduledCheckModel.id).where(
                ScheduledCheckModel.tenant_id == tenant_id,
                ScheduledCheckModel.subject_id == subject_id,
                ScheduledCheckModel.kind == kind,
                ScheduledCheckModel.due_at == due_at,
                ScheduledCheckModel.fired_at.is_(None),
                ScheduledCheckModel.cancelled_at.is_(None),
            )
        )
        if existing.scalar_one_or_none() is not None:
            return

        self._session.add(
            ScheduledCheckModel(
                id=uuid4(),
                tenant_id=tenant_id,
                subject_id=subject_id,
                kind=kind,
                reason=reason,
                due_at=due_at,
                scheduled_at=at,
            )
        )
        await self._session.flush()

    async def cancel_for(
        self, *, subject_id: UUID, tenant_id: UUID, kind: str | None, at: datetime
    ) -> int:
        stmt = (
            update(ScheduledCheckModel)
            .where(
                ScheduledCheckModel.tenant_id == tenant_id,
                ScheduledCheckModel.subject_id == subject_id,
                ScheduledCheckModel.fired_at.is_(None),
                ScheduledCheckModel.cancelled_at.is_(None),
            )
            .values(cancelled_at=at)
        )
        if kind is not None:
            stmt = stmt.where(ScheduledCheckModel.kind == kind)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)

    async def due(self, *, tenant_id: UUID, now: datetime, limit: int) -> list[DueCheck]:
        stmt = (
            select(ScheduledCheckModel)
            .where(
                ScheduledCheckModel.tenant_id == tenant_id,
                ScheduledCheckModel.due_at <= now,
                ScheduledCheckModel.fired_at.is_(None),
                ScheduledCheckModel.cancelled_at.is_(None),
            )
            # Les plus anciennes d'abord : après une panne de cron, on rattrape dans l'ordre où
            # les échéances sont tombées, pas dans un ordre arbitraire.
            .order_by(ScheduledCheckModel.due_at)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            DueCheck(
                id=r.id,
                tenant_id=r.tenant_id,
                subject_id=r.subject_id,
                kind=r.kind,
                reason=r.reason,
                due_at=_aware(r.due_at),
            )
            for r in rows
        ]

    async def mark_fired(self, *, check_id: UUID, at: datetime) -> None:
        await self._session.execute(
            update(ScheduledCheckModel)
            .where(ScheduledCheckModel.id == check_id)
            .values(fired_at=at)
        )
        await self._session.flush()

    async def pending_count(self, *, tenant_id: UUID, now: datetime) -> int:
        stmt = select(func.count()).where(
            ScheduledCheckModel.tenant_id == tenant_id,
            ScheduledCheckModel.due_at <= now,
            ScheduledCheckModel.fired_at.is_(None),
            ScheduledCheckModel.cancelled_at.is_(None),
        )
        return int((await self._session.execute(stmt)).scalar_one())
