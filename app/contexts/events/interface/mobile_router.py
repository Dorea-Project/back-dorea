"""Routes **mobile** du module Event — tout le monde publie, réagit, confirme sa présence.

Portée église (gratuit) en E-0 ; le rayonnement dénomination/plateforme (compte Business) viendra.
JWT mobile.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.events.interface.dependencies import (
    CancelEventDep,
    ConfirmParticipationDep,
    GetEventDep,
    GetEventStatsDep,
    ListParticipantsDep,
    ListVisibleEventsDep,
    PublishEventDep,
    ReactToEventDep,
    RecordEventViewDep,
    ReportEventDep,
    WithdrawParticipationDep,
)
from app.contexts.events.interface.schemas import (
    EventFeedView,
    EventStatsView,
    EventView,
    ParticipantListView,
    PublishEventBody,
    ReactEventBody,
    ReportEventBody,
)

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}",
    response_model=EventView,
    status_code=status.HTTP_201_CREATED,
    summary="Publier un événement pour son église (au-delà : compte Business, à venir)",
)
async def publish_event(
    tenant_id: UUID,
    payload: PublishEventBody,
    actor: CurrentActor,
    command: PublishEventDep,
) -> EventView:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        category=payload.category,
        title=payload.title,
        starts_at=payload.starts_at,
        scope=payload.scope,
        description=payload.description,
        ends_at=payload.ends_at,
        place_label=payload.place_label,
        latitude=payload.latitude,
        longitude=payload.longitude,
        media_urls=payload.media_urls,
    )
    return EventView.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}",
    response_model=EventFeedView,
    summary="Le fil des événements qui m'atteignent : mon église + ma dénomination + la plateforme",
)
async def events_feed(
    tenant_id: UUID,
    actor: CurrentActor,
    query: ListVisibleEventsDep,
) -> EventFeedView:
    dtos = await query.execute(tenant_id=tenant_id, viewer_account_id=actor.account_id)
    return EventFeedView.from_dtos(dtos)


@router.get(
    "/{event_id}",
    response_model=EventView,
    summary="Le détail d'un événement (+ ma réaction, ma présence, les compteurs)",
)
async def event_detail(
    event_id: UUID,
    actor: CurrentActor,
    query: GetEventDep,
) -> EventView:
    dto = await query.execute(event_id=event_id, viewer_account_id=actor.account_id)
    return EventView.from_dto(dto)


@router.post(
    "/{event_id}/react",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Réagir à un événement (ça m'intéresse / ça m'édifie / je prie)",
)
async def react(
    event_id: UUID,
    payload: ReactEventBody,
    actor: CurrentActor,
    command: ReactToEventDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id, event_id=event_id, kind=payload.kind
    )


@router.post(
    "/{event_id}/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirmer ma présence (« je serai là »)",
)
async def confirm(
    event_id: UUID,
    actor: CurrentActor,
    command: ConfirmParticipationDep,
) -> None:
    await command.execute(actor_account_id=actor.account_id, event_id=event_id)


@router.post(
    "/{event_id}/withdraw",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer ma présence",
)
async def withdraw(
    event_id: UUID,
    actor: CurrentActor,
    command: WithdrawParticipationDep,
) -> None:
    await command.execute(actor_account_id=actor.account_id, event_id=event_id)


@router.post(
    "/{event_id}/cancel",
    response_model=EventView,
    summary="Annuler mon événement (l'organisateur seul)",
)
async def cancel_event(
    event_id: UUID,
    actor: CurrentActor,
    command: CancelEventDep,
) -> EventView:
    dto = await command.execute(actor_account_id=actor.account_id, event_id=event_id)
    return EventView.from_dto(dto)


@router.get(
    "/{event_id}/participants",
    response_model=ParticipantListView,
    summary="La liste des présents — réservée à l'organisateur",
)
async def participants(
    event_id: UUID,
    actor: CurrentActor,
    query: ListParticipantsDep,
) -> ParticipantListView:
    dtos = await query.execute(actor_account_id=actor.account_id, event_id=event_id)
    return ParticipantListView.from_dtos(dtos)


@router.post(
    "/{event_id}/view",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Signaler que j'ai vu l'événement (trace le rayonnement — spectateurs distincts)",
)
async def record_view(
    event_id: UUID,
    actor: CurrentActor,
    command: RecordEventViewDep,
) -> None:
    await command.execute(actor_account_id=actor.account_id, event_id=event_id)


@router.post(
    "/{event_id}/report",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Signaler un événement inapproprié (le garde-fou de la diffusion élargie)",
)
async def report(
    event_id: UUID,
    payload: ReportEventBody,
    actor: CurrentActor,
    command: ReportEventDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id, event_id=event_id, reason=payload.reason
    )


@router.get(
    "/{event_id}/stats",
    response_model=EventStatsView,
    summary="Le rayonnement de mon événement (portée, vus par dénomination, intéressés, présents)",
)
async def event_stats(
    event_id: UUID,
    actor: CurrentActor,
    query: GetEventStatsDep,
) -> EventStatsView:
    dto = await query.execute(actor_account_id=actor.account_id, event_id=event_id)
    return EventStatsView.from_dto(dto)
