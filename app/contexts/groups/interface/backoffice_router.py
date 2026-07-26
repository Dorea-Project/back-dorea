"""Routes **backoffice** des Groupes — montées sous `/api/backoffice`.

G-0 : création d'un groupe racine (Owner/Admin) ou d'un sous-groupe (responsable scopé).
L'acteur vient de la session backoffice ; le tenant reste en chemin.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser
from app.contexts.groups.interface.dependencies import (
    AddGroupMemberDep,
    AppointGroupLeadershipDep,
    CloseGroupDep,
    CreateGroupDep,
    GetCellReportDep,
    ListGroupMembersDep,
    ModifyGroupDep,
    MultiplyCellDep,
    PromoteGroupToChurchDep,
    RemoveGroupMemberDep,
    RevokeGroupLeadershipDep,
)
from app.contexts.groups.interface.schemas import (
    AddGroupMemberRequest,
    AppointLeadershipRequest,
    CellReportResponse,
    ChurchPlantResponse,
    CreateGroupRequest,
    GroupMemberResponse,
    GroupResponse,
    LeadershipResponse,
    ModifyGroupRequest,
    MultiplicationResponse,
    MultiplyCellRequest,
    PromoteToChurchRequest,
    RevokeLeadershipRequest,
)
from app.contexts.tenant.interface.dependencies import require_platform_token

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}/groups",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un groupe (racine par Owner/Admin, sous-groupe par responsable scopé)",
)
async def create_group(
    tenant_id: UUID,
    payload: CreateGroupRequest,
    actor: CurrentBackofficeUser,
    command: CreateGroupDep,
) -> GroupResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        name=payload.name,
        type=payload.type,
        parent_group_id=payload.parent_group_id,
    )
    return GroupResponse.from_dto(dto)


@router.patch(
    "/tenants/{tenant_id}/groups/{group_id}",
    response_model=GroupResponse,
    summary="Modifier un groupe (renommer, active↔dormant) — autorité du nœud",
)
async def modify_group(
    tenant_id: UUID,
    group_id: UUID,
    payload: ModifyGroupRequest,
    actor: CurrentBackofficeUser,
    command: ModifyGroupDep,
) -> GroupResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        name=payload.name,
        status=payload.status,
    )
    return GroupResponse.from_dto(dto)


@router.delete(
    "/tenants/{tenant_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Fermer un groupe (douce, cascade) — autorité du parent, bloqué si enfants actifs",
)
async def close_group(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentBackofficeUser,
    command: CloseGroupDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id
    )


@router.post(
    "/tenants/{tenant_id}/groups/{group_id}/members",
    response_model=GroupMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rattacher un membre à un groupe (responsable scopé / Admin / Owner)",
)
async def add_group_member(
    tenant_id: UUID,
    group_id: UUID,
    payload: AddGroupMemberRequest,
    actor: CurrentBackofficeUser,
    command: AddGroupMemberDep,
) -> GroupMemberResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        account_id=payload.account_id,
    )
    return GroupMemberResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/members",
    response_model=list[GroupMemberResponse],
    summary="Roster : membres actifs d'un groupe",
)
async def list_group_members(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentBackofficeUser,
    query: ListGroupMembersDep,
) -> list[GroupMemberResponse]:
    dtos = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id
    )
    return [GroupMemberResponse.from_dto(d) for d in dtos]


@router.delete(
    "/tenants/{tenant_id}/groups/{group_id}/members/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un membre d'un groupe (statut → left)",
)
async def remove_group_member(
    tenant_id: UUID,
    group_id: UUID,
    account_id: UUID,
    actor: CurrentBackofficeUser,
    command: RemoveGroupMemberDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        account_id=account_id,
    )


@router.post(
    "/tenants/{tenant_id}/groups/{group_id}/leaders",
    response_model=LeadershipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Nommer un responsable (cap 6) ou un responsable-en-formation sur un groupe",
)
async def appoint_group_leadership(
    tenant_id: UUID,
    group_id: UUID,
    payload: AppointLeadershipRequest,
    actor: CurrentBackofficeUser,
    command: AppointGroupLeadershipDep,
) -> LeadershipResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        account_id=payload.account_id,
        grade=payload.grade,
    )
    return LeadershipResponse.from_dto(dto)


@router.delete(
    "/tenants/{tenant_id}/groups/{group_id}/leaders",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Révoquer un grade de leadership (responsable → parent ; formation → nœud)",
)
async def revoke_group_leadership(
    tenant_id: UUID,
    group_id: UUID,
    payload: RevokeLeadershipRequest,
    actor: CurrentBackofficeUser,
    command: RevokeGroupLeadershipDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        account_id=payload.account_id,
        grade=payload.grade,
    )


@router.post(
    "/tenants/{tenant_id}/groups/{group_id}/multiply",
    response_model=MultiplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Multiplier une cellule : enfante une fille, déplace des membres, promeut un leader",
)
async def multiply_cell(
    tenant_id: UUID,
    group_id: UUID,
    payload: MultiplyCellRequest,
    actor: CurrentBackofficeUser,
    command: MultiplyCellDep,
) -> MultiplicationResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        mother_group_id=group_id,
        daughter_name=payload.daughter_name,
        new_leader_account_id=payload.new_leader_account_id,
        member_account_ids=payload.member_account_ids,
    )
    return MultiplicationResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/report",
    response_model=CellReportResponse,
    summary="Santé & lignée d'une cellule (effectif, suggestion de multiplication, générations)",
)
async def get_cell_report(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentBackofficeUser,
    query: GetCellReportDep,
) -> CellReportResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id
    )
    return CellReportResponse.from_dto(dto)


@router.post(
    "/groups/{group_id}/promote-to-church",
    response_model=ChurchPlantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Émanciper un groupe en église autonome (acte Plateforme Dorea, church planting)",
    dependencies=[Depends(require_platform_token)],
)
async def promote_group_to_church(
    group_id: UUID,
    payload: PromoteToChurchRequest,
    command: PromoteGroupToChurchDep,
) -> ChurchPlantResponse:
    dto = await command.execute(
        group_id=group_id,
        church_name=payload.church_name,
        owner_account_id=payload.owner_account_id,
    )
    return ChurchPlantResponse.from_dto(dto)
