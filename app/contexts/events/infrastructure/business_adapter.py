"""Adaptateur du port `BusinessTierPort` — lit le module Billing.

Publier au-delà de son église exige que l'auteur ait le compte Business ; ce pont le vérifie."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.billing.infrastructure.persistence.repository import (
    SqlBusinessAccountRepository,
)
from app.contexts.events.application.ports import BusinessTierPort


class BillingBusinessTierAdapter(BusinessTierPort):
    def __init__(self, session: AsyncSession) -> None:
        self._accounts = SqlBusinessAccountRepository(session)

    async def is_business(self, account_id: UUID) -> bool:
        account = await self._accounts.get_by_account(account_id)
        return account is not None and account.is_business
