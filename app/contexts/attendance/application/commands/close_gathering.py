"""Use case `CloseGathering` — figer une rencontre (M6-0). La trajectoire est arrêtée."""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.authz import authorize_on_gathering, load_gathering
from app.contexts.attendance.domain.repositories import GatheringRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.repositories import GroupRepository


class CloseGathering:
    def __init__(
        self,
        gatherings: GatheringRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._gatherings = gatherings
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, gathering_id: UUID) -> None:
        gathering = await load_gathering(self._gatherings, gathering_id)
        await authorize_on_gathering(
            gathering=gathering, groups=self._groups, access=self._access,
            actor_account_id=actor_account_id,
        )
        gathering.close(now=self._clock())
        await self._gatherings.save(gathering)
