"""Chargement d'un groupe borné à son tenant (défense contre les IDs croisés)."""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.errors import GroupNotFoundError
from app.contexts.groups.domain.repositories import GroupRepository


async def load_group_in_tenant(
    groups: GroupRepository, group_id: UUID, tenant_id: UUID
) -> Group:
    group = await groups.get(group_id)
    if group is None or group.tenant_id != tenant_id:
        raise GroupNotFoundError(
            "Groupe introuvable dans cette église.",
            details={"group_id": str(group_id), "tenant_id": str(tenant_id)},
        )
    return group
