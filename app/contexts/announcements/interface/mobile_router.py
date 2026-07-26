"""Routes **mobile** des Annonces (M8) — le fil d'actualité du membre.

L'admin/le responsable publie depuis le terrain ; le membre lit son fil (3 portées fusionnées :
Dorea, son église, ses groupes), **réagit** (emoji de la palette du type) et **s'engage**
(je viens / je sers / je porte). JWT mobile (`CurrentActor`).
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.announcements.domain.aggregates import SubjectDraft
from app.contexts.announcements.interface.dependencies import (
    ArchiveAnnouncementDep,
    DecideConsentDep,
    EngageAnnouncementDep,
    GetConsolationDep,
    ListMyAnnouncementsDep,
    ListRespondersDep,
    PublishAnnouncementDep,
    RemoveReactionDep,
    SetReactionDep,
    WithdrawEngagementDep,
)
from app.contexts.announcements.interface.schemas import (
    AnnouncementFeedView,
    AnnouncementView,
    ConsentRequest,
    ConsolationView,
    PublishAnnouncementRequest,
    ReactRequest,
    ResponderListView,
)
from app.contexts.auth.interface.dependencies import CurrentActor

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}/announcements",
    response_model=AnnouncementView,
    status_code=status.HTTP_201_CREATED,
    summary="Publier (type → couleur/emojis/intention ; portée groupe ou église-entière)",
)
async def publish(
    tenant_id: UUID,
    payload: PublishAnnouncementRequest,
    actor: CurrentActor,
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
        occurred_at=payload.occurred_at,
        subjects=[
            SubjectDraft(
                account_id=s.account_id,
                role=s.role,
                effects=tuple(s.effects) if s.effects is not None else None,
                declared_duration_days=s.declared_duration_days,
            )
            for s in payload.subjects
        ],
    )
    return AnnouncementView.from_dto(dto)


@router.post(
    "/{announcement_id}/consent",
    response_model=AnnouncementView,
    summary="Accepter ou refuser d'être nommé — réservé au **sujet lui-même**",
)
async def decide_consent(
    announcement_id: UUID,
    payload: ConsentRequest,
    actor: CurrentActor,
    command: DecideConsentDep,
) -> AnnouncementView:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        announcement_id=announcement_id,
        accept=payload.accept,
    )
    return AnnouncementView.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/announcements",
    response_model=AnnouncementFeedView,
    summary="Mon fil d'actualité : Dorea + mon église + mes groupes (paginé au curseur)",
)
async def my_feed(
    tenant_id: UUID,
    actor: CurrentActor,
    query: ListMyAnnouncementsDep,
    limit: int = 20,
    before: datetime | None = None,
) -> AnnouncementFeedView:
    dto = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, limit=limit, before=before
    )
    return AnnouncementFeedView.from_dto(dto)


@router.put(
    "/{announcement_id}/reaction",
    response_model=AnnouncementView,
    summary="Réagir (emoji de la palette du type) — une par personne, changeable",
)
async def react(
    announcement_id: UUID,
    payload: ReactRequest,
    actor: CurrentActor,
    command: SetReactionDep,
) -> AnnouncementView:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        announcement_id=announcement_id,
        emoji=payload.emoji,
    )
    return AnnouncementView.from_dto(dto)


@router.delete(
    "/{announcement_id}/reaction",
    response_model=AnnouncementView,
    summary="Retirer sa réaction — idempotent",
)
async def unreact(
    announcement_id: UUID,
    actor: CurrentActor,
    command: RemoveReactionDep,
) -> AnnouncementView:
    dto = await command.execute(
        actor_account_id=actor.account_id, announcement_id=announcement_id
    )
    return AnnouncementView.from_dto(dto)


@router.post(
    "/{announcement_id}/engage",
    response_model=AnnouncementView,
    summary="S'engager (je viens / je sers / je porte) — idempotent",
)
async def engage(
    announcement_id: UUID,
    actor: CurrentActor,
    command: EngageAnnouncementDep,
) -> AnnouncementView:
    dto = await command.execute(
        actor_account_id=actor.account_id, announcement_id=announcement_id
    )
    return AnnouncementView.from_dto(dto)


@router.delete(
    "/{announcement_id}/engage",
    response_model=AnnouncementView,
    summary="Se désengager (libère une place de mobilisation) — idempotent",
)
async def disengage(
    announcement_id: UUID,
    actor: CurrentActor,
    command: WithdrawEngagementDep,
) -> AnnouncementView:
    dto = await command.execute(
        actor_account_id=actor.account_id, announcement_id=announcement_id
    )
    return AnnouncementView.from_dto(dto)


@router.get(
    "/{announcement_id}/consolation",
    response_model=ConsolationView,
    summary="« N personnes vous portent » — réservé au **sujet** de l'annonce (ou au pasteur)",
)
async def consolation(
    announcement_id: UUID,
    actor: CurrentActor,
    query: GetConsolationDep,
) -> ConsolationView:
    dto = await query.execute(
        actor_account_id=actor.account_id, announcement_id=announcement_id
    )
    return ConsolationView.from_dto(dto)


@router.get(
    "/{announcement_id}/responders",
    response_model=ResponderListView,
    summary="Qui s'est engagé (les noms) — auteur ou responsable de la portée",
)
async def responders(
    announcement_id: UUID,
    actor: CurrentActor,
    query: ListRespondersDep,
) -> ResponderListView:
    dto = await query.execute(
        actor_account_id=actor.account_id, announcement_id=announcement_id
    )
    return ResponderListView.from_dto(dto)


@router.post(
    "/{announcement_id}/archive",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver (sortir du fil) — même autorité que publier dans la portée",
)
async def archive(
    announcement_id: UUID,
    actor: CurrentActor,
    command: ArchiveAnnouncementDep,
) -> None:
    await command.execute(actor_account_id=actor.account_id, announcement_id=announcement_id)
