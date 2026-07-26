"""Implémentation SQLAlchemy de `ChurchInvitationRepository` (M-5)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.iam.domain.church_invitation import ChurchInvitation
from app.contexts.iam.domain.repositories import ChurchInvitationRepository
from app.contexts.iam.infrastructure.persistence.models import ChurchInvitationModel


def _to_domain(row: ChurchInvitationModel) -> ChurchInvitation:
    return ChurchInvitation(
        id=row.id,
        tenant_id=row.tenant_id,
        code=row.code,
        created_by_account_id=row.created_by_account_id,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


class SqlChurchInvitationRepository(ChurchInvitationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invitation: ChurchInvitation) -> None:
        self._session.add(
            ChurchInvitationModel(
                id=invitation.id,
                tenant_id=invitation.tenant_id,
                code=invitation.code,
                created_by_account_id=invitation.created_by_account_id,
                created_at=invitation.created_at,
                expires_at=invitation.expires_at,
                revoked_at=invitation.revoked_at,
            )
        )
        await self._session.flush()

    async def get(self, invitation_id: UUID) -> ChurchInvitation | None:
        row = await self._session.get(ChurchInvitationModel, invitation_id)
        return _to_domain(row) if row is not None else None

    async def get_by_code(self, code: str) -> ChurchInvitation | None:
        stmt = select(ChurchInvitationModel).where(ChurchInvitationModel.code == code)
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_domain(row) if row is not None else None

    async def save(self, invitation: ChurchInvitation) -> None:
        row = await self._session.get(ChurchInvitationModel, invitation.id)
        if row is None:
            return
        row.revoked_at = invitation.revoked_at
        await self._session.flush()

    async def list_active_by_tenant(self, tenant_id: UUID) -> list[ChurchInvitation]:
        stmt = select(ChurchInvitationModel).where(
            ChurchInvitationModel.tenant_id == tenant_id,
            ChurchInvitationModel.revoked_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]
