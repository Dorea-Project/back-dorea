"""Requête `GetCellHealth` — le `ready_to_multiply` **honnête** (M7-3).

La présence rend la multiplication honnête : on ne se base plus sur les **inscrits** (roster,
G-3) mais sur les **présents réels** (l'effectif vivant, M7-1). Une cellule de 40 sur le papier
mais 15 réels n'est **pas** prête. Reboucle la vision cellulaire (G-3) sur la réalité du terrain.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.dtos import CellHealthDTO
from app.contexts.attendance.application.pulse_service import GroupPulseComputer, classify_effectif
from app.contexts.groups.application.commands.multiply_cell import MULTIPLY_THRESHOLD
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.enums import GroupType
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.domain.permissions import Permission


class GetCellHealth:
    def __init__(
        self,
        computer: GroupPulseComputer,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._computer = computer
        self._groups = groups
        self._group_memberships = group_memberships
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID
    ) -> CellHealthDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id,
            group=group,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )

        roster = await self._group_memberships.list_active_by_group(group_id)
        pulses = await self._computer.compute(group=group, now=self._clock())
        active = classify_effectif(pulses).active

        is_cell = group.type is GroupType.CELLULE
        return CellHealthDTO(
            group_id=group_id,
            type=group.type.value,
            roster_count=len(roster),
            active_count=active,
            ready_to_multiply=is_cell and active >= MULTIPLY_THRESHOLD,
        )
