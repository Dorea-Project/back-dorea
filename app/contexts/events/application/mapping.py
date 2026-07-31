"""Mappage agrégat → DTO (module Event)."""

from __future__ import annotations

from app.contexts.events.application.dtos import EventDTO, ParticipantDTO
from app.contexts.events.domain.aggregates import Event, EventParticipant


def to_event_dto(
    event: Event,
    *,
    participant_count: int | None = None,
    my_reaction: str | None = None,
    i_confirmed: bool = False,
) -> EventDTO:
    return EventDTO(
        id=event.id,
        author_account_id=event.author_account_id,
        category=event.category.value,
        title=event.title,
        description=event.description,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        place_label=event.place_label,
        latitude=event.latitude,
        longitude=event.longitude,
        media_urls=list(event.media_urls),
        scope=event.scope.value,
        status=event.status.value,
        created_at=event.created_at,
        participant_count=participant_count,
        my_reaction=my_reaction,
        i_confirmed=i_confirmed,
    )


def to_participant_dto(p: EventParticipant) -> ParticipantDTO:
    return ParticipantDTO(account_id=p.account_id, confirmed_at=p.confirmed_at)
