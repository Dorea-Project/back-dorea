"""Routes **backoffice** des Annonces (M8) — la secrétaire sur son PWA.

Elle publie pour toute la communauté (ou une portée), consulte **l'archive** (tout, y compris
archivé/expiré) et voit qui s'est engagé. Cookie de session backoffice.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.announcements.interface.dependencies import (
    ArchiveAnnouncementDep,
    ListChurchAnnouncementsDep,
    ListRespondersDep,
    PublishAnnouncementDep,
)
from app.contexts.announcements.interface.schemas import (
    AnnouncementFeedView,
    AnnouncementView,
    PublishAnnouncementRequest,
    ResponderListView,
)
from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}/announcements",
    response_model=AnnouncementView,
    status_code=status.HTTP_201_CREATED,
    summary="Publier depuis le backoffice (toute la communauté, ou une portée)",
)
async def publish(
    tenant_id: UUID,
    payload: PublishAnnouncementRequest,
    actor: CurrentBackofficeUser,
    command: PublishAnnouncementDep,
) -> AnnouncementView:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        category=payload.category,
        title=payload.title,
        intent=payload.intent,
        scope_group_id=payload.scope_group_id,
        concerns_account_id=payload.concerns_account_id,
        body=payload.body,
        media_urls=payload.media_urls,
        event_at=payload.event_at,
        gathering_id=payload.gathering_id,
        slots_needed=payload.slots_needed,
        expires_at=payload.expires_at,
    )
    return AnnouncementView.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/announcements",
    response_model=AnnouncementFeedView,
    summary="L'archive de l'église : toutes les annonces (y compris archivées/expirées)",
)
async def list_church(
    tenant_id: UUID,
    actor: CurrentBackofficeUser,
    query: ListChurchAnnouncementsDep,
) -> AnnouncementFeedView:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return AnnouncementFeedView.from_dto(dto)


@router.get(
    "/{announcement_id}/responders",
    response_model=ResponderListView,
    summary="Qui s'est engagé (les noms)",
)
async def responders(
    announcement_id: UUID,
    actor: CurrentBackofficeUser,
    query: ListRespondersDep,
) -> ResponderListView:
    dto = await query.execute(
        actor_account_id=actor.account_id, announcement_id=announcement_id
    )
    return ResponderListView.from_dto(dto)


@router.post(
    "/{announcement_id}/archive",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver une annonce (sortir du fil ; reste consultable)",
)
async def archive(
    announcement_id: UUID,
    actor: CurrentBackofficeUser,
    command: ArchiveAnnouncementDep,
) -> None:
    await command.execute(actor_account_id=actor.account_id, announcement_id=announcement_id)
