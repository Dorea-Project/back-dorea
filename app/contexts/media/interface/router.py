"""Routes d'**upload média** (images d'annonces) — mobile & backoffice.

Upload par **corps brut** (les octets de l'image dans le body + `Content-Type`), sans multipart :
`PUT /media` renvoie `{ "url": … }` que M8 place dans `media_urls`. Authentifié (le membre/le staff
qui publie). Le validateur borne type (images) et taille.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from pydantic import BaseModel

from app._shared.interface.request_body import read_body_capped
from app.api.deps import SettingsDep
from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser
from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.media.application.media_store import validate_upload
from app.contexts.media.interface.dependencies import MediaStoreDep


class UploadResponse(BaseModel):
    url: str


async def _do_upload(request: Request, store, settings) -> UploadResponse:
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    # Lecture **bornée** : on rejette avant de bufferiser tout le corps (anti-DoS mémoire).
    body = await read_body_capped(request, max_bytes=settings.media_max_bytes)
    validate_upload(
        content_type,
        len(body),
        max_bytes=settings.media_max_bytes,
        allowed_types=settings.media_allowed_types,
    )
    url = await store.put(body, content_type=content_type)
    return UploadResponse(url=url)


mobile_router = APIRouter()
backoffice_router = APIRouter()


@mobile_router.put(
    "/media",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Téléverser une image (corps brut) → renvoie l'URL pour media_urls (M8)",
)
async def upload_mobile(
    request: Request,
    actor: CurrentActor,
    store: MediaStoreDep,
    settings: SettingsDep,
) -> UploadResponse:
    return await _do_upload(request, store, settings)


@backoffice_router.put(
    "/media",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Téléverser une image depuis le backoffice → renvoie l'URL",
)
async def upload_backoffice(
    request: Request,
    actor: CurrentBackofficeUser,
    store: MediaStoreDep,
    settings: SettingsDep,
) -> UploadResponse:
    return await _do_upload(request, store, settings)
