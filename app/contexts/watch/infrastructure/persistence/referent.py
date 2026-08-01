"""Dépôts SQLAlchemy du module Referent.

La politique par type de groupe se lit **par église, avec repli sur le défaut** (`tenant_id`
NULL) : une église peut ranger ses types autrement sans qu'on touche au code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.referent_ports import (
    CoverageGapStore,
    GroupTypePolicyRepository,
    PrimaryGroupOverrideRepository,
    ReferentHistoryRepository,
    ReferentOverrideRepository,
    WatchParameterRepository,
)
from app.contexts.watch.calibration.ports import WatchParameterWriter
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import CoverageGap, CoverageScope
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam
from app.contexts.watch.domain.referent import (
    GroupTypePolicy,
    PrimaryGroupOverride,
    ReferentChangeCause,
    ReferentHistoryEntry,
    ReferentOrigin,
    ReferentOverride,
)
from app.contexts.watch.infrastructure.persistence.models import (
    CoverageGapModel,
    GroupTypePolicyModel,
    PrimaryGroupOverrideModel,
    ReferentHistoryModel,
    ReferentOverrideModel,
    WatchParameterModel,
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


class SqlCoverageGapStore(CoverageGapStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_once(self, record: CoverageGapRecord) -> bool:
        """Un défaut qui se répète chaque nuit devient du bruit, et le bruit se désapprend."""
        stmt = select(CoverageGapModel.id).where(
            CoverageGapModel.tenant_id == record.tenant_id,
            CoverageGapModel.gap == record.gap.value,
            CoverageGapModel.scope == record.scope.value,
            CoverageGapModel.subject_id.is_(record.subject_id)
            if record.subject_id is None
            else CoverageGapModel.subject_id == record.subject_id,
            CoverageGapModel.resolved_at.is_(None),
        )
        if (await self._session.execute(stmt)).scalar_one_or_none() is not None:
            return False

        self._session.add(
            CoverageGapModel(
                id=record.id,
                tenant_id=record.tenant_id,
                scope=record.scope.value,
                subject_id=record.subject_id,
                gap=record.gap.value,
                reason=record.reason,
                observed_at=record.observed_at,
                resolved_at=record.resolved_at,
            )
        )
        await self._session.flush()
        return True

    async def open_gaps(self, tenant_id: UUID) -> list[CoverageGapRecord]:
        stmt = select(CoverageGapModel).where(
            CoverageGapModel.tenant_id == tenant_id,
            CoverageGapModel.resolved_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            CoverageGapRecord(
                id=r.id,
                tenant_id=r.tenant_id,
                scope=CoverageScope(r.scope),
                gap=CoverageGap(r.gap),
                reason=r.reason,
                observed_at=_aware(r.observed_at),
                subject_id=r.subject_id,
                resolved_at=_aware(r.resolved_at),
            )
            for r in rows
        ]


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


class SqlWatchParameterRepository(WatchParameterRepository, WatchParameterWriter):
    """Lit la valeur de l'église, sinon celle du défaut, sinon la valeur de départ codée.

    Le troisième repli n'est pas une constante déguisée : c'est le filet qui évite qu'une base
    non initialisée fasse tomber le moteur. Le seed pose les défauts en table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_int(self, tenant_id: UUID, param: WatchParam) -> int:
        stmt = select(WatchParameterModel).where(
            WatchParameterModel.param == param.value,
            or_(
                WatchParameterModel.tenant_id.is_(None),
                WatchParameterModel.tenant_id == tenant_id,
            ),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        # La ligne de l'église écrase celle du défaut.
        chosen = next((r for r in rows if r.tenant_id is not None), None) or next(
            iter(rows), None
        )
        return chosen.value if chosen is not None else DEFAULTS[param]

    async def set_int(self, *, tenant_id: UUID, param: WatchParam, value: int) -> None:
        stmt = select(WatchParameterModel).where(
            WatchParameterModel.param == param.value,
            WatchParameterModel.tenant_id == tenant_id,  # jamais la ligne du défaut
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            self._session.add(
                WatchParameterModel(
                    id=uuid4(), tenant_id=tenant_id, param=param.value, value=value
                )
            )
        else:
            row.value = value
