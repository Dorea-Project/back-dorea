"""Dépôts SQLAlchemy du module Event."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.events.domain.aggregates import (
    Event,
    EventParticipant,
    EventReactionEntry,
    EventReport,
    EventView,
)
from app.contexts.events.domain.enums import (
    EventCategory,
    EventReaction,
    EventScope,
    EventStatus,
)
from app.contexts.events.domain.repositories import (
    EventParticipantRepository,
    EventReactionRepository,
    EventReportRepository,
    EventRepository,
    EventViewRepository,
)
from app.contexts.events.infrastructure.persistence.models import (
    EventModel,
    EventParticipantModel,
    EventReactionModel,
    EventReportModel,
    EventViewModel,
)


def _to_event(row: EventModel) -> Event:
    return Event(
        id=row.id,
        tenant_id=row.tenant_id,
        author_account_id=row.author_account_id,
        category=EventCategory(row.category),
        title=row.title,
        description=row.description,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        place_label=row.place_label,
        latitude=row.latitude,
        longitude=row.longitude,
        media_urls=list(row.media_urls or []),
        scope=EventScope(row.scope),
        status=EventStatus(row.status),
        created_at=row.created_at,
        moderation_reason=row.moderation_reason,
        taken_down_at=row.taken_down_at,
    )


class SqlEventRepository(EventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: Event) -> None:
        self._session.add(
            EventModel(
                id=event.id,
                tenant_id=event.tenant_id,
                author_account_id=event.author_account_id,
                category=event.category.value,
                title=event.title,
                description=event.description,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                place_label=event.place_label,
                latitude=event.latitude,
                longitude=event.longitude,
                media_urls=list(event.media_urls),
                scope=event.scope.value,
                status=event.status.value,
                created_at=event.created_at,
            )
        )
        await self._session.flush()

    async def get(self, event_id: UUID) -> Event | None:
        row = await self._session.get(EventModel, event_id)
        return _to_event(row) if row is not None else None

    async def save(self, event: Event) -> None:
        row = await self._session.get(EventModel, event.id)
        if row is None:
            return
        row.status = event.status.value
        row.moderation_reason = event.moderation_reason
        row.taken_down_at = event.taken_down_at
        await self._session.flush()

    async def list_published_by_tenant(self, tenant_id: UUID) -> list[Event]:
        stmt = select(EventModel).where(
            EventModel.tenant_id == tenant_id,
            EventModel.status == EventStatus.PUBLISHED.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_event(r) for r in rows]

    async def list_published_by_scope(
        self, scope: EventScope, tenant_ids: list[UUID] | None = None
    ) -> list[Event]:
        if tenant_ids is not None and not tenant_ids:
            return []
        stmt = select(EventModel).where(
            EventModel.status == EventStatus.PUBLISHED.value,
            EventModel.scope == scope.value,
        )
        if tenant_ids is not None:
            stmt = stmt.where(EventModel.tenant_id.in_(tenant_ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_event(r) for r in rows]


class SqlEventParticipantRepository(EventParticipantRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, participant: EventParticipant) -> None:
        self._session.add(
            EventParticipantModel(
                id=participant.id,
                event_id=participant.event_id,
                tenant_id=participant.tenant_id,
                account_id=participant.account_id,
                confirmed_at=participant.confirmed_at,
            )
        )
        await self._session.flush()

    async def get(self, event_id: UUID, account_id: UUID) -> EventParticipant | None:
        stmt = select(EventParticipantModel).where(
            EventParticipantModel.event_id == event_id,
            EventParticipantModel.account_id == account_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return EventParticipant(
            id=row.id,
            event_id=row.event_id,
            tenant_id=row.tenant_id,
            account_id=row.account_id,
            confirmed_at=row.confirmed_at,
        )

    async def remove(self, event_id: UUID, account_id: UUID) -> None:
        await self._session.execute(
            delete(EventParticipantModel).where(
                EventParticipantModel.event_id == event_id,
                EventParticipantModel.account_id == account_id,
            )
        )
        await self._session.flush()

    async def list_by_event(self, event_id: UUID) -> list[EventParticipant]:
        stmt = select(EventParticipantModel).where(EventParticipantModel.event_id == event_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            EventParticipant(
                id=r.id,
                event_id=r.event_id,
                tenant_id=r.tenant_id,
                account_id=r.account_id,
                confirmed_at=r.confirmed_at,
            )
            for r in rows
        ]

    async def count_by_event(self, event_id: UUID) -> int:
        stmt = select(func.count()).where(EventParticipantModel.event_id == event_id)
        return int((await self._session.execute(stmt)).scalar_one())


class SqlEventReactionRepository(EventReactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for(self, event_id: UUID, account_id: UUID) -> EventReactionEntry | None:
        stmt = select(EventReactionModel).where(
            EventReactionModel.event_id == event_id,
            EventReactionModel.account_id == account_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return EventReactionEntry(
            id=row.id,
            event_id=row.event_id,
            account_id=row.account_id,
            kind=EventReaction(row.kind),
            reacted_at=row.reacted_at,
        )

    async def add(self, reaction: EventReactionEntry) -> None:
        self._session.add(
            EventReactionModel(
                id=reaction.id,
                event_id=reaction.event_id,
                account_id=reaction.account_id,
                kind=reaction.kind.value,
                reacted_at=reaction.reacted_at,
            )
        )
        await self._session.flush()

    async def remove(self, event_id: UUID, account_id: UUID) -> None:
        await self._session.execute(
            delete(EventReactionModel).where(
                EventReactionModel.event_id == event_id,
                EventReactionModel.account_id == account_id,
            )
        )
        await self._session.flush()

    async def counts_by_kind(self, event_id: UUID) -> dict[EventReaction, int]:
        stmt = (
            select(EventReactionModel.kind, func.count())
            .where(EventReactionModel.event_id == event_id)
            .group_by(EventReactionModel.kind)
        )
        rows = (await self._session.execute(stmt)).all()
        return {EventReaction(kind): int(n) for kind, n in rows}


class SqlEventViewRepository(EventViewRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, event_id: UUID, viewer_account_id: UUID) -> EventView | None:
        stmt = select(EventViewModel).where(
            EventViewModel.event_id == event_id,
            EventViewModel.viewer_account_id == viewer_account_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return EventView(
            id=row.id,
            event_id=row.event_id,
            viewer_account_id=row.viewer_account_id,
            denomination=row.denomination,
            viewed_at=row.viewed_at,
        )

    async def add(self, view: EventView) -> None:
        self._session.add(
            EventViewModel(
                id=view.id,
                event_id=view.event_id,
                viewer_account_id=view.viewer_account_id,
                denomination=view.denomination,
                viewed_at=view.viewed_at,
            )
        )
        await self._session.flush()

    async def count_by_event(self, event_id: UUID) -> int:
        stmt = select(func.count()).where(EventViewModel.event_id == event_id)
        return int((await self._session.execute(stmt)).scalar_one())

    async def counts_by_denomination(self, event_id: UUID) -> dict[str | None, int]:
        stmt = (
            select(EventViewModel.denomination, func.count())
            .where(EventViewModel.event_id == event_id)
            .group_by(EventViewModel.denomination)
        )
        rows = (await self._session.execute(stmt)).all()
        return {denom: int(n) for denom, n in rows}


class SqlEventReportRepository(EventReportRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, event_id: UUID, reporter_account_id: UUID) -> EventReport | None:
        stmt = select(EventReportModel).where(
            EventReportModel.event_id == event_id,
            EventReportModel.reporter_account_id == reporter_account_id,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return EventReport(
            id=row.id,
            event_id=row.event_id,
            reporter_account_id=row.reporter_account_id,
            reason=row.reason,
            created_at=row.created_at,
        )

    async def add(self, report: EventReport) -> None:
        self._session.add(
            EventReportModel(
                id=report.id,
                event_id=report.event_id,
                reporter_account_id=report.reporter_account_id,
                reason=report.reason,
                created_at=report.created_at,
            )
        )
        await self._session.flush()

    async def count_by_event(self, event_id: UUID) -> int:
        stmt = select(func.count()).where(EventReportModel.event_id == event_id)
        return int((await self._session.execute(stmt)).scalar_one())

    async def counts_by_event(self) -> dict[UUID, int]:
        stmt = select(EventReportModel.event_id, func.count()).group_by(
            EventReportModel.event_id
        )
        rows = (await self._session.execute(stmt)).all()
        return {event_id: int(n) for event_id, n in rows}
