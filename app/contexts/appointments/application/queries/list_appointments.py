"""Requêtes du module Rendez-vous — mes rendez-vous (demandeur), l'agenda (secrétaire).

`ListMyAppointments` — privé au demandeur. `ListTenantAgenda` — réservé aux gardiens de l'agenda
(`MANAGE_APPOINTMENTS` église-entière) : l'agenda vivant (en attente + confirmés), le sujet
confidentiel n'étant servi qu'à eux.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.appointments.application.dtos import AppointmentDTO
from app.contexts.appointments.application.mapping import to_appointment_dto
from app.contexts.appointments.domain.repositories import AppointmentRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission


class ListMyAppointments:
    def __init__(self, appointments: AppointmentRepository) -> None:
        self._appointments = appointments

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> list[AppointmentDTO]:
        mine = await self._appointments.list_by_requester(actor_account_id, tenant_id)
        mine.sort(key=lambda a: a.created_at, reverse=True)
        return [to_appointment_dto(a) for a in mine]


class ListTenantAgenda:
    def __init__(
        self, appointments: AppointmentRepository, access: GroupAccessPolicy
    ) -> None:
        self._appointments = appointments
        self._access = access

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> list[AppointmentDTO]:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.MANAGE_APPOINTMENTS,
        )
        agenda = await self._appointments.list_open_for_tenant(tenant_id)
        # En attente d'abord (à traiter), puis les confirmés par créneau.
        agenda.sort(key=lambda a: (a.scheduled_at is not None, a.scheduled_at or a.created_at))
        return [to_appointment_dto(a) for a in agenda]
