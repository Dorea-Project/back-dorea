"""Routes **mobile** des Groupes (Flutter) — self-service membre (M4, G-1b).

Le responsable génère/révoque un lien depuis son téléphone ; le membre rejoint par code
ou quitte un groupe. Authentifié par le JWT mobile (`CurrentActor`).
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.groups.interface.dependencies import (
    CreateGroupInvitationDep,
    JoinGroupByCodeDep,
    LeaveGroupDep,
    RevokeGroupInvitationDep,
)
from app.contexts.groups.interface.mobile_schemas import (
    InvitationResponse,
    JoinByCodeRequest,
    JoinResultResponse,
)

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}/groups/{group_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer un lien d'invitation à un groupe (responsable)",
)
async def create_invitation(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentActor,
    command: CreateGroupInvitationDep,
) -> InvitationResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id
    )
    return InvitationResponse.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}/invitations/{invitation_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Révoquer un lien d'invitation (responsable)",
)
async def revoke_invitation(
    tenant_id: UUID,
    invitation_id: UUID,
    actor: CurrentActor,
    command: RevokeGroupInvitationDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, invitation_id=invitation_id
    )


@router.post(
    "/join",
    response_model=JoinResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rejoindre un groupe par code d'invitation (onboarde l'église si besoin)",
)
async def join_by_code(
    payload: JoinByCodeRequest,
    actor: CurrentActor,
    command: JoinGroupByCodeDep,
) -> JoinResultResponse:
    dto = await command.execute(actor_account_id=actor.account_id, code=payload.code)
    return JoinResultResponse.from_dto(dto)


@router.post(
    "/{group_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitter un groupe (membre lui-même)",
)
async def leave_group(
    group_id: UUID,
    actor: CurrentActor,
    command: LeaveGroupDep,
) -> None:
    await command.execute(actor_account_id=actor.account_id, group_id=group_id)
