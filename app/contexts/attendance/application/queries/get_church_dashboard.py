"""Requête `GetChurchDashboard` — le cockpit du pasteur (backoffice, B7).

La grille de **tous les groupes** de l'église (chacun : infos + réalités) + les totaux qui
aident à décider : combien de cellules **prêtes à multiplier**, combien de personnes
**distinctes à interpeller**. Autorité **église-entière** `VIEW_PASTORAL_ALERTS`.
Un révélateur pour la décision, pas un juge.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.dtos import ChurchDashboardDTO
from app.contexts.attendance.application.pulse_service import GroupPulseComputer, classify_effectif
from app.contexts.attendance.application.vitals import compute_group_vitals
from app.contexts.attendance.domain.pulse import CARE_STATES
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.repositories import GroupMembershipRepository, GroupRepository
from app.contexts.iam.domain.permissions import Permission


class GetChurchDashboard:
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

    async def execute(self, *, actor_account_id: UUID, tenant_id: UUID) -> ChurchDashboardDTO:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )

        now = self._clock()
        cells = []
        care_accounts: set[UUID] = set()
        for group in await self._groups.list_active_by_tenant(tenant_id):
            roster = await self._group_memberships.list_active_by_group(group.id)
            pulses = await self._computer.compute(group=group, now=now)
            cells.append(compute_group_vitals(group, len(roster), classify_effectif(pulses)))
            care_accounts.update(p.account_id for p in pulses if p.state in CARE_STATES)

        return ChurchDashboardDTO(
            tenant_id=tenant_id,
            groups_count=len(cells),
            cells_ready_to_multiply=sum(1 for c in cells if c.ready_to_multiply),
            members_needing_care=len(care_accounts),  # comptes distincts (dédupliqués)
            groups=cells,
        )
