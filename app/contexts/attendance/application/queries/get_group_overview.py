"""Requête `GetGroupOverview` — le **détail d'un groupe** : ses infos + ses réalités (mobile).

Pour l'écran « détails du groupe » du responsable : le nom, le type, la génération, l'effectif
*réel*, les à-interpeller, les partagés, et s'il est prêt à multiplier. Autorité de la cellule
(`VIEW_PASTORAL_ALERTS`, portée sous-arbre).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.dtos import GroupVitalsDTO
from app.contexts.attendance.application.pulse_service import GroupPulseComputer, classify_effectif
from app.contexts.attendance.application.vitals import compute_group_vitals
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.domain.permissions import Permission


class GetGroupOverview:
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
    ) -> GroupVitalsDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id,
            group=group,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )
        roster = await self._group_memberships.list_active_by_group(group_id)
        pulses = await self._computer.compute(group=group, now=self._clock())
        return compute_group_vitals(group, len(roster), classify_effectif(pulses))
