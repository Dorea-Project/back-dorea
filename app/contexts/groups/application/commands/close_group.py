"""Use case `CloseGroup` — fermeture douce d'un groupe (M4, G-5).

Acte **structurel** (autorité du parent, `ensure_can_manage_structure`). Bloqué si des
**sous-groupes actifs** subsistent (on ferme les enfants d'abord). Cascade atomique :
statut → `closed`, appartenances actives → `left`, rôles du nœud **révoqués**.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.application.ports import ChurchRoleStore
from app.contexts.groups.domain.errors import GroupClosedError, GroupHasActiveChildrenError
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)


class CloseGroup:
    def __init__(
        self,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        roles: ChurchRoleStore,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._group_memberships = group_memberships
        self._roles = roles
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID
    ) -> None:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        if group.is_closed:
            raise GroupClosedError(
                "Ce groupe est déjà clôturé.", details={"group_id": str(group_id)}
            )
        await self._access.ensure_can_manage_structure(
            actor_account_id=actor_account_id, group=group
        )

        children = await self._groups.list_active_structural_children(group_id)
        if children:
            raise GroupHasActiveChildrenError(
                "Fermez d'abord les sous-groupes actifs.",
                details={"group_id": str(group_id), "active_children": len(children)},
            )

        now = self._clock()
        for gm in await self._group_memberships.list_active_by_group(group_id):
            gm.leave(now=now)
            await self._group_memberships.save(gm)
        await self._roles.revoke_all_group_roles(group_id=group_id, now=now)

        group.mark_closed()
        await self._groups.save(group)
