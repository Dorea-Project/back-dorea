"""Requête `GetGatheringRoster` — le roster malin d'une rencontre (M6-0).

Roster **dérivé** des membres actifs du groupe ; pour chacun, présent (a un signal) ou
non. L'absence est déduite (attendu moins présents) — on ne stocke jamais 20 « absent ».
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.authz import authorize_on_gathering, load_gathering
from app.contexts.attendance.application.dtos import RosterDTO, RosterEntryDTO
from app.contexts.attendance.domain.enums import AttendanceMark
from app.contexts.attendance.domain.repositories import (
    AttendanceRecordRepository,
    GatheringRepository,
    GatheringRsvpRepository,
    PlannedAbsenceRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)


class GetGatheringRoster:
    def __init__(
        self,
        gatherings: GatheringRepository,
        records: AttendanceRecordRepository,
        absences: PlannedAbsenceRepository,
        rsvps: GatheringRsvpRepository,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
    ) -> None:
        self._gatherings = gatherings
        self._records = records
        self._absences = absences
        self._rsvps = rsvps
        self._groups = groups
        self._group_memberships = group_memberships
        self._access = access

    async def execute(self, *, actor_account_id: UUID, gathering_id: UUID) -> RosterDTO:
        gathering = await load_gathering(self._gatherings, gathering_id)
        await authorize_on_gathering(
            gathering=gathering, groups=self._groups, access=self._access,
            actor_account_id=actor_account_id,
        )

        members = await self._group_memberships.list_active_by_group(gathering.group_id)
        records = await self._records.list_for_gathering(gathering_id)
        present_ids = {r.account_id for r in records if r.mark is AttendanceMark.PRESENT}

        # Excusé = déduit d'une absence pré-déclarée couvrant la date de la rencontre (M6-2).
        tenant_absences = await self._absences.list_active_by_tenant(gathering.tenant_id)
        excused_ids = {
            a.account_id for a in tenant_absences if a.covers(gathering.scheduled_at)
        }
        rsvp_ids = await self._rsvps.list_account_ids_for(gathering_id)  # « je viens » (M8)

        entries = []
        for m in members:
            present = m.account_id in present_ids
            # Présent l'emporte sur excusé (il avait prévenu mais il est venu).
            excused = (not present) and (m.account_id in excused_ids)
            entries.append(
                RosterEntryDTO(
                    account_id=m.account_id, present=present, excused=excused,
                    rsvp=m.account_id in rsvp_ids,
                )
            )
        return RosterDTO(
            gathering_id=gathering_id,
            status=gathering.status.value,
            total_expected=len(entries),
            present_count=sum(1 for e in entries if e.present),
            excused_count=sum(1 for e in entries if e.excused),
            rsvp_count=len(rsvp_ids),  # tous les « je viens » (y compris hors-roster)
            entries=entries,
        )
