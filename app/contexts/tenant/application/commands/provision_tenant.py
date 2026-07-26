"""Use case `ProvisionTenant` — la **genèse** d'une église (M0 §3.1, §6).

Provisionnement **direct** par la Plateforme (jeton de service). Crée le Tenant, le
compte Owner (email + mot de passe), sa Membership `confirmed_member` (sans rôle) et
la **propriété** (`Ownership`), en une transaction atomique. Le même noyau
(`build_genesis`) sert à l'approbation d'un onboarding.
"""

from __future__ import annotations

from app.contexts.auth.application.ports import PasswordHasher
from app.contexts.auth.domain.password import Password
from app.contexts.tenant.application.dtos import ProvisionTenantRequest, ProvisionTenantResult
from app.contexts.tenant.application.genesis import build_genesis
from app.contexts.tenant.application.ports import Clock, ProvisioningStore
from app.contexts.tenant.domain.drafts import OwnerDraft, TenantDraft
from app.contexts.tenant.domain.errors import InvalidParentTenantError
from app.contexts.tenant.domain.repositories import TenantRepository


class ProvisionTenant:
    def __init__(
        self,
        store: ProvisioningStore,
        tenants: TenantRepository,
        *,
        platform_account_id,
        clock: Clock,
        hasher: PasswordHasher,
        hash_algo_version: int,
    ) -> None:
        self._store = store
        self._tenants = tenants
        self._platform_account_id = platform_account_id
        self._clock = clock
        self._hasher = hasher
        self._hash_algo_version = hash_algo_version

    async def execute(self, request: ProvisionTenantRequest) -> ProvisionTenantResult:
        now = self._clock()
        # D6 — une annexe (parent_id fourni) exige une mère existante, active et
        # elle-même principale (filiation plate V1, M0 §4.1). Sinon annexe orpheline.
        if request.parent_id is not None:
            parent = await self._tenants.get_by_id(request.parent_id)
            if parent is None or not parent.is_active or not parent.is_independent:
                raise InvalidParentTenantError(
                    "La mère d'une annexe doit exister, être active et être une église principale."
                )
        owner_password_hash = self._hasher.hash(Password(request.owner_password).value)

        genesis = build_genesis(
            tenant=TenantDraft(
                name=request.tenant_name,
                denomination=request.denomination,
                country=request.country,
                city=request.city,
                address=request.address,
                latitude=request.latitude,
                longitude=request.longitude,
                contact_email=request.contact_email,
                estimated_member_count=request.estimated_member_count,
                parent_id=request.parent_id,
                logo_url=request.logo_url,
                short_description=request.short_description,
                contact_name=request.contact_name,
                contact_phone=request.contact_phone,
                timezone=request.timezone,
                language=request.language,
                currency=request.currency,
                operates_annexes=request.operates_annexes,
            ),
            owner=OwnerDraft(
                email=request.owner_email,
                phone=request.owner_phone,
                first_name=request.owner_first_name,
                last_name=request.owner_last_name,
            ),
            owner_password_hash=owner_password_hash,
            now=now,
        )

        await self._store.provision(
            tenant=genesis.tenant,
            owner_account=genesis.owner_account,
            owner_membership=genesis.owner_membership,
            ownership=genesis.ownership,
            owner_password_hash=owner_password_hash,
            hash_algo_version=self._hash_algo_version,
            actor_account_id=self._platform_account_id,
        )

        return ProvisionTenantResult(
            tenant_id=genesis.tenant.id,
            owner_account_id=genesis.owner_account.id,
            owner_membership_id=genesis.owner_membership.id,
        )
