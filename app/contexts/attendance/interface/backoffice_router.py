"""Routes **backoffice** de l'intelligence pastorale (B7) — le cockpit du pasteur (PWA).

Le pasteur / l'Admin *regarde* le 360° de l'église pour **décider** : le tableau de bord
(grille des groupes + totaux) et la liste de soin consolidée. Authentifié par le **cookie de
session** backoffice ; autorité **église-entière** (déjà exigée par les requêtes M7).
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.attendance.interface.dependencies import (
    GetCareListDep,
    GetChurchDashboardDep,
    GetGroupTrendDep,
    GetMemberTrajectoryDep,
    GetMultiplicationTreeDep,
    SuspendChurchDep,
)
from app.contexts.attendance.interface.schemas import (
    CareListResponse,
    ChurchDashboardResponse,
    GroupTrendResponse,
    MemberTrajectoryResponse,
    MultiplicationTreeResponse,
    SuspendChurchRequest,
    SuspensionResponse,
)
from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser

router = APIRouter()


@router.get(
    "/tenants/{tenant_id}/dashboard",
    response_model=ChurchDashboardResponse,
    summary="Tableau de bord pastoral : la grille des groupes + totaux (décider en un coup d'œil)",
)
async def church_dashboard(
    tenant_id: UUID,
    actor: CurrentBackofficeUser,
    query: GetChurchDashboardDep,
) -> ChurchDashboardResponse:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return ChurchDashboardResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/care-list",
    response_model=CareListResponse,
    summary="Liste « à interpeller » de toute l'église (le pasteur voit qui visiter)",
)
async def care_list(
    tenant_id: UUID,
    actor: CurrentBackofficeUser,
    query: GetCareListDep,
) -> CareListResponse:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return CareListResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/multiplication-tree",
    response_model=MultiplicationTreeResponse,
    summary="Arbre de multiplication : la forêt de reproduction des cellules + fertilité",
)
async def multiplication_tree(
    tenant_id: UUID,
    actor: CurrentBackofficeUser,
    query: GetMultiplicationTreeDep,
) -> MultiplicationTreeResponse:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return MultiplicationTreeResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/trend",
    response_model=GroupTrendResponse,
    summary="Tendance d'un groupe dans le temps (drill-down depuis la grille du dashboard)",
)
async def group_trend(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentBackofficeUser,
    query: GetGroupTrendDep,
    weeks: int = 8,
) -> GroupTrendResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id, weeks=weeks
    )
    return GroupTrendResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/members/{account_id}/trajectory",
    response_model=MemberTrajectoryResponse,
    summary="Trajectoire d'un membre : l'histoire derrière une entrée de la care-list",
)
async def member_trajectory(
    tenant_id: UUID,
    group_id: UUID,
    account_id: UUID,
    actor: CurrentBackofficeUser,
    query: GetMemberTrajectoryDep,
) -> MemberTrajectoryResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        account_id=account_id,
    )
    return MemberTrajectoryResponse.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}/suspensions",
    response_model=SuspensionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Suspendre l'église sur une période (Noël, deuil national) — acquitte tous les groupes",
)
async def suspend_church(
    tenant_id: UUID,
    payload: SuspendChurchRequest,
    actor: CurrentBackofficeUser,
    command: SuspendChurchDep,
) -> SuspensionResponse:
    """Une décision d'église, prise une fois, plutôt que N acquittements par N responsables.

    La cascade est calculée **à la lecture** : aucune ligne n'est générée par groupe, donc
    lever la suspension ne laisse aucun résidu à nettoyer."""
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        reason=payload.reason,
        from_date=payload.from_date,
        to_date=payload.to_date,
    )
    return SuspensionResponse.from_dto(dto)
