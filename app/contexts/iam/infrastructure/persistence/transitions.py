"""Implémentation SQLAlchemy de `MembershipTransitionStore`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.iam.application.ports import MembershipTransitionStore
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.infrastructure.persistence.models import MembershipModel


class SqlMembershipTransitionStore(MembershipTransitionStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply_transition(
        self,
        *,
        membership_id: UUID,
        new_status: MembershipStatus,
        previous_status: MembershipStatus,
        transitioned_at: datetime,
    ) -> None:
        await self._session.execute(
            update(MembershipModel)
            .where(MembershipModel.id == membership_id)
            .values(
                status=new_status.value,
                previous_status=previous_status.value,
                last_transition_at=transitioned_at,
            )
        )
