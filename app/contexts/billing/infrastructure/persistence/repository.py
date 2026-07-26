"""Dépôt SQLAlchemy du module Billing."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.billing.domain.aggregates import BusinessAccount, PaymentCard
from app.contexts.billing.domain.repositories import BusinessAccountRepository
from app.contexts.billing.infrastructure.persistence.models import BusinessAccountModel


def _card(row: BusinessAccountModel) -> PaymentCard | None:
    if row.card_brand is None:
        return None
    return PaymentCard(
        brand=row.card_brand,
        last4=row.card_last4 or "",
        prepaid=bool(row.card_prepaid),
        exp_month=row.card_exp_month or 0,
        exp_year=row.card_exp_year or 0,
        added_at=row.card_added_at,
        provider_token=row.card_provider_token,
    )


def _to_account(row: BusinessAccountModel) -> BusinessAccount:
    return BusinessAccount(
        id=row.id,
        account_id=row.account_id,
        card=_card(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _write_card(row: BusinessAccountModel, account: BusinessAccount) -> None:
    card = account.card
    row.card_brand = card.brand if card else None
    row.card_last4 = card.last4 if card else None
    row.card_prepaid = card.prepaid if card else None
    row.card_exp_month = card.exp_month if card else None
    row.card_exp_year = card.exp_year if card else None
    row.card_provider_token = card.provider_token if card else None
    row.card_added_at = card.added_at if card else None
    row.updated_at = account.updated_at


class SqlBusinessAccountRepository(BusinessAccountRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_account(self, account_id: UUID) -> BusinessAccount | None:
        stmt = select(BusinessAccountModel).where(
            BusinessAccountModel.account_id == account_id
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_account(row) if row is not None else None

    async def add(self, account: BusinessAccount) -> None:
        row = BusinessAccountModel(
            id=account.id,
            account_id=account.account_id,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )
        _write_card(row, account)
        self._session.add(row)
        await self._session.flush()

    async def save(self, account: BusinessAccount) -> None:
        row = await self._session.get(BusinessAccountModel, account.id)
        if row is None:
            return
        _write_card(row, account)
        await self._session.flush()
