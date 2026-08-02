"""Adaptateur du port `EventAudiencePort` — lit tenant (dénomination) + iam (membres actifs).

Compose ce qui existe : la dénomination via le dépôt Tenant, la portée « église » par un décompte
direct des appartenances actives (statut ≠ `closed`) — sans toucher l'interface partagée du
`MembershipRepository`.
"""

from __future__ import annotations

from math import cos, radians
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.events.application.ports import EventAudiencePort
from app.contexts.events.domain.geo import KM_PER_DEGREE_LAT as _KM_PER_DEGREE_LAT
from app.contexts.events.domain.geo import distance_km
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

    async def location_of(self, tenant_id: UUID) -> tuple[float, float] | None:
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None or tenant.location is None:
            return None
        lat, lon = tenant.location.latitude, tenant.location.longitude
        return (lat, lon) if lat is not None and lon is not None else None

    async def tenants_near(
        self, *, latitude: float, longitude: float, radius_km: float
    ) -> list[UUID]:
        """**Rectangle en SQL, cercle en Python.** Deux étages, et c'est délibéré.

        Une haversine en SQL demanderait des fonctions trigonométriques : PostgreSQL les a,
        SQLite pas toujours — et une requête qui ne tourne que sur la base de production est une
        requête qu'on ne teste pas. Le rectangle élimine 99 % des lignes avec une comparaison
        que toutes les bases savent faire et indexer ; le cercle exact se calcule ensuite sur la
        poignée qui reste. À l'échelle d'un pays, il n'y a rien à optimiser de plus.
        """
        lat_span = radius_km / _KM_PER_DEGREE_LAT
        # Un degré de longitude rétrécit vers les pôles. Près de l'équateur (Abidjan) le facteur
        # vaut presque 1 ; sans lui, la boîte serait trop étroite à Oslo et personne ne le verrait.
        cos_lat = max(cos(radians(latitude)), 0.01)  # garde-fou : jamais de division par zéro
        lon_span = radius_km / (_KM_PER_DEGREE_LAT * cos_lat)

        stmt = select(TenantModel.id, TenantModel.latitude, TenantModel.longitude).where(
            TenantModel.latitude.is_not(None),
            TenantModel.longitude.is_not(None),
            TenantModel.latitude.between(latitude - lat_span, latitude + lat_span),
            TenantModel.longitude.between(longitude - lon_span, longitude + lon_span),
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            tenant_id
            for tenant_id, lat, lon in rows
            if distance_km(latitude, longitude, lat, lon) <= radius_km
        ]

    async def member_account_ids(self, tenant_ids: list[UUID]) -> list[UUID]:
        if not tenant_ids:
            return []
        stmt = select(MembershipModel.account_id.distinct()).where(
            MembershipModel.tenant_id.in_(tenant_ids),
            MembershipModel.status != MembershipStatus.CLOSED.value,
        )
        return list((await self._session.execute(stmt)).scalars().all())
