"""Adaptateur `ChurchPlantStore` — écrit la naissance d'une église-fille (G-4).

Tenant (fille) + Ownership (émancipation) + Memberships re-pointées, en une transaction
(commit porté par `get_db_session`). Écrit les tables détenues par Tenant/IAM (dépendance
groups → tenant/iam, sens autorisé). Les comptes existent déjà : on ne les touche pas.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.groups.application.ports import ChurchPlantStore
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.infrastructure.persistence.models import MembershipModel
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.ownership import Ownership
from app.contexts.tenant.infrastructure.persistence.models import OwnershipModel, TenantModel


class SqlChurchPlantStore(ChurchPlantStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def plant(
        self,
        *,
        tenant: Tenant,
        ownership: Ownership,
        memberships: list[Membership],
        actor_account_id: UUID,
    ) -> None:
        now = tenant.created_at
        self._session.add(
            TenantModel(
                id=tenant.id,
                name=tenant.name,
                status=tenant.status.value,
                denomination=tenant.denomination,
                contact_email=tenant.contact_email,
                estimated_member_count=tenant.estimated_member_count,
                country=tenant.location.country,
                city=tenant.location.city,
                address=tenant.location.address,
                latitude=tenant.location.latitude,
                longitude=tenant.location.longitude,
                parent_id=tenant.parent_id,  # filiation église-mère ↔ fille
                created_at=now,
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
        for m in memberships:
            self._session.add(
                MembershipModel(
                    id=m.id,
                    account_id=m.account_id,
                    tenant_id=m.tenant_id,
                    status=m.status.value,
                    last_transition_at=m.last_transition_at,
                    created_at=now,
                    created_by_account_id=actor_account_id,  # compte système Plateforme
                )
            )
        await self._session.flush()
