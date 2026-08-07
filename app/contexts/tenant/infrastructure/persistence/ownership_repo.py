"""Implémentation SQLAlchemy de `OwnershipRepository`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.tenant.domain.enums import OwnershipMode, OwnershipStatus
from app.contexts.tenant.domain.ownership import Ownership
from app.contexts.tenant.domain.repositories import OwnershipRepository
from app.contexts.tenant.infrastructure.persistence.models import OwnershipModel

_ACTIVE = OwnershipStatus.ACTIVE.value


def _to_ownership(row: OwnershipModel) -> Ownership:
    return Ownership(
        id=row.id,
        account_id=row.account_id,
        tenant_id=row.tenant_id,
        mode=OwnershipMode(row.mode),
        started_at=row.started_at,
        status=OwnershipStatus(row.status),
        ended_at=row.ended_at,
    )


class SqlOwnershipRepository(OwnershipRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_active_owner(self, account_id: UUID, tenant_id: UUID) -> bool:
        stmt = select(OwnershipModel.id).where(
            OwnershipModel.account_id == account_id,
            OwnershipModel.tenant_id == tenant_id,
            OwnershipModel.status == _ACTIVE,
        )
        return (await self._session.execute(stmt)).first() is not None

    async def get_active_for_tenant(self, tenant_id: UUID) -> Ownership | None:
        stmt = select(OwnershipModel).where(
            OwnershipModel.tenant_id == tenant_id,
            OwnershipModel.status == _ACTIVE,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_ownership(row) if row is not None else None

    async def list_active_tenant_ids(self, account_id: UUID) -> list[UUID]:
        stmt = (
            select(OwnershipModel.tenant_id)
            .where(
                OwnershipModel.account_id == account_id,
                OwnershipModel.status == _ACTIVE,
            )
            .order_by(OwnershipModel.started_at)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def add(self, ownership: Ownership) -> None:
        self._session.add(
            OwnershipModel(
                id=ownership.id,
                account_id=ownership.account_id,
                tenant_id=ownership.tenant_id,
                status=ownership.status.value,
                mode=ownership.mode.value,
                started_at=ownership.started_at,
                ended_at=ownership.ended_at,
            )
        )
        await self._session.flush()

    async def end_active(self, tenant_id: UUID, ended_at: datetime) -> None:
        await self._session.execute(
            update(OwnershipModel)
            .where(OwnershipModel.tenant_id == tenant_id, OwnershipModel.status == _ACTIVE)
            .values(status=OwnershipStatus.ENDED.value, ended_at=ended_at)
        )
        await self._session.flush()
