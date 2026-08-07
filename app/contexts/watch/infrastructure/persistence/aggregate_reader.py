"""Implémentation SQL de `AggregateReader` — une requête qui ne sait pas nommer.

La requête ne **sélectionne** que l'origine et un compte. `subject_id` et `owner_account_id`
n'apparaissent nulle part : ils ne sont pas filtrés de la sortie, ils ne sont **jamais lus**.
Un test le vérifie sur le SQL compilé.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.aggregates import (
    CONFIDENTIALITY_THRESHOLD,
    AggregateReader,
    TopicCount,
)
from app.contexts.watch.infrastructure.persistence.models import SignalModel


class SqlAggregateReader(AggregateReader):
    def __init__(self, session: AsyncSession, *, clock) -> None:
        self._session = session
        self._clock = clock

    def _statement(self, tenant_id: UUID, since: datetime):
        """Isolée pour être inspectable par le test d'architecture."""
        return (
            select(SignalModel.origin, func.count().label("headcount"))
            .where(SignalModel.tenant_id == tenant_id, SignalModel.opened_at >= since)
            .group_by(SignalModel.origin)
            # Le seuil vit ICI : sous cinq, le groupe ne quitte pas la base.
            .having(func.count() >= CONFIDENTIALITY_THRESHOLD)
        )

    async def counts_by_origin(
        self, tenant_id: UUID, *, window_days: int
    ) -> tuple[TopicCount, ...]:
        since = self._clock() - timedelta(days=window_days)
        rows = (await self._session.execute(self._statement(tenant_id, since))).all()
        return tuple(
            TopicCount(topic=origin, headcount=headcount, window_days=window_days)
            for origin, headcount in rows
        )
