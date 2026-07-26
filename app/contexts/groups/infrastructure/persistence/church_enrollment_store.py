"""Adaptateur `ChurchEnrollmentStore` — crée une appartenance église `invited` (G-1b).

Le join-par-lien onboarde : il rattache un **compte existant** à l'église (table IAM
`memberships`) — dépendance groups → iam, sens autorisé. Ne touche pas au compte.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.groups.application.ports import ChurchEnrollmentStore
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.infrastructure.persistence.models import MembershipModel


class SqlChurchEnrollmentStore(ChurchEnrollmentStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enroll_invited(
        self, *, account_id: UUID, tenant_id: UUID, actor_account_id: UUID, now: datetime
    ) -> UUID:
        membership_id = uuid4()
        self._session.add(
            MembershipModel(
                id=membership_id,
                account_id=account_id,
                tenant_id=tenant_id,
                status=MembershipStatus.INVITED.value,
                last_transition_at=now,
                created_at=now,
                created_by_account_id=actor_account_id,
            )
        )
        await self._session.flush()
        return membership_id
