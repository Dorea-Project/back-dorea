"""Requête `GetMemberTrajectory` — le drill-down d'un membre (B7+).

Le pasteur voit « Koffi — à interpeller » dans la care-list ; avant d'appeler, il veut
**comprendre**. Cette requête tend l'**histoire** : la frise de ses rencontres depuis son
arrivée (présent / excusé / absent), son état de marche, depuis quand il est silencieux,
s'il a **prévenu** (tag M6-2), et s'il est **actif ailleurs** dans le réseau. Un révélateur,
pas un verdict — la conversation de soin reste humaine. Lecture seule.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.dtos import (
    MemberTrajectoryDTO,
    TrajectoryPointDTO,
)
from app.contexts.attendance.application.pulse_service import GroupPulseComputer
from app.contexts.attendance.domain.pulse import CARE_STATES
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.errors import GroupMembershipNotFoundError
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission


class GetMemberTrajectory:
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
        self, *, actor_account_id: UUID, tenant_id: UUID, group_id: UUID, account_id: UUID
    ) -> MemberTrajectoryDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id,
            group=group,
            permission=Permission.VIEW_PASTORAL_ALERTS,
        )

        traj = await self._computer.trajectory(
            group=group, account_id=account_id, now=self._clock()
        )
        if traj is None:
            raise GroupMembershipNotFoundError(
                "Ce compte n'est pas membre actif de ce groupe.",
                details={"group_id": str(group_id), "account_id": str(account_id)},
            )

        return MemberTrajectoryDTO(
            account_id=traj.account_id,
            group_id=group_id,
            state=traj.state.value,
            needs_care=traj.state in CARE_STATES,
            missed=traj.missed,
            last_present_at=traj.last_present_at,
            active_elsewhere=traj.active_elsewhere,
            current_absence_reason=traj.current_absence_reason,
            current_absence_gravity=(
                traj.current_absence_gravity.value
                if traj.current_absence_gravity is not None
                else None
            ),
            points=[
                TrajectoryPointDTO(
                    gathering_id=p.gathering_id,
                    scheduled_at=p.scheduled_at,
                    outcome=p.outcome.value,
                    title=p.title,
                )
                for p in traj.points
            ],
        )
