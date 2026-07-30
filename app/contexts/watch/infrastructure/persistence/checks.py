"""Implémentation SQLAlchemy de `ScheduledCheckStore` — les échéances du moteur."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.ports import ScheduledCheckStore
from app.contexts.watch.infrastructure.persistence.models import ScheduledCheckModel


@dataclass(frozen=True)
class DueCheck:
    """Une échéance arrivée à terme. `reason` et `payload` voyagent jusqu'au fait émis."""

    id: UUID
    tenant_id: UUID
    subject_id: UUID
    kind: str
    reason: str
    due_at: datetime
    payload: Mapping[str, Any] = MappingProxyType({})


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
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        # Idempotence : rejouer le ledger ne doit pas empiler trois fois la même échéance.
        #
        # Le filtre porte sur **tous les états**, tirées et annulées comprises. Une échéance déjà
        # tombée ne doit pas être reposée par un rejeu : elle retomberait, et la personne serait
        # relancée une seconde fois pour un silence qu'on a déjà constaté. Le tir est un **acte**,
        # pas une dérivation du journal — c'est ce qui le distingue de la pose.
        existing = await self._session.execute(
            select(ScheduledCheckModel.id).where(
                ScheduledCheckModel.tenant_id == tenant_id,
                ScheduledCheckModel.subject_id == subject_id,
                ScheduledCheckModel.kind == kind,
                ScheduledCheckModel.due_at == due_at,
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
                payload=dict(payload or {}),
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
        # Deux passes de cron qui se chevauchent ne doivent pas tirer la même échéance : la
        # seconde saute les lignes déjà prises plutôt que d'attendre — elle a d'autres échéances
        # à traiter, et une relance en double est reçue comme un harcèlement.
        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            DueCheck(
                id=r.id,
                tenant_id=r.tenant_id,
                subject_id=r.subject_id,
                kind=r.kind,
                reason=r.reason,
                due_at=_aware(r.due_at),
                payload=dict(r.payload or {}),
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

    async def purge_projected(self, tenant_id: UUID) -> None:
        """N'efface que ce qui **pend**. Ce qui est tiré ou annulé est de l'histoire.

        La pose est une projection du ledger ; le tir et l'annulation sont des actes. Effacer les
        échéances tirées, c'est autoriser le rejeu à les reposer — donc à relancer une seconde fois
        des gens dont on a déjà constaté le silence."""
        await self._session.execute(
            delete(ScheduledCheckModel).where(
                ScheduledCheckModel.tenant_id == tenant_id,
                ScheduledCheckModel.fired_at.is_(None),
                ScheduledCheckModel.cancelled_at.is_(None),
            )
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
