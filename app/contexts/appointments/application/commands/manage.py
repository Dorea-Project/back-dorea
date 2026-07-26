"""Use cases **de la secrétaire** (backoffice) — garder l'agenda du pasteur.

Confirmer un créneau, décliner avec un mot, marquer honoré. L'autorité est **église-entière** :
`MANAGE_APPOINTMENTS` (Secrétaire / Admin / Owner) — la secrétaire est les mains du pasteur.
L'appartenance du rendez-vous à l'église (`tenant_id`) est déduite de l'agrégat lui-même.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.contexts.appointments.application.dtos import AppointmentDTO
from app.contexts.appointments.application.mapping import to_appointment_dto
from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.enums import AppointmentCategory
from app.contexts.appointments.domain.errors import AppointmentNotFoundError
from app.contexts.appointments.domain.repositories import AppointmentRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission
from app.contexts.notifications.application.notifier import (
    NotificationScheduler,
    Notifier,
    PushNotification,
)

# Combien de temps avant le rendez-vous on rappelle le demandeur.
REMINDER_LEAD = timedelta(hours=1)


async def _notify(
    notifier: Notifier | None, appointment: Appointment, *, title: str, body: str
) -> None:
    """Prévient le demandeur (best-effort) — jamais un walk-in (sans compte), jamais bloquant."""
    if notifier is None or appointment.requester_account_id is None:
        return
    await notifier.notify(
        [appointment.requester_account_id],
        PushNotification(title=title, body=body, data={"type": "appointment",
                                                       "id": str(appointment.id)}),
    )


async def _ensure_keeper(access: GroupAccessPolicy, *, actor_account_id: UUID, tenant_id: UUID):
    await access.ensure_church_wide(
        actor_account_id=actor_account_id,
        tenant_id=tenant_id,
        permission=Permission.MANAGE_APPOINTMENTS,
    )


async def _load_for_keeper(
    appointments: AppointmentRepository,
    access: GroupAccessPolicy,
    *,
    actor_account_id: UUID,
    appointment_id: UUID,
) -> Appointment:
    appointment = await appointments.get(appointment_id)
    if appointment is None:
        raise AppointmentNotFoundError(
            "Rendez-vous introuvable.", details={"appointment_id": str(appointment_id)}
        )
    await access.ensure_church_wide(
        actor_account_id=actor_account_id,
        tenant_id=appointment.tenant_id,
        permission=Permission.MANAGE_APPOINTMENTS,
    )
    return appointment


class OpenAppointment:
    """La secrétaire **ouvre** un rendez-vous au bureau — pour un membre ou un walk-in.

    Émettre au nom d'autrui est un acte gardien (`MANAGE_APPOINTMENTS`) : c'est le pendant, côté
    bureau, de la demande mobile du membre. Un créneau fourni → le RDV naît confirmé."""

    def __init__(
        self, appointments: AppointmentRepository, access: GroupAccessPolicy, *, clock
    ) -> None:
        self._appointments = appointments
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        subject: str,
        category: AppointmentCategory = AppointmentCategory.OTHER,
        requester_account_id: UUID | None = None,
        requester_name: str | None = None,
        requester_phone: str | None = None,
        with_pastor_account_id: UUID | None = None,
        scheduled_at: datetime | None = None,
        preferred_at: datetime | None = None,
        note: str | None = None,
    ) -> AppointmentDTO:
        await _ensure_keeper(
            self._access, actor_account_id=actor_account_id, tenant_id=tenant_id
        )
        appointment = Appointment.open_at_office(
            id=uuid4(),
            tenant_id=tenant_id,
            opened_by_account_id=actor_account_id,
            subject=subject,
            category=category,
            now=self._clock(),
            requester_account_id=requester_account_id,
            requester_name=requester_name,
            requester_phone=requester_phone,
            with_pastor_account_id=with_pastor_account_id,
            scheduled_at=scheduled_at,
            preferred_at=preferred_at,
            note=note,
        )
        await self._appointments.add(appointment)
        return to_appointment_dto(appointment)


class ConfirmAppointment:
    def __init__(
        self,
        appointments: AppointmentRepository,
        access: GroupAccessPolicy,
        notifier: Notifier | None = None,
        scheduler: NotificationScheduler | None = None,
        *,
        clock,
    ) -> None:
        self._appointments = appointments
        self._access = access
        self._notifier = notifier
        self._scheduler = scheduler
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, appointment_id: UUID, scheduled_at: datetime
    ) -> AppointmentDTO:
        appointment = await _load_for_keeper(
            self._appointments, self._access,
            actor_account_id=actor_account_id, appointment_id=appointment_id,
        )
        appointment.confirm(at=scheduled_at, by_account_id=actor_account_id, now=self._clock())
        await self._appointments.save(appointment)
        await _notify(
            self._notifier, appointment,
            title="Rendez-vous confirmé", body="Votre rendez-vous a été confirmé.",
        )
        await self._schedule_reminder(appointment)
        return to_appointment_dto(appointment)

    async def _schedule_reminder(self, appointment: Appointment) -> None:
        """Planifie un rappel au demandeur avant l'heure (best-effort, jamais un walk-in)."""
        if (
            self._scheduler is None
            or appointment.requester_account_id is None
            or appointment.scheduled_at is None
        ):
            return
        await self._scheduler.schedule(
            [appointment.requester_account_id],
            PushNotification(
                title="Rappel de rendez-vous",
                body="Votre rendez-vous approche.",
                data={"type": "appointment", "id": str(appointment.id)},
            ),
            at=appointment.scheduled_at - REMINDER_LEAD,
        )


class DeclineAppointment:
    def __init__(
        self,
        appointments: AppointmentRepository,
        access: GroupAccessPolicy,
        notifier: Notifier | None = None,
        *,
        clock,
    ) -> None:
        self._appointments = appointments
        self._access = access
        self._notifier = notifier
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, appointment_id: UUID, reason: str | None = None
    ) -> AppointmentDTO:
        appointment = await _load_for_keeper(
            self._appointments, self._access,
            actor_account_id=actor_account_id, appointment_id=appointment_id,
        )
        appointment.decline(by_account_id=actor_account_id, reason=reason, now=self._clock())
        await self._appointments.save(appointment)
        await _notify(
            self._notifier, appointment,
            title="Rendez-vous",
            body=appointment.decision_note or "Votre demande n'a pas été retenue.",
        )
        return to_appointment_dto(appointment)


class CompleteAppointment:
    def __init__(
        self, appointments: AppointmentRepository, access: GroupAccessPolicy, *, clock
    ) -> None:
        self._appointments = appointments
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, appointment_id: UUID
    ) -> AppointmentDTO:
        appointment = await _load_for_keeper(
            self._appointments, self._access,
            actor_account_id=actor_account_id, appointment_id=appointment_id,
        )
        appointment.complete(by_account_id=actor_account_id, now=self._clock())
        await self._appointments.save(appointment)
        return to_appointment_dto(appointment)


class CloseAppointment:
    """Le gardien **ferme** un rendez-vous qui ne se fera pas — sans jugement (comme annuler)."""

    def __init__(
        self, appointments: AppointmentRepository, access: GroupAccessPolicy, *, clock
    ) -> None:
        self._appointments = appointments
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, appointment_id: UUID
    ) -> AppointmentDTO:
        appointment = await _load_for_keeper(
            self._appointments, self._access,
            actor_account_id=actor_account_id, appointment_id=appointment_id,
        )
        appointment.cancel(now=self._clock())
        await self._appointments.save(appointment)
        return to_appointment_dto(appointment)
