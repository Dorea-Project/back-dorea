"""Requête `GetMyPlannedAbsences` — le membre voit ses absences déclarées (M6-2)."""

from __future__ import annotations

from uuid import UUID

from app.contexts.attendance.application.commands.declare_absence import _to_dto
from app.contexts.attendance.application.dtos import PlannedAbsenceDTO
from app.contexts.attendance.domain.repositories import PlannedAbsenceRepository


class GetMyPlannedAbsences:
    def __init__(self, absences: PlannedAbsenceRepository) -> None:
        self._absences = absences

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> list[PlannedAbsenceDTO]:
        rows = await self._absences.list_active_by_account(actor_account_id, tenant_id)
        return [_to_dto(a) for a in rows]
