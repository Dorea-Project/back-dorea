"""Use cases M6-2 : `DeclareAbsence` / `CancelAbsence` — la dignité de prévenir.

Le membre annonce **sa propre** absence (période + tag), tenant-large. Prérequis : être
membre actif de l'église. On n'annule que **sa** déclaration.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.attendance.application.dtos import PlannedAbsenceDTO
from app.contexts.attendance.domain.enums import AbsenceReason
from app.contexts.attendance.domain.errors import (
    InvalidAbsencePeriodError,
    NotAChurchMemberError,
    PlannedAbsenceNotFoundError,
)
from app.contexts.attendance.domain.gravity import gravity_of
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.attendance.domain.repositories import PlannedAbsenceRepository
from app.contexts.iam.domain.repositories import MembershipRepository


def _to_dto(a: PlannedAbsence) -> PlannedAbsenceDTO:
    return PlannedAbsenceDTO(
        id=a.id,
        account_id=a.account_id,
        tenant_id=a.tenant_id,
        reason=a.reason.value,
        gravity=gravity_of(a.reason).value,
        note=a.note,
        from_date=a.from_date,
        to_date=a.to_date,
    )


class DeclareAbsence:
    def __init__(
        self,
        absences: PlannedAbsenceRepository,
        church_memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._absences = absences
        self._church_memberships = church_memberships
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        reason: AbsenceReason,
        from_date: datetime,
        to_date: datetime,
        note: str | None = None,
    ) -> PlannedAbsenceDTO:
        if to_date < from_date:
            raise InvalidAbsencePeriodError(
                "La fin de la période précède le début.",
                details={"from": from_date.isoformat(), "to": to_date.isoformat()},
            )
        if await self._church_memberships.get_active(actor_account_id, tenant_id) is None:
            raise NotAChurchMemberError(
                "Vous devez être membre de cette église.",
                details={"tenant_id": str(tenant_id)},
            )

        absence = PlannedAbsence(
            id=uuid4(),
            account_id=actor_account_id,
            tenant_id=tenant_id,
            reason=reason,
            from_date=from_date,
            to_date=to_date,
            declared_by_account_id=actor_account_id,  # self
            declared_at=self._clock(),
            note=note,
        )
        await self._absences.add(absence)
        return _to_dto(absence)


class CancelAbsence:
    def __init__(self, absences: PlannedAbsenceRepository, *, clock) -> None:
        self._absences = absences
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, absence_id: UUID) -> None:
        absence = await self._absences.get(absence_id)
        if absence is None or absence.account_id != actor_account_id:
            raise PlannedAbsenceNotFoundError(
                "Absence introuvable.", details={"absence_id": str(absence_id)}
            )
        absence.cancel(now=self._clock())
        await self._absences.save(absence)
