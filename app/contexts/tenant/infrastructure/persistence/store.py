"""Implémentation SQLAlchemy de `ProvisioningStore` — écriture atomique de la genèse.

Les quatre insertions (tenant, account owner, membership, role owner) partagent la
**même session** : le commit est porté par la dépendance `get_db_session` (une
transaction par requête). Soit tout est écrit, soit rien (M0 §6).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import AccountCreationSource
from app.contexts.iam.infrastructure.persistence.models import (
    AccountModel,
    MembershipModel,
    RoleAssignmentModel,
)
from app.contexts.tenant.application.ports import ProvisioningStore
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.ownership import Ownership
from app.contexts.tenant.infrastructure.persistence.models import OwnershipModel, TenantModel


class SqlProvisioningStore(ProvisioningStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def provision(
        self,
        *,
        tenant: Tenant,
        owner_account: Account,
        owner_membership: Membership,
        ownership: Ownership,
        owner_password_hash: str,
        hash_algo_version: int,
        actor_account_id: UUID,
    ) -> None:
        # `now` cohérent : mêmes horodatages produits par la commande.
        now = tenant.created_at

        self._session.add(
            TenantModel(
                id=tenant.id,
                name=tenant.name,
                slug=tenant.slug,
                status=tenant.status.value,
                denomination=tenant.denomination,
                contact_email=tenant.contact_email,
                contact_name=tenant.contact_name,
                contact_phone=tenant.contact_phone,
                estimated_member_count=tenant.estimated_member_count,
                logo_url=tenant.logo_url,
                short_description=tenant.short_description,
                timezone=tenant.timezone,
                language=tenant.language,
                currency=tenant.currency,
                country=tenant.location.country,
                city=tenant.location.city,
                address=tenant.location.address,
                latitude=tenant.location.latitude,
                longitude=tenant.location.longitude,
                parent_id=tenant.parent_id,
                operates_annexes=tenant.operates_annexes,
                created_at=now,
            )
        )
        self._session.add(
            AccountModel(
                id=owner_account.id,
                phone_number=owner_account.phone_number,
                first_name=owner_account.first_name,
                last_name=owner_account.last_name,
                email=owner_account.email,
                password_hash=owner_password_hash,  # credential initial (remis à l'Owner)
                hash_algo_version=hash_algo_version,
                is_phone_verified=owner_account.is_phone_verified,
                created_at=now,
                created_by_type=AccountCreationSource.OWNER.value,  # M0 : créé par la voie owner
                status=owner_account.status.value,
            )
        )
        self._session.add(
            MembershipModel(
                id=owner_membership.id,
                account_id=owner_membership.account_id,
                tenant_id=owner_membership.tenant_id,
                status=owner_membership.status.value,
                last_transition_at=owner_membership.last_transition_at,
                created_at=now,
                created_by_account_id=actor_account_id,  # compte système Plateforme (P0.1)
            )
        )
        for ra in owner_membership.active_roles():
            self._session.add(
                RoleAssignmentModel(
                    id=ra.id,
                    membership_id=owner_membership.id,
                    tenant_id=owner_membership.tenant_id,  # dénormalisé (P0.2)
                    role=ra.role.value,
                    group_id=ra.group_id,
                    assigned_at=ra.assigned_at,
                    assigned_by_account_id=actor_account_id,
                )
            )

        self._session.add(
            OwnershipModel(
                id=ownership.id,
                account_id=ownership.account_id,
                tenant_id=ownership.tenant_id,
                status=ownership.status.value,
                mode=ownership.mode.value,
                started_at=ownership.started_at,
                ended_at=ownership.ended_at,
            )
        )

        await self._session.flush()
