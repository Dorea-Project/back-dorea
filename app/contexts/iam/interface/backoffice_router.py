"""Routes **backoffice** du contexte IAM (écritures) — montées sous `/api/backoffice/iam`.

Protégées par la **session backoffice** (`CurrentBackofficeUser`) : l'acteur est
l'Owner/Admin connecté. L'autorisation fine (RBAC borné par la propriété, politique
d'autorité par rôle) est vérifiée dans les use cases via `AuthorizationService`.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser
from app.contexts.iam.application.dtos import InvitedMemberInput
from app.contexts.iam.interface.dependencies import (
    AcceptTransferDep,
    BulkEnrollDep,
    CancelTransferDep,
    CloseMembershipDep,
    CreateChurchInvitationDep,
    DeclineTransferDep,
    EnrollInvitedMemberDep,
    EnrollMemberDep,
    ListTransfersDep,
    RequestTransferDep,
    RevokeChurchInvitationDep,
    RevokeRoleDep,
    TransitionStatusDep,
)
from app.contexts.iam.interface.schemas import (
    BulkEnrollRequest,
    BulkEnrollResponse,
    ChurchInvitationResponse,
    CloseMembershipRequest,
    CloseMembershipResponse,
    EnrollInvitedMemberRequest,
    EnrollInvitedMemberResponse,
    EnrollMemberRequest,
    EnrollMemberResponse,
    RequestTransferRequest,
    RevokeRoleRequest,
    RevokeRoleResponse,
    TransferListResponse,
    TransferResponse,
    TransitionRequest,
    TransitionResponse,
)

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}/members",
    response_model=EnrollMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enrôler un membre porteur d'un rôle (Owner→staff, Admin→équipe)",
)
async def enroll_member(
    tenant_id: UUID,
    payload: EnrollMemberRequest,
    actor: CurrentBackofficeUser,
    command: EnrollMemberDep,
) -> EnrollMemberResponse:
    result = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        role=payload.role,
        phone_number=payload.phone_number,
        group_id=payload.group_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    return EnrollMemberResponse.from_result(result)


@router.post(
    "/tenants/{tenant_id}/invited-members",
    response_model=EnrollInvitedMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enrôler un fidèle ordinaire (statut invited, sans rôle ni credential)",
)
async def enroll_invited_member(
    tenant_id: UUID,
    payload: EnrollInvitedMemberRequest,
    actor: CurrentBackofficeUser,
    command: EnrollInvitedMemberDep,
) -> EnrollInvitedMemberResponse:
    result = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        phone_number=payload.phone_number,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    return EnrollInvitedMemberResponse.from_result(result)


@router.post(
    "/tenants/{tenant_id}/members/import",
    response_model=BulkEnrollResponse,
    summary="Import en masse de fidèles (onboarding M3) — best-effort par ligne",
)
async def import_members(
    tenant_id: UUID,
    payload: BulkEnrollRequest,
    actor: CurrentBackofficeUser,
    command: BulkEnrollDep,
) -> BulkEnrollResponse:
    result = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        rows=[
            InvitedMemberInput(
                phone_number=m.phone_number, first_name=m.first_name, last_name=m.last_name
            )
            for m in payload.members
        ],
    )
    return BulkEnrollResponse.from_result(result)


@router.post(
    "/tenants/{tenant_id}/members/{account_id}/transitions",
    response_model=TransitionResponse,
    summary="Faire évoluer le statut d'un membre (Admin/Intégration)",
)
async def transition_member(
    tenant_id: UUID,
    account_id: UUID,
    payload: TransitionRequest,
    actor: CurrentBackofficeUser,
    command: TransitionStatusDep,
) -> TransitionResponse:
    result = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        target_account_id=account_id,
        event=payload.event,
    )
    return TransitionResponse.from_result(result)


@router.post(
    "/tenants/{tenant_id}/members/{account_id}/revoke-role",
    response_model=RevokeRoleResponse,
    summary="Révoquer un rôle d'un membre (autorité symétrique de l'attribution)",
)
async def revoke_role(
    tenant_id: UUID,
    account_id: UUID,
    payload: RevokeRoleRequest,
    actor: CurrentBackofficeUser,
    command: RevokeRoleDep,
) -> RevokeRoleResponse:
    result = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        target_account_id=account_id,
        role=payload.role,
        group_id=payload.group_id,
    )
    return RevokeRoleResponse.from_result(result)


@router.post(
    "/tenants/{tenant_id}/members/{account_id}/close",
    response_model=CloseMembershipResponse,
    summary="Clôturer une appartenance (Admin) — cascade atomique des rôles",
)
async def close_membership(
    tenant_id: UUID,
    account_id: UUID,
    payload: CloseMembershipRequest,
    actor: CurrentBackofficeUser,
    command: CloseMembershipDep,
) -> CloseMembershipResponse:
    result = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        target_account_id=account_id,
        closure_reason=payload.closure_reason,
    )
    return CloseMembershipResponse.from_result(result)


# --- Rejoindre une église : liens d'invitation (M-5) ---


@router.post(
    "/tenants/{tenant_id}/church-invitations",
    response_model=ChurchInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer un lien d'invitation église (accueil/Admin) — réutilisable, expirable",
)
async def create_church_invitation(
    tenant_id: UUID,
    actor: CurrentBackofficeUser,
    command: CreateChurchInvitationDep,
) -> ChurchInvitationResponse:
    dto = await command.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return ChurchInvitationResponse.from_dto(dto)


@router.post(
    "/church-invitations/{invitation_id}/revoke",
    response_model=ChurchInvitationResponse,
    summary="Révoquer un lien d'invitation église (couper l'accès)",
)
async def revoke_church_invitation(
    invitation_id: UUID,
    actor: CurrentBackofficeUser,
    command: RevokeChurchInvitationDep,
) -> ChurchInvitationResponse:
    dto = await command.execute(actor_account_id=actor.account_id, invitation_id=invitation_id)
    return ChurchInvitationResponse.from_dto(dto)


# --- Transfert de membre entre églises (poignée de main) ---


@router.post(
    "/tenants/{tenant_id}/transfer-requests",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Demander à recevoir un membre d'une autre église (la destination initie)",
)
async def request_transfer(
    tenant_id: UUID,
    payload: RequestTransferRequest,
    actor: CurrentBackofficeUser,
    command: RequestTransferDep,
) -> TransferResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        account_id=payload.account_id,
        from_tenant_id=payload.from_tenant_id,
        to_tenant_id=tenant_id,  # l'église connectée est la destination
        to_group_id=payload.to_group_id,
    )
    return TransferResponse.from_dto(dto)


@router.post(
    "/transfers/{transfer_id}/accept",
    response_model=TransferResponse,
    summary="Accepter et libérer le membre (la source consent) — exécute le transfert",
)
async def accept_transfer(
    transfer_id: UUID,
    actor: CurrentBackofficeUser,
    command: AcceptTransferDep,
) -> TransferResponse:
    dto = await command.execute(actor_account_id=actor.account_id, transfer_id=transfer_id)
    return TransferResponse.from_dto(dto)


@router.post(
    "/transfers/{transfer_id}/decline",
    response_model=TransferResponse,
    summary="Refuser la demande de transfert (la source garde le membre)",
)
async def decline_transfer(
    transfer_id: UUID,
    actor: CurrentBackofficeUser,
    command: DeclineTransferDep,
) -> TransferResponse:
    dto = await command.execute(actor_account_id=actor.account_id, transfer_id=transfer_id)
    return TransferResponse.from_dto(dto)


@router.post(
    "/transfers/{transfer_id}/cancel",
    response_model=TransferResponse,
    summary="Annuler sa propre demande de transfert (la destination se rétracte)",
)
async def cancel_transfer(
    transfer_id: UUID,
    actor: CurrentBackofficeUser,
    command: CancelTransferDep,
) -> TransferResponse:
    dto = await command.execute(actor_account_id=actor.account_id, transfer_id=transfer_id)
    return TransferResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/transfers",
    response_model=TransferListResponse,
    summary="Transferts de l'église : entrants (à traiter) et sortants (émis)",
)
async def list_transfers(
    tenant_id: UUID,
    actor: CurrentBackofficeUser,
    query: ListTransfersDep,
) -> TransferListResponse:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return TransferListResponse.from_dto(dto)
