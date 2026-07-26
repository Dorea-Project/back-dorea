"""Use cases M6-3 : `AddVisitor` / `RemoveVisitor` — capturer un visage nouveau.

Autorisation `RECORD_ATTENDANCE` (comme le pointage), rencontre **ouverte**. Le visiteur est
hors roster (pas membre) — la conversion en membre viendra plus tard (entonnoir).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.attendance.application.authz import authorize_on_gathering, load_gathering
from app.contexts.attendance.application.dtos import VisitorDTO
from app.contexts.attendance.domain.errors import GatheringClosedError, VisitorNotFoundError
from app.contexts.attendance.domain.repositories import GatheringRepository, VisitorRepository
from app.contexts.attendance.domain.visitor import Visitor
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.repositories import GroupRepository


class AddVisitor:
    def __init__(
        self,
        gatherings: GatheringRepository,
        visitors: VisitorRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._gatherings = gatherings
        self._visitors = visitors
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, gathering_id: UUID, name: str, phone: str | None = None
    ) -> VisitorDTO:
        gathering = await load_gathering(self._gatherings, gathering_id)
        if not gathering.is_open:
            raise GatheringClosedError(
                "Cette rencontre est clôturée.", details={"gathering_id": str(gathering_id)}
            )
        await authorize_on_gathering(
            gathering=gathering, groups=self._groups, access=self._access,
            actor_account_id=actor_account_id,
        )
        visitor = Visitor(
            id=uuid4(),
            gathering_id=gathering_id,
            tenant_id=gathering.tenant_id,
            name=name,
            phone=phone,
            captured_by_account_id=actor_account_id,
            captured_at=self._clock(),
        )
        await self._visitors.add(visitor)
        return VisitorDTO(
            id=visitor.id, gathering_id=gathering_id, name=visitor.name, phone=visitor.phone
        )


class RemoveVisitor:
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
        self, *, actor_account_id: UUID, gathering_id: UUID, visitor_id: UUID
    ) -> None:
        gathering = await load_gathering(self._gatherings, gathering_id)
        await authorize_on_gathering(
            gathering=gathering, groups=self._groups, access=self._access,
            actor_account_id=actor_account_id,
        )
        visitor = await self._visitors.get(visitor_id)
        if visitor is None or visitor.gathering_id != gathering_id:
            raise VisitorNotFoundError(
                "Visiteur introuvable sur cette rencontre.",
                details={"visitor_id": str(visitor_id)},
            )
        await self._visitors.remove(visitor_id)
