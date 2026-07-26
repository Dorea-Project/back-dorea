"""Requête `GetBusinessStatus` — mon tier de compte (gratuit / business)."""

from __future__ import annotations

from uuid import UUID

from app.contexts.billing.application.dtos import BusinessStatusDTO
from app.contexts.billing.application.mapping import to_status_dto
from app.contexts.billing.domain.repositories import BusinessAccountRepository


class GetBusinessStatus:
    def __init__(self, accounts: BusinessAccountRepository) -> None:
        self._accounts = accounts

    async def execute(self, *, actor_account_id: UUID) -> BusinessStatusDTO:
        return to_status_dto(await self._accounts.get_by_account(actor_account_id))
