"""Dépôt SQLAlchemy du module Sermon."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.sermon.domain.aggregates import Sermon
from app.contexts.sermon.domain.companion import CompanionSession
from app.contexts.sermon.domain.digest import Capsule, CompanionQuestion, SermonDigest
from app.contexts.sermon.domain.enums import CompanionStatus, SermonSourceKind, SermonStatus
from app.contexts.sermon.domain.repositories import (
    CompanionSessionRepository,
    SermonRepository,
)
from app.contexts.sermon.infrastructure.persistence.models import (
    CompanionSessionModel,
    SermonDigestModel,
    SermonModel,
)


def _to_digest(row: SermonDigestModel) -> SermonDigest:
    return SermonDigest(
        summary=row.summary,
        key_points=tuple(row.key_points or []),
        capsules=tuple(Capsule(title=c["title"], body=c["body"]) for c in (row.capsules or [])),
        questions=tuple(
            CompanionQuestion(prompt=q["prompt"], guidance=q["guidance"])
            for q in (row.questions or [])
        ),
    )


def _digest_model(sermon_id: UUID, digest: SermonDigest) -> SermonDigestModel:
    return SermonDigestModel(
        sermon_id=sermon_id,
        summary=digest.summary,
        key_points=list(digest.key_points),
        capsules=[{"title": c.title, "body": c.body} for c in digest.capsules],
        questions=[{"prompt": q.prompt, "guidance": q.guidance} for q in digest.questions],
    )


def _to_sermon(row: SermonModel, digest_row: SermonDigestModel | None) -> Sermon:
    return Sermon(
        id=row.id,
        tenant_id=row.tenant_id,
        author_account_id=row.author_account_id,
        title=row.title,
        reference=row.reference,
        source_kind=SermonSourceKind(row.source_kind),
        raw_text=row.raw_text,
        preached_on=row.preached_on,
        status=SermonStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        approved_at=row.approved_at,
        digest=_to_digest(digest_row) if digest_row is not None else None,
    )


class SqlSermonRepository(SermonRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, sermon: Sermon) -> None:
        self._session.add(
            SermonModel(
                id=sermon.id,
                tenant_id=sermon.tenant_id,
                author_account_id=sermon.author_account_id,
                title=sermon.title,
                reference=sermon.reference,
                source_kind=sermon.source_kind.value,
                raw_text=sermon.raw_text,
                preached_on=sermon.preached_on,
                status=sermon.status.value,
                created_at=sermon.created_at,
                updated_at=sermon.updated_at,
                approved_at=sermon.approved_at,
            )
        )
        if sermon.digest is not None:
            self._session.add(_digest_model(sermon.id, sermon.digest))
        await self._session.flush()

    async def get(self, sermon_id: UUID) -> Sermon | None:
        row = await self._session.get(SermonModel, sermon_id)
        if row is None:
            return None
        digest_row = await self._session.get(SermonDigestModel, sermon_id)
        return _to_sermon(row, digest_row)

    async def save(self, sermon: Sermon) -> None:
        row = await self._session.get(SermonModel, sermon.id)
        if row is None:
            return
        row.status = sermon.status.value
        row.approved_at = sermon.approved_at
        row.updated_at = sermon.updated_at
        await self._session.flush()

    async def list_by_tenant(self, tenant_id: UUID) -> list[Sermon]:
        stmt = (
            select(SermonModel)
            .where(SermonModel.tenant_id == tenant_id)
            .order_by(SermonModel.preached_on.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        digests = {
            d.sermon_id: d
            for d in (
                await self._session.execute(
                    select(SermonDigestModel).where(
                        SermonDigestModel.sermon_id.in_([r.id for r in rows])
                    )
                )
            ).scalars().all()
        } if rows else {}
        return [_to_sermon(r, digests.get(r.id)) for r in rows]


def _to_session(row: CompanionSessionModel) -> CompanionSession:
    return CompanionSession(
        id=row.id,
        sermon_id=row.sermon_id,
        tenant_id=row.tenant_id,
        member_account_id=row.member_account_id,
        attended=row.attended,
        step=row.step,
        status=CompanionStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlCompanionSessionRepository(CompanionSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, companion: CompanionSession) -> None:
        self._session.add(
            CompanionSessionModel(
                id=companion.id,
                sermon_id=companion.sermon_id,
                tenant_id=companion.tenant_id,
                member_account_id=companion.member_account_id,
                attended=companion.attended,
                step=companion.step,
                status=companion.status.value,
                created_at=companion.created_at,
                updated_at=companion.updated_at,
            )
        )
        await self._session.flush()

    async def get(self, session_id: UUID) -> CompanionSession | None:
        row = await self._session.get(CompanionSessionModel, session_id)
        return _to_session(row) if row is not None else None

    async def save(self, companion: CompanionSession) -> None:
        row = await self._session.get(CompanionSessionModel, companion.id)
        if row is None:
            return
        row.attended = companion.attended
        row.step = companion.step
        row.status = companion.status.value
        row.updated_at = companion.updated_at
        await self._session.flush()

    async def find_active(
        self, member_account_id: UUID, sermon_id: UUID
    ) -> CompanionSession | None:
        stmt = select(CompanionSessionModel).where(
            CompanionSessionModel.member_account_id == member_account_id,
            CompanionSessionModel.sermon_id == sermon_id,
            CompanionSessionModel.status == CompanionStatus.IN_PROGRESS.value,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_session(row) if row is not None else None
