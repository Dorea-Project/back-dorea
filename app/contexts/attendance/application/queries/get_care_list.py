"""Requête `GetCareList` — la liste « à interpeller » sur toute l'église (M7-2).

Consolide, à travers **tous les groupes** de l'église, les membres en `at_risk` / `dormant` —
le *nudge* de soin au pasteur (« prends de ses nouvelles »). Les **partagés** (Mme Richmond)
n'y figurent **jamais** (ils vont bien, ailleurs). Autorité **église-entière** (Owner/Admin/
pasteur ; un scopé passe par la pulsation de *sa* cellule, M7-0). Un révélateur, pas un juge.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.dtos import CareEntryDTO, CareListDTO
from app.contexts.attendance.application.pulse_service import GroupPulseComputer
from app.contexts.attendance.domain.pulse import CARE_STATES
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission


class GetCareList:
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

    async def execute(self, *, actor_account_id: UUID, tenant_id: UUID) -> CareListDTO:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )

        now = self._clock()
        entries: list[CareEntryDTO] = []
        for group in await self._groups.list_active_by_tenant(tenant_id):
            for p in await self._computer.compute(group=group, now=now):
                if p.state in CARE_STATES:  # at_risk / dormant — jamais « shared »
                    entries.append(
                        CareEntryDTO(
                            account_id=p.account_id,
                            group_id=group.id,
                            group_name=group.name,
                            state=p.state.value,
                            missed=p.missed,
                            last_present_at=p.last_present_at,
                        )
                    )

        entries.sort(key=lambda e: e.missed, reverse=True)  # les plus silencieux d'abord
        return CareListDTO(tenant_id=tenant_id, count=len(entries), entries=entries)
