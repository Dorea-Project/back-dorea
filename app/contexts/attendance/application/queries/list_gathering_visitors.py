"""Requête `ListGatheringVisitors` — les visages nouveaux d'une rencontre (M6-3)."""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.authz import authorize_on_gathering, load_gathering
from app.contexts.attendance.application.dtos import VisitorDTO
from app.contexts.attendance.domain.repositories import GatheringRepository, VisitorRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.repositories import GroupRepository


class ListGatheringVisitors:
    def __init__(
        self,
        gatherings: GatheringRepository,
        visitors: VisitorRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
    ) -> None:
        self._gatherings = gatherings
        self._visitors = visitors
        self._groups = groups
        self._access = access

    async def execute(
        self, *, actor_account_id: UUID, gathering_id: UUID
    ) -> list[VisitorDTO]:
        gathering = await load_gathering(self._gatherings, gathering_id)
        await authorize_on_gathering(
            gathering=gathering, groups=self._groups, access=self._access,
            actor_account_id=actor_account_id,
        )
        rows = await self._visitors.list_for_gathering(gathering_id)
        return [
            VisitorDTO(id=v.id, gathering_id=v.gathering_id, name=v.name, phone=v.phone)
            for v in rows
        ]
