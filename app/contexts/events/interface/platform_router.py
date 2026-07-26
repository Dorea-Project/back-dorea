"""Routes **Plateforme** de modération des événements — Dorea, l'admin central.

Gouverner le rayonnement élargi : voir la file des événements signalés, en **retirer** un. Gardée
par le **jeton de service Plateforme** (`require_platform_token`) — aucune église ne modère au-delà
d'elle-même. *Révélateur, pas juge* : le signalement éclaire, l'humain de la Plateforme tranche.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.contexts.events.interface.dependencies import (
    ListReportedEventsDep,
    TakeDownEventDep,
)
from app.contexts.events.interface.schemas import (
    EventView,
    ReportedEventListView,
    TakeDownEventBody,
)
from app.contexts.tenant.interface.dependencies import require_platform_token

router = APIRouter(dependencies=[Depends(require_platform_token)])


@router.get(
    "/events/reported",
    response_model=ReportedEventListView,
    summary="La file de revue : les événements signalés (les plus signalés d'abord)",
)
async def reported(query: ListReportedEventsDep) -> ReportedEventListView:
    dtos = await query.execute()
    return ReportedEventListView.from_dtos(dtos)


@router.post(
    "/events/{event_id}/takedown",
    response_model=EventView,
    summary="Retirer un événement (modération Plateforme)",
)
async def takedown(
    event_id: UUID,
    payload: TakeDownEventBody,
    command: TakeDownEventDep,
) -> EventView:
    dto = await command.execute(event_id=event_id, reason=payload.reason)
    return EventView.from_dto(dto)
