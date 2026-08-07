"""Port de persistance du module Notifications."""

from abc import abstractmethod
from datetime import datetime
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.notifications.domain.aggregates import Device, ScheduledNotification


class DeviceRepository(Repository):
    @abstractmethod
    async def get_by_token(self, token: str) -> Device | None: ...

    @abstractmethod
    async def add(self, device: Device) -> None: ...

    @abstractmethod
    async def save(self, device: Device) -> None: ...

    @abstractmethod
    async def remove_by_token(self, token: str, *, account_id: UUID) -> None:
        """Oublie un jeton — **borné à son propriétaire** (DOREA-023).

        Sans le compte, connaître un jeton suffisait à faire taire les notifications de
        quelqu'un d'autre. Un jeton n'est pas un secret : il transite, il se journalise,
        il s'échange entre l'app et le fournisseur push."""
        ...

    @abstractmethod
    async def list_by_account(self, account_id: UUID) -> list[Device]: ...

    @abstractmethod
    async def tokens_for_accounts(self, account_ids: list[UUID]) -> list[str]:
        """Tous les jetons des appareils des comptes visés — la cible d'un envoi."""
        ...


class ScheduledNotificationRepository(Repository):
    @abstractmethod
    async def add(self, job: ScheduledNotification) -> None: ...

    @abstractmethod
    async def save(self, job: ScheduledNotification) -> None: ...

    @abstractmethod
    async def list_due(self, now: datetime, *, limit: int) -> list[ScheduledNotification]:
        """Les notifications **en attente** dont l'heure est venue (`scheduled_for <= now`)."""
        ...
