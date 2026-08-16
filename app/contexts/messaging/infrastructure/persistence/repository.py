"""Écriture des accusés et des refus."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.messaging.application.inbound import DeliveryReport
from app.contexts.messaging.domain.enums import Channel
from app.contexts.messaging.infrastructure.persistence.models import (
    DeliveryModel,
    OptOutModel,
)


class DeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, report: DeliveryReport, *, now: datetime) -> None:
        """Écrit le dernier état connu d'un message.

        En **upsert**, et c'est délibéré : le fournisseur peut parler avant nous
        (l'accusé arrive pendant que la transaction d'envoi n'est pas encore
        commise), et il peut parler plusieurs fois pour le même message —
        `sent`, puis `delivered`, puis `read`. Chaque nouvelle parole remplace
        la précédente ; on garde l'état, pas l'historique.
        """
        existing = await self._session.get(DeliveryModel, report.message_id)
        occurred = report.occurred_at or now

        if existing is None:
            self._session.add(
                DeliveryModel(
                    message_id=report.message_id,
                    channel=Channel.WHATSAPP.value,
                    purpose="unknown",
                    provider_message_id=report.provider_message_id,
                    status=report.status,
                    error_code=report.error_code,
                    error_text=report.error_text,
                    created_at=occurred,
                    updated_at=occurred,
                )
            )
            return

        existing.status = report.status
        existing.updated_at = occurred
        if report.provider_message_id is not None:
            existing.provider_message_id = report.provider_message_id
        if report.error_code is not None:
            existing.error_code = report.error_code
            existing.error_text = report.error_text

    async def get(self, message_id: str) -> DeliveryModel | None:
        return await self._session.get(DeliveryModel, message_id)


class OptOutRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, *, phone_number: str, channel: Channel, keyword: str, now: datetime
    ) -> None:
        existing = await self._session.get(OptOutModel, phone_number)
        if existing is not None:
            return  # déjà refusé : un second stop ne change rien

        self._session.add(
            OptOutModel(
                phone_number=phone_number,
                channel=channel.value,
                keyword=keyword,
                created_at=now,
            )
        )

    async def remove(self, phone_number: str) -> None:
        existing = await self._session.get(OptOutModel, phone_number)
        if existing is not None:
            await self._session.delete(existing)

    async def is_opted_out(self, phone_number: str) -> bool:
        found = await self._session.scalar(
            select(OptOutModel.phone_number).where(
                OptOutModel.phone_number == phone_number
            )
        )
        return found is not None
