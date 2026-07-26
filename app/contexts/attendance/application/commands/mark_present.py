"""Use cases de pointage (M6-0) : `MarkPresent` / `UnmarkPresent`.

**Idempotents** (marquer deux fois = pareil) → le client hors-ligne rejoue ses marques.
On ne pointe présent qu'un **membre du roster** (un présent hors-roster = visiteur, M6-3).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.attendance.application.authz import authorize_on_gathering, load_gathering
from app.contexts.attendance.application.return_detection import DetectReturn
from app.contexts.attendance.domain.aggregates import AttendanceRecord
from app.contexts.attendance.domain.enums import AttendanceMark, AttendanceSource
from app.contexts.attendance.domain.errors import GatheringClosedError, NotAGroupMemberError
from app.contexts.attendance.domain.repositories import (
    AttendanceRecordRepository,
    GatheringRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)


class MarkPresent:
    def __init__(
        self,
        gatherings: GatheringRepository,
        records: AttendanceRecordRepository,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
        returns: DetectReturn | None = None,
        *,
        clock,
    ) -> None:
        self._gatherings = gatherings
        self._records = records
        self._groups = groups
        self._group_memberships = group_memberships
        self._access = access
        self._returns = returns
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, gathering_id: UUID, account_id: UUID
    ) -> None:
        gathering = await load_gathering(self._gatherings, gathering_id)
        if not gathering.is_open:
            raise GatheringClosedError(
                "Cette rencontre est clôturée.", details={"gathering_id": str(gathering_id)}
            )
        await authorize_on_gathering(
            gathering=gathering, groups=self._groups, access=self._access,
            actor_account_id=actor_account_id,
        )
        if await self._group_memberships.get_active(account_id, gathering.group_id) is None:
            raise NotAGroupMemberError(
                "Ce compte n'est pas membre du groupe (un présent hors-roster = visiteur).",
                details={"account_id": str(account_id), "group_id": str(gathering.group_id)},
            )

        if await self._records.get_for(gathering_id, account_id) is not None:
            return  # idempotent : déjà marqué
        await self._records.add(
            AttendanceRecord(
                id=uuid4(),
                gathering_id=gathering_id,
                account_id=account_id,
                mark=AttendanceMark.PRESENT,
                source=AttendanceSource.LEADER,
                recorded_at=self._clock(),
                recorded_by_account_id=actor_account_id,
            )
        )
        if self._returns is not None:
            # Il était là. Le moteur en tirera ce qu'il faut — daté du jour de la **rencontre**,
            # pas de la saisie : une entrée différée ne décale pas son histoire.
            await self._returns.on_positive_presence(
                account_id=account_id,
                tenant_id=gathering.tenant_id,
                occurred_at=gathering.scheduled_at,
                gathering_id=gathering.id,
                recorded_at=self._clock(),
            )


class UnmarkPresent:
    def __init__(
        self,
        gatherings: GatheringRepository,
        records: AttendanceRecordRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._gatherings = gatherings
        self._records = records
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, gathering_id: UUID, account_id: UUID
    ) -> None:
        gathering = await load_gathering(self._gatherings, gathering_id)
        if not gathering.is_open:
            raise GatheringClosedError(
                "Cette rencontre est clôturée.", details={"gathering_id": str(gathering_id)}
            )
        await authorize_on_gathering(
            gathering=gathering, groups=self._groups, access=self._access,
            actor_account_id=actor_account_id,
        )
        await self._records.remove(gathering_id, account_id)  # idempotent
