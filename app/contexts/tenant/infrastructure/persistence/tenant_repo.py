"""Implémentation SQLAlchemy de `TenantRepository` (lecture + sauvegarde profil/statut)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.enums import TenantStatus
from app.contexts.tenant.domain.repositories import TenantRepository
from app.contexts.tenant.domain.value_objects import Location
from app.contexts.tenant.infrastructure.persistence.models import TenantModel


def _to_tenant(row: TenantModel) -> Tenant:
    return Tenant(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        status=TenantStatus(row.status),
        parent_id=row.parent_id,
        denomination=row.denomination,
        contact_email=row.contact_email,
        estimated_member_count=row.estimated_member_count,
        location=Location(
            country=row.country,
            city=row.city,
            address=row.address,
            latitude=row.latitude,
            longitude=row.longitude,
        ),
        slug=row.slug,
        logo_url=row.logo_url,
        short_description=row.short_description,
        contact_name=row.contact_name,
        contact_phone=row.contact_phone,
        timezone=row.timezone,
        language=row.language,
        currency=row.currency,
        operates_annexes=row.operates_annexes,
    )


class SqlTenantRepository(TenantRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        row = await self._session.get(TenantModel, tenant_id)
        return _to_tenant(row) if row is not None else None

    async def list_all(self, *, limit: int, offset: int) -> list[Tenant]:
        stmt = (
            select(TenantModel).order_by(TenantModel.created_at.desc()).limit(limit).offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_tenant(r) for r in rows]

    async def save(self, tenant: Tenant) -> None:
        loc = tenant.location
        await self._session.execute(
            update(TenantModel)
            .where(TenantModel.id == tenant.id)
            .values(
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
                country=loc.country,
                city=loc.city,
                address=loc.address,
                latitude=loc.latitude,
                longitude=loc.longitude,
            )
        )
