"""Use case `LeaveGroup` — un membre quitte un groupe lui-même (mobile, M4, G-1b).

Acte personnel (pas d'autorité de gestion) : on ne peut quitter que **sa propre**
appartenance. L'appartenance passe à `left` (trace conservée).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.domain.errors import GroupMembershipNotFoundError
from app.contexts.groups.domain.repositories import GroupMembershipRepository


class LeaveGroup:
    def __init__(self, group_memberships: GroupMembershipRepository, *, clock) -> None:
        self._group_memberships = group_memberships
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, group_id: UUID) -> None:
        membership = await self._group_memberships.get_active(actor_account_id, group_id)
        if membership is None:
            raise GroupMembershipNotFoundError(
                "Vous n'êtes pas membre actif de ce groupe.",
                details={"group_id": str(group_id)},
            )
        membership.leave(now=self._clock())
        await self._group_memberships.save(membership)
