"""Implémentations SQLAlchemy des dépôts Mission."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.mission.domain.aggregates import (
    MissionLink,
    MissionReaction,
    Seeker,
)
from app.contexts.mission.domain.enums import SeekerReaction, SeekerStatus
from app.contexts.mission.domain.repositories import (
    MissionLinkRepository,
    MissionReactionRepository,
    SeekerRepository,
)
from app.contexts.mission.infrastructure.persistence.models import (
    MissionLinkModel,
    MissionReactionModel,
    SeekerModel,
)


def _to_link(row: MissionLinkModel) -> MissionLink:
    return MissionLink(
        id=row.id,
        tenant_id=row.tenant_id,
        inviter_account_id=row.inviter_account_id,
        inviter_group_id=row.inviter_group_id,
        message=row.message,
        media_urls=list(row.media_urls or []),
        place_label=row.place_label,
        latitude=row.latitude,
        longitude=row.longitude,
        code=row.code,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


class SqlMissionLinkRepository(MissionLinkRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, link: MissionLink) -> None:
        self._session.add(
            MissionLinkModel(
                id=link.id,
                tenant_id=link.tenant_id,
                inviter_account_id=link.inviter_account_id,
                inviter_group_id=link.inviter_group_id,
                message=link.message,
                media_urls=list(link.media_urls),
                place_label=link.place_label,
                latitude=link.latitude,
                longitude=link.longitude,
                code=link.code,
                created_at=link.created_at,
                expires_at=link.expires_at,
                revoked_at=link.revoked_at,
            )
        )
        await self._session.flush()

    async def get(self, link_id: UUID) -> MissionLink | None:
        row = await self._session.get(MissionLinkModel, link_id)
        return _to_link(row) if row is not None else None

    async def get_by_code(self, code: str) -> MissionLink | None:
        stmt = select(MissionLinkModel).where(MissionLinkModel.code == code)
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_link(row) if row is not None else None

    async def save(self, link: MissionLink) -> None:
        row = await self._session.get(MissionLinkModel, link.id)
        if row is None:
            return
        row.revoked_at = link.revoked_at
        await self._session.flush()

    async def get_active_personal(
        self, account_id: UUID, tenant_id: UUID
    ) -> MissionLink | None:
        stmt = select(MissionLinkModel).where(
            MissionLinkModel.inviter_account_id == account_id,
            MissionLinkModel.tenant_id == tenant_id,
            MissionLinkModel.revoked_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_link(row) if row is not None else None

    async def get_active_group(self, group_id: UUID) -> MissionLink | None:
        stmt = select(MissionLinkModel).where(
            MissionLinkModel.inviter_group_id == group_id,
            MissionLinkModel.revoked_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_link(row) if row is not None else None


class SqlSeekerRepository(SeekerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, seeker: Seeker) -> None:
        self._session.add(
            SeekerModel(
                id=seeker.id,
                tenant_id=seeker.tenant_id,
                link_id=seeker.link_id,
                inviter_account_id=seeker.inviter_account_id,
                inviter_group_id=seeker.inviter_group_id,
                name=seeker.name,
                phone=seeker.phone,
                status=seeker.status.value,
                created_at=seeker.created_at,
                accompanied_by_account_id=seeker.accompanied_by_account_id,
                accompanied_at=seeker.accompanied_at,
                closed_at=seeker.closed_at,
                person_account_id=seeker.person_account_id,
                integrated_account_id=seeker.integrated_account_id,
                integrated_at=seeker.integrated_at,
            )
        )
        await self._session.flush()

    async def get(self, seeker_id: UUID) -> Seeker | None:
        row = await self._session.get(SeekerModel, seeker_id)
        return _to_seeker(row) if row is not None else None

    async def save(self, seeker: Seeker) -> None:
        row = await self._session.get(SeekerModel, seeker.id)
        if row is None:
            return
        row.status = seeker.status.value
        row.accompanied_by_account_id = seeker.accompanied_by_account_id
        row.accompanied_at = seeker.accompanied_at
        row.closed_at = seeker.closed_at
        row.person_account_id = seeker.person_account_id
        row.integrated_account_id = seeker.integrated_account_id
        row.integrated_at = seeker.integrated_at
        await self._session.flush()

    async def list_by_inviter_account(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[Seeker]:
        stmt = select(SeekerModel).where(
            SeekerModel.inviter_account_id == account_id,
            SeekerModel.tenant_id == tenant_id,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_seeker(r) for r in rows]

    async def list_by_inviter_group(self, group_id: UUID) -> list[Seeker]:
        stmt = select(SeekerModel).where(SeekerModel.inviter_group_id == group_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_seeker(r) for r in rows]

    async def count_by_link(self, link_id: UUID) -> int:
        stmt = select(func.count()).where(SeekerModel.link_id == link_id)
        return int((await self._session.execute(stmt)).scalar_one())


def _to_seeker(row: SeekerModel) -> Seeker:
    return Seeker(
        id=row.id,
        tenant_id=row.tenant_id,
        link_id=row.link_id,
        inviter_account_id=row.inviter_account_id,
        inviter_group_id=row.inviter_group_id,
        name=row.name,
        phone=row.phone,
        status=SeekerStatus(row.status),
        created_at=row.created_at,
        accompanied_by_account_id=row.accompanied_by_account_id,
        accompanied_at=row.accompanied_at,
        closed_at=row.closed_at,
        person_account_id=row.person_account_id,
        integrated_account_id=row.integrated_account_id,
        integrated_at=row.integrated_at,
    )


class SqlMissionReactionRepository(MissionReactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, reaction: MissionReaction) -> None:
        self._session.add(
            MissionReactionModel(
                id=reaction.id,
                link_id=reaction.link_id,
                kind=reaction.kind.value,
                reacted_at=reaction.reacted_at,
            )
        )
        await self._session.flush()

    async def counts_by_kind(self, link_id: UUID) -> dict[SeekerReaction, int]:
        stmt = (
            select(MissionReactionModel.kind, func.count())
            .where(MissionReactionModel.link_id == link_id)
            .group_by(MissionReactionModel.kind)
        )
        rows = (await self._session.execute(stmt)).all()
        return {SeekerReaction(kind): int(n) for kind, n in rows}
