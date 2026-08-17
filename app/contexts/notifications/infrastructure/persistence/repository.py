"""Dépôt SQLAlchemy du module Notifications."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app._shared.messages import MessageKey
from app.contexts.notifications.domain.aggregates import Device, ScheduledNotification
from app.contexts.notifications.domain.enums import DevicePlatform, ScheduledStatus
from app.contexts.notifications.domain.repositories import (
    DeviceRepository,
    ScheduledNotificationRepository,
)
from app.contexts.notifications.infrastructure.persistence.models import (
    DeviceModel,
    ScheduledNotificationModel,
)


def _to_device(row: DeviceModel) -> Device:
    return Device(
        id=row.id,
        account_id=row.account_id,
        token=row.token,
        platform=DevicePlatform(row.platform),
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
    )


class SqlDeviceRepository(DeviceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_token(self, token: str) -> Device | None:
        stmt = select(DeviceModel).where(DeviceModel.token == token)
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_device(row) if row is not None else None

    async def add(self, device: Device) -> None:
        self._session.add(
            DeviceModel(
                id=device.id,
                account_id=device.account_id,
                token=device.token,
                platform=device.platform.value,
                created_at=device.created_at,
                last_seen_at=device.last_seen_at,
            )
        )
        await self._session.flush()

    async def save(self, device: Device) -> None:
        row = await self._session.get(DeviceModel, device.id)
        if row is None:
            return
        row.account_id = device.account_id
        row.platform = device.platform.value
        row.last_seen_at = device.last_seen_at
        await self._session.flush()

    async def remove_by_token(self, token: str, *, account_id: UUID) -> None:
        # DOREA-023 — le compte est dans le WHERE : on ne peut pas effacer le jeton d'autrui.
        await self._session.execute(
            delete(DeviceModel).where(
                DeviceModel.token == token, DeviceModel.account_id == account_id
            )
        )
        await self._session.flush()

    async def list_by_account(self, account_id: UUID) -> list[Device]:
        stmt = select(DeviceModel).where(DeviceModel.account_id == account_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_device(r) for r in rows]

    async def tokens_by_account(self, account_ids: list[UUID]) -> dict[UUID, list[str]]:
        if not account_ids:
            return {}
        stmt = select(DeviceModel.account_id, DeviceModel.token).where(
            DeviceModel.account_id.in_(account_ids)
        )
        grouped: dict[UUID, list[str]] = {}
        for account_id, token in (await self._session.execute(stmt)).all():
            grouped.setdefault(account_id, []).append(token)
        return grouped


def _to_job(row: ScheduledNotificationModel) -> ScheduledNotification:
    return ScheduledNotification(
        id=row.id,
        account_ids=[UUID(str(a)) for a in (row.account_ids or [])],
        key=MessageKey(row.message_key) if row.message_key else None,
        params=row.params or {},
        data=row.data,
        scheduled_for=row.scheduled_for,
        status=ScheduledStatus(row.status),
        created_at=row.created_at,
        sent_at=row.sent_at,
        legacy_title=row.title,
        legacy_body=row.body,
    )


class SqlScheduledNotificationRepository(ScheduledNotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: ScheduledNotification) -> None:
        self._session.add(
            ScheduledNotificationModel(
                id=job.id,
                account_ids=[str(a) for a in job.account_ids],
                message_key=job.key.value if job.key else None,
                params=dict(job.params),
                data=job.data,
                scheduled_for=job.scheduled_for,
                status=job.status.value,
                created_at=job.created_at,
                sent_at=job.sent_at,
            )
        )
        await self._session.flush()

    async def save(self, job: ScheduledNotification) -> None:
        row = await self._session.get(ScheduledNotificationModel, job.id)
        if row is None:
            return
        row.status = job.status.value
        row.sent_at = job.sent_at
        await self._session.flush()

    async def list_due(
        self, now: datetime, *, limit: int
    ) -> list[ScheduledNotification]:
        stmt = (
            select(ScheduledNotificationModel)
            .where(
                ScheduledNotificationModel.status == ScheduledStatus.PENDING.value,
                ScheduledNotificationModel.scheduled_for <= now,
            )
            .order_by(ScheduledNotificationModel.scheduled_for)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_job(r) for r in rows]
