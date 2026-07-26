"""Use case `ModifyGroup` — renommer / basculer active↔dormant (M4, G-5).

Acte **léger** (autorité du nœud, `ensure_can_manage`) : présentation du groupe, pas
gouvernance. Type immuable et pas de déplacement dans l'arbre en V1.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.dtos import GroupDTO
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.enums import GroupStatus
from app.contexts.groups.domain.errors import GroupClosedError, InvalidGroupStatusError
from app.contexts.groups.domain.repositories import GroupRepository

_MODIFIABLE_STATUSES = frozenset({GroupStatus.ACTIVE, GroupStatus.DORMANT})


class ModifyGroup:
    def __init__(self, groups: GroupRepository, access: GroupAccessPolicy) -> None:
        self._groups = groups
        self._access = access

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        name: str | None = None,
        status: GroupStatus | None = None,
    ) -> GroupDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        if group.is_closed:
            raise GroupClosedError(
                "Ce groupe est clôturé.", details={"group_id": str(group_id)}
            )
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        if name is not None:
            group.rename(name)
        if status is not None:
            if status not in _MODIFIABLE_STATUSES:
                raise InvalidGroupStatusError(
                    "Seuls 'active' et 'dormant' sont modifiables ici.",
                    details={"status": status.value},
                )
            group.set_status(status)

        await self._groups.save(group)
        return GroupDTO(
            id=group.id,
            tenant_id=group.tenant_id,
            name=group.name,
            type=group.type.value,
            status=group.status.value,
            parent_group_id=group.parent_group_id,
        )
