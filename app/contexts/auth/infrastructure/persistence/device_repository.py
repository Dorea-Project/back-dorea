"""Implémentation SQLAlchemy de `DeviceRepository`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.auth.domain.repositories import DeviceRepository
from app.contexts.auth.infrastructure.persistence.models import DeviceModel


class SqlDeviceRepository(DeviceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_trusted(self, account_id: UUID, device_id: str) -> bool:
        stmt = select(DeviceModel.id).where(
            DeviceModel.account_id == account_id,
            DeviceModel.device_id == device_id,
        )
        return (await self._session.execute(stmt)).first() is not None

    async def trust(self, account_id: UUID, device_id: str, trusted_at: datetime) -> None:
        if await self.is_trusted(account_id, device_id):
            return  # idempotent
        self._session.add(
            DeviceModel(
                id=uuid4(),
                account_id=account_id,
                device_id=device_id,
                trusted_at=trusted_at,
            )
        )
        await self._session.flush()
