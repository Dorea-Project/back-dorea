"""Routes HTTP du contexte IAM (surface mobile — lecture).

Le fidèle lit **sa propre** appartenance : l'`account_id` vient de l'acteur
authentifié (`CurrentActor`), jamais de l'URL. Le tenant reste en chemin (un
compte peut appartenir à plusieurs églises).
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.iam.interface.dependencies import (
    GetMembershipStatusDep,
    GetMyMembershipsDep,
    JoinChurchByCodeDep,
)
from app.contexts.iam.interface.schemas import (
    JoinChurchRequest,
    JoinChurchResponse,
    MembershipStatusResponse,
)

router = APIRouter()


@router.post(
    "/join-church",
    response_model=JoinChurchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rejoindre une église par code d'invitation (self-service ; le code autorise)",
)
async def join_church(
    payload: JoinChurchRequest,
    actor: CurrentActor,
    command: JoinChurchByCodeDep,
) -> JoinChurchResponse:
    result = await command.execute(actor_account_id=actor.account_id, code=payload.code)
    return JoinChurchResponse.from_result(result)


@router.get(
    "/me/memberships",
    response_model=list[MembershipStatusResponse],
    summary="Toutes mes appartenances actives (découverte post-login)",
)
async def read_my_memberships(
    actor: CurrentActor,
    query: GetMyMembershipsDep,
) -> list[MembershipStatusResponse]:
    dtos = await query.execute(account_id=actor.account_id)
    return [MembershipStatusResponse.from_dto(dto) for dto in dtos]


@router.get(
    "/me/tenants/{tenant_id}/membership",
    response_model=MembershipStatusResponse,
    summary="Mon statut d'appartenance et mes rôles actifs dans un tenant",
)
async def read_my_membership_status(
    tenant_id: UUID,
    actor: CurrentActor,
    query: GetMembershipStatusDep,
) -> MembershipStatusResponse:
    dto = await query.execute(account_id=actor.account_id, tenant_id=tenant_id)
    return MembershipStatusResponse.from_dto(dto)
