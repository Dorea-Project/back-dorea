"""Adaptateur du port `EventAudiencePort` — lit tenant (dénomination) + iam (membres actifs).

Compose ce qui existe : la dénomination via le dépôt Tenant, la portée « église » par un décompte
direct des appartenances actives (statut ≠ `closed`) — sans toucher l'interface partagée du
`MembershipRepository`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.events.application.ports import EventAudiencePort
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.infrastructure.persistence.models import MembershipModel
from app.contexts.tenant.infrastructure.persistence.models import TenantModel
from app.contexts.tenant.infrastructure.persistence.tenant_repo import SqlTenantRepository


class IamTenantAudienceAdapter(EventAudiencePort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tenants = SqlTenantRepository(session)

    async def denomination_of(self, tenant_id: UUID) -> str | None:
        tenant = await self._tenants.get_by_id(tenant_id)
        return tenant.denomination if tenant is not None else None

    async def count_active_members(self, tenant_id: UUID) -> int:
        stmt = select(func.count()).where(
            MembershipModel.tenant_id == tenant_id,
            MembershipModel.status != MembershipStatus.CLOSED.value,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def tenants_in_denomination(self, denomination: str) -> list[UUID]:
        stmt = select(TenantModel.id).where(TenantModel.denomination == denomination)
        return list((await self._session.execute(stmt)).scalars().all())

    async def all_tenant_ids(self) -> list[UUID]:
        stmt = select(TenantModel.id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def member_account_ids(self, tenant_ids: list[UUID]) -> list[UUID]:
        if not tenant_ids:
            return []
        stmt = select(MembershipModel.account_id.distinct()).where(
            MembershipModel.tenant_id.in_(tenant_ids),
            MembershipModel.status != MembershipStatus.CLOSED.value,
        )
        return list((await self._session.execute(stmt)).scalars().all())
