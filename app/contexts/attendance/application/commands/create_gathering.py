"""Use case `CreateGathering` — ouvrir une rencontre de groupe (M6-0).

Autorisée par `RECORD_ATTENDANCE` (portée sous-arbre). M6-0 : rencontre **de groupe**
(le culte église-entière viendra plus tard). Elle démarre **ouverte**.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.attendance.application.dtos import GatheringDTO
from app.contexts.attendance.application.ports import SessionCodeGenerator
from app.contexts.attendance.domain.aggregates import Gathering
from app.contexts.attendance.domain.enums import GatheringStatus, GatheringType
from app.contexts.attendance.domain.repositories import GatheringRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission


class CreateGathering:
    def __init__(
        self,
        gatherings: GatheringRepository,
        groups: GroupRepository,
        codes: SessionCodeGenerator,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._gatherings = gatherings
        self._groups = groups
        self._codes = codes
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        type: GatheringType,
        scheduled_at: datetime,
        title: str | None = None,
    ) -> GatheringDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id,
            group=group,
            permission=Permission.RECORD_ATTENDANCE,
        )

        gathering = Gathering(
            id=uuid4(),
            tenant_id=tenant_id,
            group_id=group_id,
            type=type,
            title=title,
            scheduled_at=scheduled_at,
            status=GatheringStatus.OPEN,
            created_by_account_id=actor_account_id,
            created_at=self._clock(),
            check_in_code=self._codes.generate(),  # self-check-in dispo dès l'ouverture (M6-1)
        )
        await self._gatherings.add(gathering)
        return GatheringDTO(
            id=gathering.id,
            tenant_id=gathering.tenant_id,
            group_id=gathering.group_id,
            type=gathering.type.value,
            title=gathering.title,
            scheduled_at=gathering.scheduled_at,
            status=gathering.status.value,
            check_in_code=gathering.check_in_code,
        )
