"""Implémentation SQLAlchemy de `MembershipLifecycleStore` — révocation & clôture cascade."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.iam.application.ports import MembershipLifecycleStore
from app.contexts.iam.domain.enums import (
    MembershipClosureReason,
    MembershipStatus,
    RevocationReason,
)
from app.contexts.iam.infrastructure.persistence.models import (
    MembershipModel,
    RoleAssignmentModel,
)


class SqlMembershipLifecycleStore(MembershipLifecycleStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def revoke_role(
        self,
        *,
        role_assignment_id: UUID,
        revoked_at: datetime,
        reason: RevocationReason,
    ) -> None:
        await self._session.execute(
            update(RoleAssignmentModel)
            .where(
                RoleAssignmentModel.id == role_assignment_id,
                RoleAssignmentModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at, revoked_reason=reason.value)
        )

    async def close_membership(
        self,
        *,
        membership_id: UUID,
        closed_at: datetime,
        closure_reason: MembershipClosureReason,
    ) -> None:
        # Cascade atomique : la même session porte les deux UPDATE ; commit = tout ou rien.
        await self._session.execute(
            update(RoleAssignmentModel)
            .where(
                RoleAssignmentModel.membership_id == membership_id,
                RoleAssignmentModel.revoked_at.is_(None),
            )
            .values(revoked_at=closed_at, revoked_reason=RevocationReason.DEMOTION_CASCADE.value)
        )
        await self._session.execute(
            update(MembershipModel)
            .where(MembershipModel.id == membership_id)
            .values(
                status=MembershipStatus.CLOSED.value,
                closed_at=closed_at,
                closure_reason=closure_reason.value,
            )
        )
