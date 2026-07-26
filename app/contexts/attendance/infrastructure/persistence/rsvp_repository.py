"""Implémentation SQLAlchemy de `GatheringRsvpRepository` (M6, « je viens »)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.attendance.domain.repositories import GatheringRsvpRepository
from app.contexts.attendance.domain.rsvp import GatheringRsvp
from app.contexts.attendance.infrastructure.persistence.models import GatheringRsvpModel


class SqlGatheringRsvpRepository(GatheringRsvpRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_for(self, rsvp: GatheringRsvp) -> None:
        stmt = select(GatheringRsvpModel).where(
            GatheringRsvpModel.gathering_id == rsvp.gathering_id,
            GatheringRsvpModel.account_id == rsvp.account_id,
        )
        if (await self._session.execute(stmt)).scalars().first() is not None:
            return  # idempotent : déjà posé
        self._session.add(
            GatheringRsvpModel(
                id=rsvp.id,
                gathering_id=rsvp.gathering_id,
                account_id=rsvp.account_id,
                rsvp_at=rsvp.rsvp_at,
            )
        )
        await self._session.flush()

    async def remove(self, gathering_id: UUID, account_id: UUID) -> None:
        await self._session.execute(
            delete(GatheringRsvpModel).where(
                GatheringRsvpModel.gathering_id == gathering_id,
                GatheringRsvpModel.account_id == account_id,
            )
        )

    async def list_account_ids_for(self, gathering_id: UUID) -> set[UUID]:
        stmt = select(GatheringRsvpModel.account_id).where(
            GatheringRsvpModel.gathering_id == gathering_id
        )
        return set((await self._session.execute(stmt)).scalars().all())
