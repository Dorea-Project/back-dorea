"""Routes backoffice du contexte Tenant (M0) — montées sous `/api/backoffice`.

Le provisionnement (`ProvisionTenant`) est un **acte Plateforme**, protégé par un
jeton de service (garde `require_platform_token`), pas par une session Owner.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser
from app.contexts.tenant.application.dtos import ProvisionTenantRequest, UpdateTenantInput
from app.contexts.tenant.interface.dependencies import (
    GetTenantDep,
    GetTenantFamilyDep,
    ListMyTenantsDep,
    ListTenantsDep,
    ProvisionTenantDep,
    SetTenantStatusDep,
    TransferOwnershipDep,
    UpdateTenantDep,
    require_platform_token,
)
from app.contexts.tenant.interface.schemas import (
    ProvisionAnnexeSchema,
    ProvisionTenantRequestSchema,
    ProvisionTenantResponse,
    TenantDetailResponse,
    TenantFamilyResponse,
    UpdateTenantSchema,
)


class TransferOwnershipSchema(BaseModel):
    new_owner_account_id: UUID


class TransferOwnershipResponse(BaseModel):
    tenant_id: UUID
    new_owner_account_id: UUID

router = APIRouter()


@router.post(
    "/tenants",
    response_model=ProvisionTenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provisionner une église (Tenant + Owner) — acte Plateforme",
    dependencies=[Depends(require_platform_token)],
)
async def provision_tenant(
    payload: ProvisionTenantRequestSchema,
    command: ProvisionTenantDep,
) -> ProvisionTenantResponse:
    result = await command.execute(
        ProvisionTenantRequest(
            tenant_name=payload.tenant_name,
            owner_phone=payload.owner_phone,
            owner_email=payload.owner_email,
            owner_password=payload.owner_password,
            owner_first_name=payload.owner_first_name,
            owner_last_name=payload.owner_last_name,
            parent_id=payload.parent_id,
            denomination=payload.denomination,
            contact_email=payload.contact_email,
            estimated_member_count=payload.estimated_member_count,
            country=payload.country,
            city=payload.city,
            address=payload.address,
            latitude=payload.latitude,
            longitude=payload.longitude,
            logo_url=payload.logo_url,
            short_description=payload.short_description,
            contact_name=payload.contact_name,
            contact_phone=payload.contact_phone,
            timezone=payload.timezone,
            language=payload.language,
            currency=payload.currency,
            operates_annexes=payload.operates_annexes,
        )
    )
    return ProvisionTenantResponse.from_result(result)


@router.post(
    "/tenants/{parent_id}/annexes",
    response_model=ProvisionTenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter une annexe (église-fille avec son propre Owner) — acte Plateforme",
    dependencies=[Depends(require_platform_token)],
)
async def provision_annexe(
    parent_id: UUID,
    payload: ProvisionAnnexeSchema,
    command: ProvisionTenantDep,
) -> ProvisionTenantResponse:
    """Une annexe est une **église-fille** : son propre Owner, sa propre gouvernance,
    rattachée à la mère par `parent_id` (M0 §4.1). La mère est validée par la commande —
    elle doit exister, être active et être elle-même un principal (filiation plate)."""
    result = await command.execute(
        ProvisionTenantRequest(
            parent_id=parent_id,  # ← du chemin, jamais du corps
            operates_annexes=False,  # filiation plate : une annexe n'a pas d'annexe
            **payload.model_dump(),
        )
    )
    return ProvisionTenantResponse.from_result(result)


# --- Owner : gère SON église (session backoffice) ---


@router.get(
    "/me/tenants",
    response_model=list[TenantDetailResponse],
    summary="Mes églises — celles dont je suis l'Owner actif (point d'entrée après login)",
)
async def list_my_tenants(
    actor: CurrentBackofficeUser, query: ListMyTenantsDep
) -> list[TenantDetailResponse]:
    dtos = await query.execute(actor_account_id=actor.account_id)
    return [TenantDetailResponse.from_dto(d) for d in dtos]


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantDetailResponse,
    summary="Lire le profil de mon église (Owner)",
)
async def get_tenant(
    tenant_id: UUID, actor: CurrentBackofficeUser, query: GetTenantDep
) -> TenantDetailResponse:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return TenantDetailResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/family",
    response_model=TenantFamilyResponse,
    summary="Ma famille — mon église et ses annexes (supervision en lecture seule)",
)
async def get_tenant_family(
    tenant_id: UUID, actor: CurrentBackofficeUser, query: GetTenantFamilyDep
) -> TenantFamilyResponse:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return TenantFamilyResponse.from_dto(dto)


@router.patch(
    "/tenants/{tenant_id}",
    response_model=TenantDetailResponse,
    summary="Éditer le profil de mon église (Owner)",
)
async def update_tenant(
    tenant_id: UUID,
    payload: UpdateTenantSchema,
    actor: CurrentBackofficeUser,
    command: UpdateTenantDep,
) -> TenantDetailResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        updates=UpdateTenantInput(**payload.model_dump()),
    )
    return TenantDetailResponse.from_dto(dto)


# --- Dorea : annuaire + suspension (jeton de service) ---


@router.get(
    "/tenants",
    response_model=list[TenantDetailResponse],
    summary="Annuaire des églises (Dorea)",
    dependencies=[Depends(require_platform_token)],
)
async def list_tenants(
    query: ListTenantsDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TenantDetailResponse]:
    dtos = await query.execute(limit=limit, offset=offset)
    return [TenantDetailResponse.from_dto(d) for d in dtos]


@router.post(
    "/tenants/{tenant_id}/suspend",
    response_model=TenantDetailResponse,
    summary="Suspendre une église (Dorea)",
    dependencies=[Depends(require_platform_token)],
)
async def suspend_tenant(
    tenant_id: UUID, command: SetTenantStatusDep
) -> TenantDetailResponse:
    return TenantDetailResponse.from_dto(await command.execute(tenant_id=tenant_id, suspend=True))


@router.post(
    "/tenants/{tenant_id}/reactivate",
    response_model=TenantDetailResponse,
    summary="Réactiver une église (Dorea)",
    dependencies=[Depends(require_platform_token)],
)
async def reactivate_tenant(
    tenant_id: UUID, command: SetTenantStatusDep
) -> TenantDetailResponse:
    return TenantDetailResponse.from_dto(await command.execute(tenant_id=tenant_id, suspend=False))


@router.post(
    "/tenants/{tenant_id}/transfer-ownership",
    response_model=TransferOwnershipResponse,
    summary="Transférer le siège Owner (succession) — acte Plateforme",
    dependencies=[Depends(require_platform_token)],
)
async def transfer_ownership(
    tenant_id: UUID, payload: TransferOwnershipSchema, command: TransferOwnershipDep
) -> TransferOwnershipResponse:
    new_owner = await command.execute(
        tenant_id=tenant_id, new_owner_account_id=payload.new_owner_account_id
    )
    return TransferOwnershipResponse(tenant_id=tenant_id, new_owner_account_id=new_owner)
