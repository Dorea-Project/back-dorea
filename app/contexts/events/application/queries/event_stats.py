"""Requête `GetEventStats` — le tableau de bord de rayonnement, réservé à l'organisateur.

Portée (audience potentielle), vues distinctes + ventilation par dénomination, intéressés
manifestés (réaction « ça m'intéresse »), présences confirmées, réactions.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.events.application.dtos import EventStatsDTO
from app.contexts.events.application.ports import EventAudiencePort
from app.contexts.events.domain.aggregates import NEARBY_RADIUS_KM
from app.contexts.events.domain.enums import EventReaction, EventScope
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

    async def _reach_of(self, event) -> int:
        """**Le dénominateur, et il doit suivre la portée.**

        Il ne comptait que l'église de l'auteur, quelle que soit la portée : un événement de
        voisinage aurait affiché « 40 vues sur 42 » alors qu'il en atteignait 662. Un taux dont
        le dénominateur est faux est pire qu'une absence de taux — il rassure.
        """
        if event.scope is EventScope.CHURCH:
            return await self._audience.count_active_members(event.tenant_id)
        if event.scope is EventScope.NEARBY:
            if event.latitude is None:
                return await self._audience.count_active_members(event.tenant_id)
            tenants = await self._audience.tenants_near(
                latitude=event.latitude,
                longitude=event.longitude,
                radius_km=NEARBY_RADIUS_KM,
            )
        elif event.scope is EventScope.DENOMINATION:
            denomination = await self._audience.denomination_of(event.tenant_id)
            tenants = (
                await self._audience.tenants_in_denomination(denomination)
                if denomination is not None
                else [event.tenant_id]
            )
        else:  # PLATFORM
            tenants = await self._audience.all_tenant_ids()
        return len(await self._audience.member_account_ids(tenants))

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
            reach=await self._reach_of(event),
            views_total=await self._views.count_by_event(event_id),
            views_by_denomination={(d or _INDEPENDENT): n for d, n in raw.items()},
            interested_count=reaction_counts.get(EventReaction.INTERESTED.value, 0),
            confirmed_count=await self._participants.count_by_event(event_id),
            reaction_counts=reaction_counts,
        )
