"""Requête `GetCellReport` — santé et lignée d'une cellule (M4 §2, G-3, signal dashboard).

Renvoie l'effectif actif, la **suggestion** de multiplication (`ready_to_multiply`), la
génération et les cellules-filles. Lecture réservée à qui peut gérer le groupe (sous-arbre).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.commands.multiply_cell import MULTIPLY_THRESHOLD
from app.contexts.groups.application.dtos import CellReportDTO, DaughterCellDTO
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)


class GetCellReport:
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
    ) -> CellReportDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        members = await self._group_memberships.list_active_by_group(group_id)
        daughters = await self._groups.list_children_by_lineage(group_id)
        is_cell = group.type is GroupType.CELLULE
        return CellReportDTO(
            group_id=group.id,
            type=group.type.value,
            generation=group.generation,
            active_member_count=len(members),
            ready_to_multiply=is_cell and len(members) >= MULTIPLY_THRESHOLD,
            daughters=[
                DaughterCellDTO(id=d.id, name=d.name, generation=d.generation) for d in daughters
            ],
        )
