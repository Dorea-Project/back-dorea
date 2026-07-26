"""Use case `CreateGroup` — crée un groupe racine ou un sous-groupe (M4 §4, G-0).

Autorisation par **sous-arbre** (`GroupAccessPolicy`) : l'Owner/Admin partout, le
responsable scopé dans le sous-arbre qu'il dirige. Le sous-groupe hérite du tenant et du
chemin de son parent. Un parent d'un autre tenant est refusé (frontière d'église).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.groups.application.dtos import GroupDTO
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.errors import (
    CrossTenantParentError,
    ParentGroupNotFoundError,
)
from app.contexts.groups.domain.repositories import GroupRepository


class CreateGroup:
    def __init__(
        self,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        name: str,
        type: GroupType,
        parent_group_id: UUID | None = None,
    ) -> GroupDTO:
        parent = await self._resolve_parent(parent_group_id, tenant_id)
        await self._access.ensure_can_create(
            actor_account_id=actor_account_id, tenant_id=tenant_id, parent=parent
        )

        now = self._clock()
        if parent is None:
            group = Group.create_root(
                id=uuid4(),
                tenant_id=tenant_id,
                name=name,
                type=type,
                now=now,
                created_by_account_id=actor_account_id,
            )
        else:
            group = Group.create_child(
                id=uuid4(),
                parent=parent,
                name=name,
                type=type,
                now=now,
                created_by_account_id=actor_account_id,
            )

        await self._groups.add(group)
        return GroupDTO(
            id=group.id,
            tenant_id=group.tenant_id,
            name=group.name,
            type=group.type.value,
            status=group.status.value,
            parent_group_id=group.parent_group_id,
        )

    async def _resolve_parent(
        self, parent_group_id: UUID | None, tenant_id: UUID
    ) -> Group | None:
        if parent_group_id is None:
            return None
        parent = await self._groups.get(parent_group_id)
        if parent is None:
            raise ParentGroupNotFoundError(
                "Groupe parent introuvable.", details={"parent_group_id": str(parent_group_id)}
            )
        if parent.tenant_id != tenant_id:
            raise CrossTenantParentError(
                "Le groupe parent appartient à une autre église.",
                details={"parent_group_id": str(parent_group_id), "tenant_id": str(tenant_id)},
            )
        return parent
