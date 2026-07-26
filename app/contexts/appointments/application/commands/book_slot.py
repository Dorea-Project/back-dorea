"""Use case `BookSlot` — le membre **réserve** un créneau ouvert (self-service).

Le RDV naît **confirmé** sur le pasteur du créneau (« premier dispo » → pasteur déduit). On
revalide côté serveur que le créneau est bien ouvert (règle + futur + non pris) : anti double
réservation et anti-triche. La secrétaire, elle, place via `OpenAppointment` (avec pasteur).
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

from app.contexts.appointments.application.dtos import AppointmentDTO
from app.contexts.appointments.application.mapping import to_appointment_dto
from app.contexts.appointments.application.slots_service import open_slots_from
from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.enums import AppointmentCategory
from app.contexts.appointments.domain.errors import (
    RequesterNotMemberError,
    SlotNotAvailableError,
)
from app.contexts.appointments.domain.repositories import (
    AppointmentRepository,
    AvailabilityRuleRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository


class BookSlot:
    def __init__(
        self,
        rules: AvailabilityRuleRepository,
        appointments: AppointmentRepository,
        memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._rules = rules
        self._appointments = appointments
        self._memberships = memberships
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        with_pastor_account_id: UUID,
        starts_at: datetime,
        subject: str,
        category: AppointmentCategory = AppointmentCategory.OTHER,
        note: str | None = None,
    ) -> AppointmentDTO:
        if await self._memberships.get_active(actor_account_id, tenant_id) is None:
            raise RequesterNotMemberError(
                "Rejoignez d'abord cette église pour réserver un rendez-vous.",
                details={"tenant_id": str(tenant_id)},
            )
        await self._ensure_slot_is_open(tenant_id, with_pastor_account_id, starts_at)

        appointment = Appointment.book(
            id=uuid4(),
            tenant_id=tenant_id,
            requester_account_id=actor_account_id,
            with_pastor_account_id=with_pastor_account_id,
            subject=subject,
            category=category,
            scheduled_at=starts_at,
            now=self._clock(),
            booked_by_account_id=actor_account_id,
            note=note,
        )
        await self._appointments.add(appointment)
        return to_appointment_dto(appointment)

    async def _ensure_slot_is_open(
        self, tenant_id: UUID, pastor_account_id: UUID, starts_at: datetime
    ) -> None:
        day = starts_at.date()
        rules = await self._rules.list_active_by_pastor(pastor_account_id, tenant_id)
        booked = await self._appointments.list_confirmed_between(
            tenant_id,
            datetime.combine(day, time.min, tzinfo=UTC),
            datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC),
        )
        candidates = open_slots_from(
            rules, booked, from_date=day, to_date=day, now=self._clock()
        )
        if not any(s.starts_at == starts_at for s in candidates):
            raise SlotNotAvailableError(
                "Ce créneau n'est plus disponible.",
                details={"pastor_account_id": str(pastor_account_id), "starts_at": str(starts_at)},
            )
