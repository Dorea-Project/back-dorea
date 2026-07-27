"""Use cases **du demandeur** (mobile) — demander un rendez-vous, l'annuler.

`RequestAppointment` — un **membre actif** demande à rencontrer le pasteur (sujet confidentiel,
créneau souhaité optionnel). `CancelAppointment` — le demandeur se rétracte (lui seul).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.appointments.application.dtos import AppointmentDTO
from app.contexts.appointments.application.mapping import to_appointment_dto
from app.contexts.appointments.application.relay import RouteAppointment
from app.contexts.appointments.application.watch_facts import EmitAppointmentFacts
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
        facts: EmitAppointmentFacts | None = None,
        routing: RouteAppointment | None = None,
        *,
        clock,
    ) -> None:
        self._appointments = appointments
        self._memberships = memberships
        self._facts = facts
        self._routing = routing
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
        # Adresser tout de suite, à quelqu'un de **disponible** : une absence déclarée est
        # connue d'avance, donc contournée sans faire attendre le délai de relais.
        if self._routing is not None:
            await self._routing.initial(appointment, at=appointment.created_at)
        await self._appointments.add(appointment)
        # Le fait entre **ici**, au geste — pas à la confirmation du créneau. Sinon on perd
        # l'antériorité, qui est toute la valeur du canal.
        if self._facts is not None:
            await self._facts.execute(appointment)
        return to_appointment_dto(appointment)


class CancelAppointment:
    def __init__(
        self,
        appointments: AppointmentRepository,
        facts: EmitAppointmentFacts | None = None,
        *,
        clock,
    ) -> None:
        self._appointments = appointments
        self._facts = facts
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
        appointment.cancel(now=self._clock(), by_account_id=actor_account_id)
        await self._appointments.save(appointment)
        # Il a demandé, puis a reculé : le signal le plus urgent que le moteur sache produire.
        if self._facts is not None:
            await self._facts.execute(appointment)
        return to_appointment_dto(appointment)
