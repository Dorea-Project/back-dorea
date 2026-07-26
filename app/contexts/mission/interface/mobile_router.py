"""Routes **mobile** de la Mission (M9) — le membre inviteur.

Générer *mon* lien (ou le lien de mon groupe), voir *mon* fruit missionnaire, couper un lien.
Authentifié par le JWT mobile (`CurrentActor`).
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.mission.interface.dependencies import (
    AccompanySeekerDep,
    CloseSeekerDep,
    CreateGroupLinkDep,
    CreateMyLinkDep,
    GenerateVerseCardDep,
    IntegrateSeekerDep,
    ListMySeekersDep,
    RevokeLinkDep,
)
from app.contexts.mission.interface.schemas import (
    CreateLinkRequest,
    GenerateCardRequest,
    IntegrateRequest,
    IntegrateResponse,
    MissionLinkResponse,
    MySeekersResponse,
    SeekerResponse,
    VerseCardResponse,
)

router = APIRouter()


@router.post(
    "/generate-card",
    response_model=VerseCardResponse,
    summary="Générer une carte à partir d'un verset flou : l'IA retrouve la référence, la Bible "
    "donne le texte exact, la carte est designée",
)
async def generate_card(
    payload: GenerateCardRequest,
    actor: CurrentActor,  # réservé aux membres (comme la création de lien)
    command: GenerateVerseCardDep,
) -> VerseCardResponse:
    dto = await command.execute(query=payload.query)
    return VerseCardResponse.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}/my-link",
    response_model=MissionLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer mon lien/QR personnel d'invitation (idempotent : un par membre)",
)
async def create_my_link(
    tenant_id: UUID,
    payload: CreateLinkRequest,
    actor: CurrentActor,
    command: CreateMyLinkDep,
) -> MissionLinkResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        message=payload.message,
        media_urls=payload.media_urls,
        place_label=payload.place_label,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return MissionLinkResponse.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}/groups/{group_id}/link",
    response_model=MissionLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer le lien d'évangélisation d'un groupe (campagne) — responsable du groupe",
)
async def create_group_link(
    tenant_id: UUID,
    group_id: UUID,
    payload: CreateLinkRequest,
    actor: CurrentActor,
    command: CreateGroupLinkDep,
) -> MissionLinkResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        message=payload.message,
        media_urls=payload.media_urls,
        place_label=payload.place_label,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return MissionLinkResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/my-seekers",
    response_model=MySeekersResponse,
    summary="Mon fruit missionnaire : les chercheurs que j'ai amenés + le signal des réactions",
)
async def my_seekers(
    tenant_id: UUID,
    actor: CurrentActor,
    query: ListMySeekersDep,
) -> MySeekersResponse:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return MySeekersResponse.from_dto(dto)


@router.post(
    "/links/{link_id}/revoke",
    response_model=MissionLinkResponse,
    summary="Couper un lien (l'auteur, ou un responsable du groupe)",
)
async def revoke_link(
    link_id: UUID,
    actor: CurrentActor,
    command: RevokeLinkDep,
) -> MissionLinkResponse:
    dto = await command.execute(actor_account_id=actor.account_id, link_id=link_id)
    return MissionLinkResponse.from_dto(dto)


@router.post(
    "/seekers/{seeker_id}/accompany",
    response_model=SeekerResponse,
    summary="Prendre le relais d'un chercheur (l'inviteur, ou un responsable du groupe)",
)
async def accompany_seeker(
    seeker_id: UUID,
    actor: CurrentActor,
    command: AccompanySeekerDep,
) -> SeekerResponse:
    dto = await command.execute(actor_account_id=actor.account_id, seeker_id=seeker_id)
    return SeekerResponse.from_dto(dto)


@router.post(
    "/seekers/{seeker_id}/close",
    response_model=SeekerResponse,
    summary="Clôturer le parcours d'un chercheur, sans jugement (l'inviteur / responsable groupe)",
)
async def close_seeker(
    seeker_id: UUID,
    actor: CurrentActor,
    command: CloseSeekerDep,
) -> SeekerResponse:
    dto = await command.execute(actor_account_id=actor.account_id, seeker_id=seeker_id)
    return SeekerResponse.from_dto(dto)


@router.post(
    "/seekers/{seeker_id}/integrate",
    response_model=IntegrateResponse,
    summary="Intégrer un chercheur : il devient membre (tunnel visiteur→membre) — autorité "
    "d'enrôlement (responsable du groupe, ou église-entière pour un chercheur personnel)",
)
async def integrate_seeker(
    seeker_id: UUID,
    payload: IntegrateRequest,
    actor: CurrentActor,
    command: IntegrateSeekerDep,
) -> IntegrateResponse:
    result = await command.execute(
        actor_account_id=actor.account_id,
        seeker_id=seeker_id,
        phone=payload.phone,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    return IntegrateResponse.from_result(result)
