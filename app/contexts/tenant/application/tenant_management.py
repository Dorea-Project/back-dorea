"""Gestion du Tenant (P4) — lecture/liste/édition (Owner) + suspension (Dorea).

- **Owner** : lire et éditer **son** église (autorisé si `Ownership` active).
- **Dorea** : lister l'annuaire et suspendre/réactiver (garde jeton de service à l'endpoint).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.tenant.application.dtos import (
    TenantDetailDTO,
    TenantFamilyDTO,
    UpdateTenantInput,
)
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.errors import TenantForbiddenError, TenantNotFoundError
from app.contexts.tenant.domain.repositories import OwnershipRepository, TenantRepository
from app.contexts.tenant.domain.value_objects import Location


def to_detail(tenant: Tenant) -> TenantDetailDTO:
    loc = tenant.location
    return TenantDetailDTO(
        tenant_id=tenant.id,
        name=tenant.name,
        status=tenant.status.value,
        denomination=tenant.denomination,
        contact_email=tenant.contact_email,
        estimated_member_count=tenant.estimated_member_count,
        country=loc.country,
        city=loc.city,
        address=loc.address,
        latitude=loc.latitude,
        longitude=loc.longitude,
        is_independent=tenant.is_independent,
        slug=tenant.slug,
        logo_url=tenant.logo_url,
        short_description=tenant.short_description,
        contact_name=tenant.contact_name,
        contact_phone=tenant.contact_phone,
        timezone=tenant.timezone,
        language=tenant.language,
        currency=tenant.currency,
        operates_annexes=tenant.operates_annexes,
    )


async def _load_owned(
    tenants: TenantRepository,
    ownership: OwnershipRepository,
    actor_account_id: UUID,
    tenant_id: UUID,
) -> Tenant:
    if not await ownership.is_active_owner(actor_account_id, tenant_id):
        raise TenantForbiddenError("Réservé à l'Owner de ce tenant.")
    tenant = await tenants.get_by_id(tenant_id)
    if tenant is None:
        raise TenantNotFoundError("Église introuvable.")
    return tenant


class GetTenant:
    def __init__(self, tenants: TenantRepository, ownership: OwnershipRepository) -> None:
        self._tenants = tenants
        self._ownership = ownership

    async def execute(self, *, actor_account_id: UUID, tenant_id: UUID) -> TenantDetailDTO:
        return to_detail(
            await _load_owned(self._tenants, self._ownership, actor_account_id, tenant_id)
        )


class UpdateTenant:
    def __init__(self, tenants: TenantRepository, ownership: OwnershipRepository) -> None:
        self._tenants = tenants
        self._ownership = ownership

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, updates: UpdateTenantInput
    ) -> TenantDetailDTO:
        tenant = await _load_owned(self._tenants, self._ownership, actor_account_id, tenant_id)
        tenant.update_profile(
            denomination=updates.denomination,
            contact_email=updates.contact_email,
            estimated_member_count=updates.estimated_member_count,
            location=Location(
                country=updates.country,
                city=updates.city,
                address=updates.address,
                latitude=updates.latitude,
                longitude=updates.longitude,
            ),
            logo_url=updates.logo_url,
            short_description=updates.short_description,
            contact_name=updates.contact_name,
            contact_phone=updates.contact_phone,
            timezone=updates.timezone,
            language=updates.language,
            currency=updates.currency,
        )
        await self._tenants.save(tenant)
        return to_detail(tenant)


class GetTenantFamily:
    """« Ma famille » — le principal et ses annexes (M0 §4.2).

    **La brique de consolidation du Church OS.** L'isolation, elle, est native : la tablette
    d'une annexe est une session scopée à SON tenant. Ici on fait l'inverse — le principal
    *voit* l'ensemble. En **lecture seule** : il ne gouverne pas ses annexes (subsidiarité),
    chacune se gouverne elle-même.

    Sert aussi d'assiette d'abonnement (taille-famille + nombre d'annexes) — même calcul,
    un seul endroit."""

    def __init__(self, tenants: TenantRepository, ownership: OwnershipRepository) -> None:
        self._tenants = tenants
        self._ownership = ownership

    async def execute(self, *, actor_account_id: UUID, tenant_id: UUID) -> TenantFamilyDTO:
        principal = await _load_owned(self._tenants, self._ownership, actor_account_id, tenant_id)
        # Filiation plate (V1) : une annexe n'a pas d'annexe → pas de récursion.
        children = [] if not principal.is_independent else await self._tenants.list_children(
            principal.id
        )
        declared = [t.estimated_member_count or 0 for t in (principal, *children)]
        return TenantFamilyDTO(
            principal=to_detail(principal),
            annexes=[to_detail(c) for c in children],
            family_member_count=sum(declared),
            active_annexe_count=sum(1 for c in children if c.is_active),
        )


class ListMyTenants:
    """« Mes églises » — celles dont l'acteur est l'Owner **actif** (session backoffice).

    Point d'entrée du front après login : `/auth/me` ne donne que l'`account_id`,
    c'est ici qu'on découvre le(s) `tenant_id` à charger."""

    def __init__(self, tenants: TenantRepository, ownership: OwnershipRepository) -> None:
        self._tenants = tenants
        self._ownership = ownership

    async def execute(self, *, actor_account_id: UUID) -> list[TenantDetailDTO]:
        tenant_ids = await self._ownership.list_active_tenant_ids(actor_account_id)
        out: list[TenantDetailDTO] = []
        for tenant_id in tenant_ids:
            tenant = await self._tenants.get_by_id(tenant_id)
            if tenant is not None:  # propriété orpheline (anomalie) → ignorée
                out.append(to_detail(tenant))
        return out


class ListTenants:
    """Annuaire Dorea (garde jeton de service à l'endpoint)."""

    def __init__(self, tenants: TenantRepository) -> None:
        self._tenants = tenants

    async def execute(self, *, limit: int, offset: int) -> list[TenantDetailDTO]:
        return [to_detail(t) for t in await self._tenants.list_all(limit=limit, offset=offset)]


class SetTenantStatus:
    """Suspendre / réactiver une église (Dorea)."""

    def __init__(self, tenants: TenantRepository) -> None:
        self._tenants = tenants

    async def execute(self, *, tenant_id: UUID, suspend: bool) -> TenantDetailDTO:
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError("Église introuvable.")
        tenant.suspend() if suspend else tenant.reactivate()
        await self._tenants.save(tenant)
        return to_detail(tenant)
