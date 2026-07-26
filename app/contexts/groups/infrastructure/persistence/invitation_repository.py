"""Implémentation SQLAlchemy de `GroupInvitationRepository` (G-1b)."""

from __future__ import annotations

from datetime import UTC
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.groups.domain.invitation import GroupInvitation
from app.contexts.groups.domain.repositories import GroupInvitationRepository
from app.contexts.groups.infrastructure.persistence.models import GroupInvitationModel


def _aware(dt):
    """SQLite rend des datetimes naïfs — on rattache UTC pour comparer à un `now` aware."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_invitation(row: GroupInvitationModel) -> GroupInvitation:
    return GroupInvitation(
        id=row.id,
        group_id=row.group_id,
        tenant_id=row.tenant_id,
        code=row.code,
        created_by_account_id=row.created_by_account_id,
        created_at=_aware(row.created_at),
        expires_at=_aware(row.expires_at),
        revoked_at=_aware(row.revoked_at),
    )


class SqlGroupInvitationRepository(GroupInvitationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invitation: GroupInvitation) -> None:
        self._session.add(
            GroupInvitationModel(
                id=invitation.id,
                group_id=invitation.group_id,
                tenant_id=invitation.tenant_id,
                code=invitation.code,
                created_by_account_id=invitation.created_by_account_id,
                created_at=invitation.created_at,
                expires_at=invitation.expires_at,
                revoked_at=invitation.revoked_at,
            )
        )
        await self._session.flush()

    async def get(self, invitation_id: UUID) -> GroupInvitation | None:
        row = await self._session.get(GroupInvitationModel, invitation_id)
        return _to_invitation(row) if row is not None else None

    async def get_by_code(self, code: str) -> GroupInvitation | None:
        stmt = select(GroupInvitationModel).where(GroupInvitationModel.code == code)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_invitation(row) if row is not None else None

    async def save(self, invitation: GroupInvitation) -> None:
        await self._session.execute(
            update(GroupInvitationModel)
            .where(GroupInvitationModel.id == invitation.id)
            .values(revoked_at=invitation.revoked_at)
        )
