"""Injection backoffice du contexte Tenant — garde Plateforme + commande."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header

from app.api.deps import DbSession, SettingsDep
from app.contexts.auth.infrastructure.hashing import HASH_ALGO_VERSION, Argon2PasswordHasher
from app.contexts.iam.infrastructure.persistence.repositories import (
    SqlAlchemyMembershipRepository,
)
from app.contexts.tenant.application.commands.provision_tenant import ProvisionTenant
from app.contexts.tenant.application.commands.transfer_ownership import TransferOwnership
from app.contexts.tenant.application.tenant_management import (
    GetTenant,
    ListTenants,
    SetTenantStatus,
    UpdateTenant,
)
from app.contexts.tenant.domain.errors import PlatformAuthRequiredError
from app.contexts.tenant.infrastructure.persistence.ownership_repo import SqlOwnershipRepository
from app.contexts.tenant.infrastructure.persistence.store import SqlProvisioningStore
from app.contexts.tenant.infrastructure.persistence.tenant_repo import SqlTenantRepository

_hasher = Argon2PasswordHasher()  # sans état → instance unique


async def require_platform_token(
    settings: SettingsDep,
    x_service_token: Annotated[str | None, Header()] = None,
) -> None:
    """Garde des actes Plateforme : jeton de service statique (en attendant M2/S3).

    Comparaison **à temps constant** (`secrets.compare_digest`) — pas de fuite temporelle."""
    if x_service_token is None or not secrets.compare_digest(
        x_service_token, settings.backoffice_service_token
    ):
        raise PlatformAuthRequiredError("Jeton de service Plateforme requis ou invalide.")


def get_provision_tenant_command(session: DbSession, settings: SettingsDep) -> ProvisionTenant:
    return ProvisionTenant(
        SqlProvisioningStore(session),
        SqlTenantRepository(session),
        platform_account_id=settings.platform_account_id,
        clock=lambda: datetime.now(UTC),
        hasher=_hasher,
        hash_algo_version=HASH_ALGO_VERSION,
    )


ProvisionTenantDep = Annotated[ProvisionTenant, Depends(get_provision_tenant_command)]


def get_get_tenant_query(session: DbSession) -> GetTenant:
    return GetTenant(SqlTenantRepository(session), SqlOwnershipRepository(session))


def get_update_tenant_command(session: DbSession) -> UpdateTenant:
    return UpdateTenant(SqlTenantRepository(session), SqlOwnershipRepository(session))


def get_list_tenants_query(session: DbSession) -> ListTenants:
    return ListTenants(SqlTenantRepository(session))


def get_set_tenant_status_command(session: DbSession) -> SetTenantStatus:
    return SetTenantStatus(SqlTenantRepository(session))


def get_transfer_ownership_command(session: DbSession) -> TransferOwnership:
    return TransferOwnership(
        SqlOwnershipRepository(session),
        SqlAlchemyMembershipRepository(session),
        clock=lambda: datetime.now(UTC),
    )


GetTenantDep = Annotated[GetTenant, Depends(get_get_tenant_query)]
UpdateTenantDep = Annotated[UpdateTenant, Depends(get_update_tenant_command)]
ListTenantsDep = Annotated[ListTenants, Depends(get_list_tenants_query)]
SetTenantStatusDep = Annotated[SetTenantStatus, Depends(get_set_tenant_status_command)]
TransferOwnershipDep = Annotated[TransferOwnership, Depends(get_transfer_ownership_command)]
