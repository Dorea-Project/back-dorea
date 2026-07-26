"""Dépôts SQLAlchemy du module Referent.

La politique par type de groupe se lit **par église, avec repli sur le défaut** (`tenant_id`
NULL) : une église peut ranger ses types autrement sans qu'on touche au code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.referent_ports import (
    GroupTypePolicyRepository,
    PrimaryGroupOverrideRepository,
    ReferentHistoryRepository,
    ReferentOverrideRepository,
)
from app.contexts.watch.domain.referent import (
    GroupTypePolicy,
    PrimaryGroupOverride,
    ReferentChangeCause,
    ReferentHistoryEntry,
    ReferentOrigin,
    ReferentOverride,
)
from app.contexts.watch.infrastructure.persistence.models import (
    GroupTypePolicyModel,
    PrimaryGroupOverrideModel,
    ReferentHistoryModel,
    ReferentOverrideModel,
)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SqlGroupTypePolicyRepository(GroupTypePolicyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def all_for(self, tenant_id: UUID) -> dict[str, GroupTypePolicy]:
        stmt = select(GroupTypePolicyModel).where(
            or_(
                GroupTypePolicyModel.tenant_id.is_(None),
                GroupTypePolicyModel.tenant_id == tenant_id,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        # Le défaut d'abord, l'église ensuite : sa ligne écrase celle du défaut.
        policies: dict[str, GroupTypePolicy] = {}
        for row in sorted(rows, key=lambda r: r.tenant_id is not None):
            policies[row.group_type] = GroupTypePolicy(
                group_type=row.group_type,
                bears_veille=bool(row.bears_veille),
                primacy_rank=row.primacy_rank,
            )
        return policies


class SqlReferentOverrideRepository(ReferentOverrideRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, override: ReferentOverride) -> None:
        self._session.add(
            ReferentOverrideModel(
                id=override.id,
                tenant_id=override.tenant_id,
                person_id=override.person_id,
                referent_person_id=override.referent_person_id,
                origin=override.origin.value,
                started_at=override.started_at,
                started_by_account_id=override.started_by_account_id,
                ended_at=override.ended_at,
                ended_reason=override.ended_reason,
            )
        )
        await self._session.flush()

    async def save(self, override: ReferentOverride) -> None:
        row = await self._session.get(ReferentOverrideModel, override.id)
        if row is None:
            return
        row.ended_at = override.ended_at
        row.ended_reason = override.ended_reason
        await self._session.flush()

    async def active_for(self, person_id: UUID, tenant_id: UUID) -> list[ReferentOverride]:
        stmt = select(ReferentOverrideModel).where(
            ReferentOverrideModel.person_id == person_id,
            ReferentOverrideModel.tenant_id == tenant_id,
            ReferentOverrideModel.ended_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            ReferentOverride(
                id=r.id,
                tenant_id=r.tenant_id,
                person_id=r.person_id,
                referent_person_id=r.referent_person_id,
                origin=ReferentOrigin(r.origin),
                started_at=_aware(r.started_at),
                started_by_account_id=r.started_by_account_id,
                ended_at=_aware(r.ended_at),
                ended_reason=r.ended_reason,
            )
            for r in rows
        ]


class SqlPrimaryGroupOverrideRepository(PrimaryGroupOverrideRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, override: PrimaryGroupOverride) -> None:
        self._session.add(
            PrimaryGroupOverrideModel(
                id=override.id,
                tenant_id=override.tenant_id,
                person_id=override.person_id,
                group_id=override.group_id,
                started_at=override.started_at,
                started_by_account_id=override.started_by_account_id,
                ended_at=override.ended_at,
            )
        )
        await self._session.flush()

    async def active_for(
        self, person_id: UUID, tenant_id: UUID
    ) -> PrimaryGroupOverride | None:
        stmt = select(PrimaryGroupOverrideModel).where(
            PrimaryGroupOverrideModel.person_id == person_id,
            PrimaryGroupOverrideModel.tenant_id == tenant_id,
            PrimaryGroupOverrideModel.ended_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return PrimaryGroupOverride(
            id=row.id,
            tenant_id=row.tenant_id,
            person_id=row.person_id,
            group_id=row.group_id,
            started_at=_aware(row.started_at),
            started_by_account_id=row.started_by_account_id,
            ended_at=_aware(row.ended_at),
        )


class SqlReferentHistoryRepository(ReferentHistoryRepository):
    """Append-only : il n'existe volontairement ni `save`, ni `delete`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: ReferentHistoryEntry) -> None:
        self._session.add(
            ReferentHistoryModel(
                id=entry.id,
                tenant_id=entry.tenant_id,
                person_id=entry.person_id,
                referent_person_id=entry.referent_person_id,
                origin=entry.origin.value if entry.origin else None,
                observed_at=entry.observed_at,
                cause=entry.cause.value,
            )
        )
        await self._session.flush()

    async def last_for(
        self, person_id: UUID, tenant_id: UUID, *, before: datetime | None = None
    ) -> ReferentHistoryEntry | None:
        stmt = (
            select(ReferentHistoryModel)
            .where(
                ReferentHistoryModel.person_id == person_id,
                ReferentHistoryModel.tenant_id == tenant_id,
            )
            .order_by(ReferentHistoryModel.observed_at.desc())
            .limit(1)
        )
        if before is not None:
            stmt = stmt.where(ReferentHistoryModel.observed_at < before)
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return ReferentHistoryEntry(
            id=row.id,
            tenant_id=row.tenant_id,
            person_id=row.person_id,
            referent_person_id=row.referent_person_id,
            origin=ReferentOrigin(row.origin) if row.origin else None,
            observed_at=_aware(row.observed_at),
            cause=ReferentChangeCause(row.cause),
        )
