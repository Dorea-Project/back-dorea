"""Requêtes du module Rendez-vous — et le **cloisonnement** qui rend le canal privé.

Trois audiences, trois requêtes, trois types de sortie. Ce n'est pas de la prudence : c'est ce
qui permet à un membre de demander sans que *« on sait qu'il a demandé »* circule dans l'église.
Le coût social est exactement ce que le canal venait de supprimer ; le faire revenir par la
porte administrative annulerait tout le bénéfice.

| Qui | Ce qu'il voit | Type |
|---|---|---|
| Le demandeur | ses propres demandes, en entier | `AppointmentDTO` |
| Le destinataire de la demande | **ses** demandes en attente, avec le motif | `AppointmentDTO` |
| Le secrétariat | les créneaux **confirmés** à organiser | `AgendaEntryDTO` |

Une demande déclinée ou réorientée n'entre **jamais** dans l'agenda.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.appointments.application.dtos import AgendaEntryDTO, AppointmentDTO
from app.contexts.appointments.application.mapping import (
    to_agenda_entry_dto,
    to_appointment_dto,
)
from app.contexts.appointments.domain.enums import AppointmentStatus
from app.contexts.appointments.domain.repositories import AppointmentRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission


class ListMyAppointments:
    """Le demandeur voit les siennes, en entier — c'est lui qui les a écrites."""

    def __init__(self, appointments: AppointmentRepository) -> None:
        self._appointments = appointments

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> list[AppointmentDTO]:
        mine = await self._appointments.list_by_requester(actor_account_id, tenant_id)
        mine.sort(key=lambda a: a.created_at, reverse=True)
        return [to_appointment_dto(a) for a in mine]


class ListMyPendingRequests:
    """Les demandes **adressées à moi**, avec leur motif. Ma file, personne d'autre.

    Aucune permission d'église n'ouvre cet écran : c'est le **routage** qui décide. Un admin ne
    voit pas les demandes des autres du seul fait qu'il est admin — sinon le cloisonnement ne
    serait qu'une convention."""

    def __init__(self, appointments: AppointmentRepository) -> None:
        self._appointments = appointments

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> list[AppointmentDTO]:
        rows = await self._appointments.list_open_for_tenant(tenant_id)
        mine = [
            a
            for a in rows
            if a.is_awaiting_answer and a.routed_to_account_id == actor_account_id
        ]
        mine.sort(key=lambda a: a.routed_at or a.created_at)  # la plus ancienne d'abord
        return [to_appointment_dto(a) for a in mine]


class ListTenantAgenda:
    """L'agenda du secrétariat : **les créneaux confirmés, et rien d'autre.**

    Ni les demandes en attente, ni les motifs, ni ce qui a été décliné ou réorienté. Le type de
    sortie ne porte pas ces champs — un oubli de filtrage ne peut donc pas les faire fuir."""

    def __init__(
        self, appointments: AppointmentRepository, access: GroupAccessPolicy
    ) -> None:
        self._appointments = appointments
        self._access = access

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> list[AgendaEntryDTO]:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.MANAGE_APPOINTMENTS,
        )
        rows = await self._appointments.list_open_for_tenant(tenant_id)
        agenda = [
            a
            for a in rows
            if a.status is AppointmentStatus.CONFIRMED and a.scheduled_at is not None
        ]
        agenda.sort(key=lambda a: a.scheduled_at)
        return [to_agenda_entry_dto(a) for a in agenda]
