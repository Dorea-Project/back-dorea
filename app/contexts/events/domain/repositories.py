"""Ports de persistance du module Event."""

from abc import abstractmethod
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.events.domain.aggregates import (
    Event,
    EventParticipant,
    EventReactionEntry,
    EventReport,
    EventView,
)
from app.contexts.events.domain.enums import EventReaction, EventScope


class EventRepository(Repository):
    @abstractmethod
    async def add(self, event: Event) -> None: ...

    @abstractmethod
    async def get(self, event_id: UUID) -> Event | None: ...

    @abstractmethod
    async def save(self, event: Event) -> None:
        """Persiste une annulation."""
        ...

    @abstractmethod
    async def list_published_by_tenant(self, tenant_id: UUID) -> list[Event]:
        """Tous les événements publiés d'une église (toutes portées)."""
        ...

    @abstractmethod
    async def list_published_by_scope(
        self, scope: EventScope, tenant_ids: list[UUID] | None = None
    ) -> list[Event]:
        """Les événements publiés d'une **portée** donnée ; filtrés sur un ensemble d'églises
        (`tenant_ids`) pour la dénomination, ou tous (`None`) pour la plateforme."""
        ...


class EventParticipantRepository(Repository):
    @abstractmethod
    async def add(self, participant: EventParticipant) -> None: ...

    @abstractmethod
    async def get(self, event_id: UUID, account_id: UUID) -> EventParticipant | None: ...

    @abstractmethod
    async def remove(self, event_id: UUID, account_id: UUID) -> None: ...

    @abstractmethod
    async def list_by_event(self, event_id: UUID) -> list[EventParticipant]:
        """La liste des confirmés — réservée à l'organisateur."""
        ...

    @abstractmethod
    async def count_by_event(self, event_id: UUID) -> int: ...


class EventReactionRepository(Repository):
    @abstractmethod
    async def get_for(self, event_id: UUID, account_id: UUID) -> EventReactionEntry | None: ...

    @abstractmethod
    async def add(self, reaction: EventReactionEntry) -> None: ...

    @abstractmethod
    async def remove(self, event_id: UUID, account_id: UUID) -> None: ...

    @abstractmethod
    async def counts_by_kind(self, event_id: UUID) -> dict[EventReaction, int]: ...


class EventViewRepository(Repository):
    @abstractmethod
    async def get(self, event_id: UUID, viewer_account_id: UUID) -> EventView | None: ...

    @abstractmethod
    async def add(self, view: EventView) -> None: ...

    @abstractmethod
    async def count_by_event(self, event_id: UUID) -> int: ...

    @abstractmethod
    async def counts_by_denomination(self, event_id: UUID) -> dict[str | None, int]:
        """Les vues ventilées par dénomination (None = spectateurs d'églises indépendantes)."""
        ...


class EventReportRepository(Repository):
    @abstractmethod
    async def get(self, event_id: UUID, reporter_account_id: UUID) -> EventReport | None: ...

    @abstractmethod
    async def add(self, report: EventReport) -> None: ...

    @abstractmethod
    async def count_by_event(self, event_id: UUID) -> int: ...

    @abstractmethod
    async def counts_by_event(self) -> dict[UUID, int]:
        """Le nombre de signalements par événement — nourrit la file de revue de la Plateforme."""
        ...
