"""Use case `RemoveGroupMember` — retire un compte d'un groupe (M4 §6, G-1).

L'appartenance passe à `left` (on garde la trace, on ne supprime pas). Managé :
même autorisation par sous-arbre que l'ajout.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.errors import GroupMembershipNotFoundError
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)


class RemoveGroupMember:
    def __init__(
        self,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._group_memberships = group_memberships
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID, account_id: UUID
    ) -> None:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        membership = await self._group_memberships.get_active(account_id, group_id)
        if membership is None:
            raise GroupMembershipNotFoundError(
                "Ce compte n'est pas membre actif de ce groupe.",
                details={"account_id": str(account_id), "group_id": str(group_id)},
            )
        membership.leave(now=self._clock())
        await self._group_memberships.save(membership)
