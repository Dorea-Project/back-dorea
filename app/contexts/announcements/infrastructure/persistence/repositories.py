"""Implémentations SQLAlchemy des dépôts Annonces."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.announcements.domain.aggregates import (
    Announcement,
    AnnouncementEngagement,
    AnnouncementReaction,
    AnnouncementSubject,
)
from app.contexts.announcements.domain.enums import (
    AnnouncementCategory,
    AnnouncementIntent,
    AnnouncementStatus,
    SubjectConsent,
    SubjectRole,
    WatchEffect,
)
from app.contexts.announcements.domain.repositories import (
    AnnouncementEngagementRepository,
    AnnouncementReactionRepository,
    AnnouncementRepository,
    AnnouncementSubjectRepository,
)
from app.contexts.announcements.infrastructure.persistence.models import (
    AnnouncementEngagementModel,
    AnnouncementModel,
    AnnouncementReactionModel,
    AnnouncementSubjectModel,
)

_PUBLISHED = AnnouncementStatus.PUBLISHED.value


def _to_domain(row: AnnouncementModel) -> Announcement:
    return Announcement(
        id=row.id,
        tenant_id=row.tenant_id,
        category=AnnouncementCategory(row.category),
        intent=AnnouncementIntent(row.intent),
        scope_group_id=row.scope_group_id,
        title=row.title,
        body=row.body,
        author_account_id=row.author_account_id,
        concerns_account_id=row.concerns_account_id,
        published_at=row.published_at,
        status=AnnouncementStatus(row.status),
        event_at=row.event_at,
        gathering_id=row.gathering_id,
        slots_needed=row.slots_needed,
        media_urls=list(row.media_urls or []),
        expires_at=row.expires_at,
        occurred_at=row.occurred_at,
    )


def _to_subject(row: AnnouncementSubjectModel) -> AnnouncementSubject:
    return AnnouncementSubject(
        id=row.id,
        announcement_id=row.announcement_id,
        account_id=row.account_id,
        role=SubjectRole(row.role),
        effects=tuple(WatchEffect(e) for e in (row.effects or [])),
        consent=SubjectConsent(row.consent),
        attached_at=row.attached_at,
        declared_duration_days=row.declared_duration_days,
        consent_decided_at=row.consent_decided_at,
    )


class SqlAnnouncementRepository(AnnouncementRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, a: Announcement) -> None:
        self._session.add(
            AnnouncementModel(
                id=a.id,
                tenant_id=a.tenant_id,
                category=a.category.value,
                intent=a.intent.value,
                scope_group_id=a.scope_group_id,
                title=a.title,
                body=a.body,
                media_urls=list(a.media_urls),
                author_account_id=a.author_account_id,
                concerns_account_id=a.concerns_account_id,
                published_at=a.published_at,
                expires_at=a.expires_at,
                status=a.status.value,
                event_at=a.event_at,
                gathering_id=a.gathering_id,
                slots_needed=a.slots_needed,
                occurred_at=a.occurred_at,
            )
        )
        await self._session.flush()

    async def get(self, announcement_id: UUID) -> Announcement | None:
        row = await self._session.get(AnnouncementModel, announcement_id)
        return _to_domain(row) if row is not None else None

    async def save(self, a: Announcement) -> None:
        row = await self._session.get(AnnouncementModel, a.id)
        if row is None:
            return
        row.status = a.status.value
        await self._session.flush()

    async def list_feed_candidates(
        self, tenant_id: UUID, *, now: datetime, before: datetime | None, limit: int
    ) -> list[Announcement]:
        stmt = (
            select(AnnouncementModel)
            .where(
                # Les trois portées : plateforme (tenant NULL) OU cette église.
                or_(
                    AnnouncementModel.tenant_id.is_(None),
                    AnnouncementModel.tenant_id == tenant_id,
                ),
                AnnouncementModel.status == _PUBLISHED,
                or_(
                    AnnouncementModel.expires_at.is_(None),
                    AnnouncementModel.expires_at > now,
                ),
            )
            .order_by(AnnouncementModel.published_at.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(AnnouncementModel.published_at < before)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def list_by_tenant(self, tenant_id: UUID) -> list[Announcement]:
        stmt = select(AnnouncementModel).where(AnnouncementModel.tenant_id == tenant_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]


class SqlAnnouncementSubjectRepository(AnnouncementSubjectRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_all(self, subjects: list[AnnouncementSubject]) -> None:
        if not subjects:
            return
        self._session.add_all(
            [
                AnnouncementSubjectModel(
                    id=s.id,
                    announcement_id=s.announcement_id,
                    account_id=s.account_id,
                    role=s.role.value,
                    effects=[e.value for e in s.effects],
                    consent=s.consent.value,
                    declared_duration_days=s.declared_duration_days,
                    attached_at=s.attached_at,
                    consent_decided_at=s.consent_decided_at,
                )
                for s in subjects
            ]
        )
        await self._session.flush()

    async def get(self, subject_id: UUID) -> AnnouncementSubject | None:
        row = await self._session.get(AnnouncementSubjectModel, subject_id)
        return _to_subject(row) if row is not None else None

    async def save(self, subject: AnnouncementSubject) -> None:
        row = await self._session.get(AnnouncementSubjectModel, subject.id)
        if row is None:
            return
        row.consent = subject.consent.value
        row.consent_decided_at = subject.consent_decided_at
        await self._session.flush()

    async def list_for(self, announcement_id: UUID) -> list[AnnouncementSubject]:
        stmt = select(AnnouncementSubjectModel).where(
            AnnouncementSubjectModel.announcement_id == announcement_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_subject(r) for r in rows]

    async def account_ids_among(
        self, account_id: UUID, announcement_ids: list[UUID]
    ) -> set[UUID]:
        if not announcement_ids:
            return set()
        stmt = select(AnnouncementSubjectModel.announcement_id).where(
            AnnouncementSubjectModel.account_id == account_id,
            AnnouncementSubjectModel.announcement_id.in_(announcement_ids),
        )
        return set((await self._session.execute(stmt)).scalars().all())


class SqlAnnouncementEngagementRepository(AnnouncementEngagementRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, e: AnnouncementEngagement) -> None:
        self._session.add(
            AnnouncementEngagementModel(
                id=e.id,
                announcement_id=e.announcement_id,
                account_id=e.account_id,
                responded_at=e.responded_at,
            )
        )
        await self._session.flush()

    async def get(
        self, announcement_id: UUID, account_id: UUID
    ) -> AnnouncementEngagement | None:
        stmt = select(AnnouncementEngagementModel).where(
            AnnouncementEngagementModel.announcement_id == announcement_id,
            AnnouncementEngagementModel.account_id == account_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_engagement(row) if row is not None else None

    async def remove(self, announcement_id: UUID, account_id: UUID) -> None:
        await self._session.execute(
            delete(AnnouncementEngagementModel).where(
                AnnouncementEngagementModel.announcement_id == announcement_id,
                AnnouncementEngagementModel.account_id == account_id,
            )
        )

    async def count_for(self, announcement_id: UUID) -> int:
        stmt = select(func.count()).where(
            AnnouncementEngagementModel.announcement_id == announcement_id
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def list_for(self, announcement_id: UUID) -> list[AnnouncementEngagement]:
        stmt = select(AnnouncementEngagementModel).where(
            AnnouncementEngagementModel.announcement_id == announcement_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_engagement(r) for r in rows]

    async def counts_for_many(self, announcement_ids: list[UUID]) -> dict[UUID, int]:
        if not announcement_ids:
            return {}
        stmt = (
            select(AnnouncementEngagementModel.announcement_id, func.count())
            .where(AnnouncementEngagementModel.announcement_id.in_(announcement_ids))
            .group_by(AnnouncementEngagementModel.announcement_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {aid: int(n) for aid, n in rows}

    async def engaged_among(
        self, account_id: UUID, announcement_ids: list[UUID]
    ) -> set[UUID]:
        if not announcement_ids:
            return set()
        stmt = select(AnnouncementEngagementModel.announcement_id).where(
            AnnouncementEngagementModel.account_id == account_id,
            AnnouncementEngagementModel.announcement_id.in_(announcement_ids),
        )
        return set((await self._session.execute(stmt)).scalars().all())


def _to_engagement(row: AnnouncementEngagementModel) -> AnnouncementEngagement:
    return AnnouncementEngagement(
        id=row.id,
        announcement_id=row.announcement_id,
        account_id=row.account_id,
        responded_at=row.responded_at,
    )


class SqlAnnouncementReactionRepository(AnnouncementReactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_for(self, reaction: AnnouncementReaction) -> None:
        """Une réaction par (annonce, compte) : on remplace l'emoji s'il y en avait un."""
        stmt = select(AnnouncementReactionModel).where(
            AnnouncementReactionModel.announcement_id == reaction.announcement_id,
            AnnouncementReactionModel.account_id == reaction.account_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is not None:
            row.emoji = reaction.emoji
            row.reacted_at = reaction.reacted_at
        else:
            self._session.add(
                AnnouncementReactionModel(
                    id=reaction.id,
                    announcement_id=reaction.announcement_id,
                    account_id=reaction.account_id,
                    emoji=reaction.emoji,
                    reacted_at=reaction.reacted_at,
                )
            )
        await self._session.flush()

    async def remove(self, announcement_id: UUID, account_id: UUID) -> None:
        await self._session.execute(
            delete(AnnouncementReactionModel).where(
                AnnouncementReactionModel.announcement_id == announcement_id,
                AnnouncementReactionModel.account_id == account_id,
            )
        )

    async def counts_by_emoji(self, announcement_id: UUID) -> dict[str, int]:
        stmt = (
            select(AnnouncementReactionModel.emoji, func.count())
            .where(AnnouncementReactionModel.announcement_id == announcement_id)
            .group_by(AnnouncementReactionModel.emoji)
        )
        rows = (await self._session.execute(stmt)).all()
        return {emoji: int(n) for emoji, n in rows}

    async def counts_by_emoji_for_many(
        self, announcement_ids: list[UUID]
    ) -> dict[UUID, dict[str, int]]:
        if not announcement_ids:
            return {}
        stmt = (
            select(
                AnnouncementReactionModel.announcement_id,
                AnnouncementReactionModel.emoji,
                func.count(),
            )
            .where(AnnouncementReactionModel.announcement_id.in_(announcement_ids))
            .group_by(
                AnnouncementReactionModel.announcement_id, AnnouncementReactionModel.emoji
            )
        )
        out: dict[UUID, dict[str, int]] = {}
        for aid, emoji, n in (await self._session.execute(stmt)).all():
            out.setdefault(aid, {})[emoji] = int(n)
        return out

    async def reactions_of_account_among(
        self, account_id: UUID, announcement_ids: list[UUID]
    ) -> dict[UUID, str]:
        if not announcement_ids:
            return {}
        stmt = select(
            AnnouncementReactionModel.announcement_id, AnnouncementReactionModel.emoji
        ).where(
            AnnouncementReactionModel.account_id == account_id,
            AnnouncementReactionModel.announcement_id.in_(announcement_ids),
        )
        return {aid: emoji for aid, emoji in (await self._session.execute(stmt)).all()}
