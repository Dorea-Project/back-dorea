"""Requête `GetGroupPulse` — la pulsation de la cellule (M7-0).

Projette l'état de marche calculé par `GroupPulseComputer`. Lecture seule ; autorisée par
`VIEW_PASTORAL_ALERTS`. Un **révélateur**, pas un juge (M7 §1).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.dtos import GroupPulseDTO, PulseEntryDTO
from app.contexts.attendance.application.pulse_service import GroupPulseComputer
from app.contexts.attendance.domain.pulse import CARE_STATES
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission


class GetGroupPulse:
    def __init__(
        self,
        computer: GroupPulseComputer,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._computer = computer
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID
    ) -> GroupPulseDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id,
            group=group,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )

        pulses = await self._computer.compute(group=group, now=self._clock())
        entries = [
            PulseEntryDTO(
                account_id=p.account_id,
                state=p.state.value,
                missed=p.missed,
                needs_care=p.state in CARE_STATES,
                last_present_at=p.last_present_at,
            )
            for p in pulses
        ]
        return GroupPulseDTO(
            group_id=group_id,
            total=len(entries),
            needs_care_count=sum(1 for e in entries if e.needs_care),
            entries=entries,
        )
