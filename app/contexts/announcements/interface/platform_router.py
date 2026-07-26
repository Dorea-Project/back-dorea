"""Route **Plateforme** des Annonces (M8) — Dorea, l'admin central.

Une annonce Dorea atteint **toutes les églises** : elle n'appartient à aucun tenant et apparaît
dans le fil de chaque membre. Gardée par le **jeton de service Plateforme**
(`require_platform_token`), pas par une session d'église — aucune église n'en publie ni n'archive.
"""

from fastapi import APIRouter, Depends, status

from app.contexts.announcements.interface.dependencies import PublishPlatformDep
from app.contexts.announcements.interface.schemas import (
    AnnouncementView,
    PublishPlatformAnnouncementRequest,
)
from app.contexts.tenant.interface.dependencies import require_platform_token

router = APIRouter(dependencies=[Depends(require_platform_token)])


@router.post(
    "/announcements",
    response_model=AnnouncementView,
    status_code=status.HTTP_201_CREATED,
    summary="Publier une annonce Dorea (admin central) → toutes les églises",
)
async def publish_platform(
    payload: PublishPlatformAnnouncementRequest,
    command: PublishPlatformDep,
) -> AnnouncementView:
    dto = await command.execute(
        category=payload.category,
        title=payload.title,
        intent=payload.intent,
        body=payload.body,
        media_urls=payload.media_urls,
        expires_at=payload.expires_at,
    )
    return AnnouncementView.from_dto(dto)
