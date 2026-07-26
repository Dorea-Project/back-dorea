"""Use cases **du demandeur** (mobile) — demander un rendez-vous, l'annuler.

`RequestAppointment` — un **membre actif** demande à rencontrer le pasteur (sujet confidentiel,
créneau souhaité optionnel). `CancelAppointment` — le demandeur se rétracte (lui seul).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.appointments.application.dtos import AppointmentDTO
from app.contexts.appointments.application.mapping import to_appointment_dto
from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.enums import AppointmentCategory
from app.contexts.appointments.domain.errors import (
    AppointmentNotFoundError,
    NotAppointmentRequesterError,
    RequesterNotMemberError,
)
from app.contexts.appointments.domain.repositories import AppointmentRepository
from app.contexts.iam.domain.repositories import MembershipRepository


class RequestAppointment:
    def __init__(
        self,
        appointments: AppointmentRepository,
        memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._appointments = appointments
        self._memberships = memberships
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        subject: str,
        category: AppointmentCategory = AppointmentCategory.OTHER,
        preferred_at: datetime | None = None,
        note: str | None = None,
    ) -> AppointmentDTO:
        if await self._memberships.get_active(actor_account_id, tenant_id) is None:
            raise RequesterNotMemberError(
                "Rejoignez d'abord cette église pour solliciter un rendez-vous.",
                details={"tenant_id": str(tenant_id)},
            )
        appointment = Appointment.request(
            id=uuid4(),
            tenant_id=tenant_id,
            requester_account_id=actor_account_id,
            subject=subject,
            category=category,
            now=self._clock(),
            preferred_at=preferred_at,
            note=note,
        )
        await self._appointments.add(appointment)
        return to_appointment_dto(appointment)


class CancelAppointment:
    def __init__(self, appointments: AppointmentRepository, *, clock) -> None:
        self._appointments = appointments
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, appointment_id: UUID
    ) -> AppointmentDTO:
        appointment = await self._appointments.get(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(
                "Rendez-vous introuvable.", details={"appointment_id": str(appointment_id)}
            )
        if appointment.requester_account_id != actor_account_id:
            raise NotAppointmentRequesterError(
                "Seul le demandeur peut annuler sa demande.",
                details={"appointment_id": str(appointment_id)},
            )
        appointment.cancel(now=self._clock())
        await self._appointments.save(appointment)
        return to_appointment_dto(appointment)
