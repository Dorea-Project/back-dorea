"""Use case : `IsConfirmedMember` (M1 §8.2)."""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.domain.repositories import MembershipRepository


class IsConfirmedMember:
    def __init__(self, memberships: MembershipRepository) -> None:
        self._memberships = memberships

    async def execute(self, *, account_id: UUID, tenant_id: UUID) -> bool:
        membership = await self._memberships.get_active(account_id, tenant_id)
        return membership is not None and membership.is_confirmed_member
