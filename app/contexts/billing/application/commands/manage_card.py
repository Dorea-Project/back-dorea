"""Use cases **de la personne** — enregistrer / retirer sa carte prépayée Visa.

Enregistrer une carte prépayée Visa **ouvre le tier Business** (non facturé). La retirer revient au
tier gratuit. Une personne gère **son propre** compte de facturation.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.billing.application.dtos import BusinessStatusDTO
from app.contexts.billing.application.mapping import to_status_dto
from app.contexts.billing.domain.aggregates import BusinessAccount, PaymentCard
from app.contexts.billing.domain.repositories import BusinessAccountRepository


class AddPaymentCard:
    def __init__(self, accounts: BusinessAccountRepository, *, clock) -> None:
        self._accounts = accounts
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        brand: str,
        last4: str,
        prepaid: bool,
        exp_month: int,
        exp_year: int,
        provider_token: str | None = None,
    ) -> BusinessStatusDTO:
        now = self._clock()
        card = PaymentCard(
            brand=brand,
            last4=last4,
            prepaid=prepaid,
            exp_month=exp_month,
            exp_year=exp_year,
            added_at=now,
            provider_token=provider_token,
        )
        account = await self._accounts.get_by_account(actor_account_id)
        if account is None:
            account = BusinessAccount.open_free(
                id=uuid4(), account_id=actor_account_id, now=now
            )
            account.add_card(card, now=now)  # valide (prépayée Visa) avant d'enregistrer
            await self._accounts.add(account)
        else:
            account.add_card(card, now=now)
            await self._accounts.save(account)
        return to_status_dto(account)


class RemovePaymentCard:
    def __init__(self, accounts: BusinessAccountRepository, *, clock) -> None:
        self._accounts = accounts
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID) -> BusinessStatusDTO:
        account = await self._accounts.get_by_account(actor_account_id)
        if account is None or account.card is None:
            return to_status_dto(account)  # déjà gratuit — idempotent
        account.remove_card(now=self._clock())
        await self._accounts.save(account)
        return to_status_dto(account)
