"""Requête `ListGroupMembers` — roster des membres actifs d'un groupe (M4 §6, G-1).

Lecture réservée à qui peut **gérer** le groupe (même portée sous-arbre que l'ajout/retrait).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.dtos import GroupMemberDTO
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)


class ListGroupMembers:
    def __init__(
        self,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
    ) -> None:
        self._groups = groups
        self._group_memberships = group_memberships
        self._access = access

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID
    ) -> list[GroupMemberDTO]:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        rows = await self._group_memberships.list_active_by_group(group_id)
        return [
            GroupMemberDTO(
                group_id=m.group_id,
                account_id=m.account_id,
                status=m.status.value,
                joined_at=m.joined_at,
            )
            for m in rows
        ]
