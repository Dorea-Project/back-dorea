"""Port de persistance du module Billing."""

from abc import abstractmethod
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.billing.domain.aggregates import BusinessAccount


class BusinessAccountRepository(Repository):
    @abstractmethod
    async def get_by_account(self, account_id: UUID) -> BusinessAccount | None: ...

    @abstractmethod
    async def add(self, account: BusinessAccount) -> None: ...

    @abstractmethod
    async def save(self, account: BusinessAccount) -> None:
        """Persiste l'ajout / le retrait de la carte."""
        ...
