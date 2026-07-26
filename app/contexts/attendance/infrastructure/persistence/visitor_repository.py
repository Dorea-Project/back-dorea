"""Implémentation SQLAlchemy de `VisitorRepository` (M6-3)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.attendance.domain.repositories import VisitorRepository
from app.contexts.attendance.domain.visitor import Visitor
from app.contexts.attendance.infrastructure.persistence.models import GatheringVisitorModel


def _to_visitor(row: GatheringVisitorModel) -> Visitor:
    return Visitor(
        id=row.id,
        gathering_id=row.gathering_id,
        tenant_id=row.tenant_id,
        name=row.name,
        phone=row.phone,
        captured_by_account_id=row.captured_by_account_id,
        captured_at=row.captured_at,
    )


class SqlVisitorRepository(VisitorRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, visitor: Visitor) -> None:
        self._session.add(
            GatheringVisitorModel(
                id=visitor.id,
                gathering_id=visitor.gathering_id,
                tenant_id=visitor.tenant_id,
                name=visitor.name,
                phone=visitor.phone,
                captured_by_account_id=visitor.captured_by_account_id,
                captured_at=visitor.captured_at,
            )
        )
        await self._session.flush()

    async def get(self, visitor_id: UUID) -> Visitor | None:
        row = await self._session.get(GatheringVisitorModel, visitor_id)
        return _to_visitor(row) if row is not None else None

    async def remove(self, visitor_id: UUID) -> None:
        await self._session.execute(
            delete(GatheringVisitorModel).where(GatheringVisitorModel.id == visitor_id)
        )

    async def list_for_gathering(self, gathering_id: UUID) -> list[Visitor]:
        stmt = select(GatheringVisitorModel).where(
            GatheringVisitorModel.gathering_id == gathering_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_visitor(r) for r in rows]
