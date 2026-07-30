"""Use case `SelfCheckIn` — le membre se marque présent lui-même (M6-1, la 2ᵉ voix).

**Le code de séance EST l'autorisation** (façon Kahoot) : le membre tape le code que le
responsable affiche, dans la fenêtre où la rencontre est **ouverte** → présent, source `self`.
Idempotent. Réservé aux **membres du groupe** (un présent hors-roster = visiteur, M6-3).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.attendance.application.dtos import SelfCheckInDTO
from app.contexts.attendance.application.return_detection import DetectReturn
from app.contexts.attendance.domain.aggregates import AttendanceRecord
from app.contexts.attendance.domain.enums import AttendanceMark, AttendanceSource
from app.contexts.attendance.domain.errors import GatheringNotFoundError, NotAGroupMemberError
from app.contexts.attendance.domain.repositories import (
    AttendanceRecordRepository,
    GatheringRepository,
)
from app.contexts.groups.domain.repositories import GroupMembershipRepository


class SelfCheckIn:
    def __init__(
        self,
        gatherings: GatheringRepository,
        records: AttendanceRecordRepository,
        group_memberships: GroupMembershipRepository,
        returns: DetectReturn | None = None,
        *,
        clock,
    ) -> None:
        self._gatherings = gatherings
        self._records = records
        self._group_memberships = group_memberships
        self._returns = returns
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, code: str) -> SelfCheckInDTO:
        gathering = await self._gatherings.get_open_by_check_in_code(code)
        if gathering is None:
            raise GatheringNotFoundError(
                "Code de séance invalide ou rencontre clôturée.", details={"code": code}
            )

        # On ne s'auto-marque que dans SON groupe (le hors-roster = visiteur, M6-3).
        if await self._group_memberships.get_active(actor_account_id, gathering.group_id) is None:
            raise NotAGroupMemberError(
                "Vous n'êtes pas membre de ce groupe.",
                details={"group_id": str(gathering.group_id)},
            )

        if await self._records.get_for(gathering.id, actor_account_id) is None:
            await self._records.add(
                AttendanceRecord(
                    id=uuid4(),
                    gathering_id=gathering.id,
                    account_id=actor_account_id,
                    mark=AttendanceMark.PRESENT,
                    source=AttendanceSource.SELF,  # la 2ᵉ voix
                    recorded_at=self._clock(),
                    recorded_by_account_id=actor_account_id,  # le membre lui-même
                )
            )
        if self._returns is not None:
            # Se pointer soi-même vaut présence : c'est la personne qui dit « je suis là ».
            await self._returns.on_positive_presence(
                account_id=actor_account_id,
                tenant_id=gathering.tenant_id,
                occurred_at=gathering.scheduled_at,
                gathering_id=gathering.id,
                recorded_at=self._clock(),
                # Le groupe de la rencontre : c'est son rythme qui dira quand regarder
                # à nouveau si cette personne a disparu.
                group_id=gathering.group_id,
            )
        return SelfCheckInDTO(
            gathering_id=gathering.id, group_id=gathering.group_id, title=gathering.title
        )
