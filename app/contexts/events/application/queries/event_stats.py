"""Requête `GetEventStats` — le tableau de bord de rayonnement, réservé à l'organisateur.

Portée (audience potentielle), vues distinctes + ventilation par dénomination, intéressés
manifestés (réaction « ça m'intéresse »), présences confirmées, réactions.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.events.application.dtos import EventStatsDTO
from app.contexts.events.application.ports import EventAudiencePort
from app.contexts.events.domain.enums import EventReaction
from app.contexts.events.domain.errors import EventNotFoundError, NotEventAuthorError
from app.contexts.events.domain.repositories import (
    EventParticipantRepository,
    EventReactionRepository,
    EventRepository,
    EventViewRepository,
)

_INDEPENDENT = "indépendante"


class GetEventStats:
    def __init__(
        self,
        events: EventRepository,
        views: EventViewRepository,
        participants: EventParticipantRepository,
        reactions: EventReactionRepository,
        audience: EventAudiencePort,
    ) -> None:
        self._events = events
        self._views = views
        self._participants = participants
        self._reactions = reactions
        self._audience = audience

    async def execute(self, *, actor_account_id: UUID, event_id: UUID) -> EventStatsDTO:
        event = await self._events.get(event_id)
        if event is None:
            raise EventNotFoundError(
                "Événement introuvable.", details={"event_id": str(event_id)}
            )
        if event.author_account_id != actor_account_id:
            raise NotEventAuthorError(
                "Seul l'organisateur voit le rayonnement de son événement.",
                details={"event_id": str(event_id)},
            )
        reaction_counts = {
            k.value: n for k, n in (await self._reactions.counts_by_kind(event_id)).items()
        }
        raw = await self._views.counts_by_denomination(event_id)
        return EventStatsDTO(
            reach=await self._audience.count_active_members(event.tenant_id),
            views_total=await self._views.count_by_event(event_id),
            views_by_denomination={(d or _INDEPENDENT): n for d, n in raw.items()},
            interested_count=reaction_counts.get(EventReaction.INTERESTED.value, 0),
            confirmed_count=await self._participants.count_by_event(event_id),
            reaction_counts=reaction_counts,
        )
