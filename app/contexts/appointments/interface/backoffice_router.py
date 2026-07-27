"""Routes **backoffice** du module Rendez-vous — la secrétaire garde l'agenda du pasteur (PWA).

Voir l'agenda vivant (demandes + confirmés), confirmer un créneau, décliner avec un mot, marquer
honoré. Cookie de session backoffice ; autorité `MANAGE_APPOINTMENTS` (vérifiée dans les use cases).
"""

from uuid import UUID

from fastapi import APIRouter

from app.contexts.appointments.interface.dependencies import (
    AddAvailabilityRuleDep,
    CloseAppointmentDep,
    CompleteAppointmentDep,
    ConfirmAppointmentDep,
    DeactivateAvailabilityRuleDep,
    DeclineAppointmentDep,
    ListMyPendingRequestsDep,
    ListTenantAgendaDep,
    OpenAppointmentDep,
)
from app.contexts.appointments.interface.schemas import (
    AgendaView,
    AppointmentListView,
    AppointmentView,
    AvailabilityRuleBody,
    AvailabilityRuleView,
    ConfirmAppointmentBody,
    DeclineAppointmentBody,
    OpenAppointmentBody,
)
from app.contexts.auth.interface.backoffice_dependencies import CurrentBackofficeUser

router = APIRouter()


@router.get(
    "/tenants/{tenant_id}",
    response_model=AgendaView,
    summary="L'agenda : les créneaux confirmés à organiser — jamais les demandes en attente",
)
async def agenda(
    tenant_id: UUID,
    user: CurrentBackofficeUser,
    query: ListTenantAgendaDep,
) -> AgendaView:
    """Le secrétariat organise des créneaux. Il ne voit ni les demandes en attente, ni leur
    motif : c'est ce qui permet de demander sans que « on sait qu'il a demandé » circule."""
    dtos = await query.execute(actor_account_id=user.account_id, tenant_id=tenant_id)
    return AgendaView.from_dtos(dtos)


@router.get(
    "/tenants/{tenant_id}/requests",
    response_model=AppointmentListView,
    summary="Les demandes qui me sont adressées — ma file, avec leur motif",
)
async def my_requests(
    tenant_id: UUID,
    user: CurrentBackofficeUser,
    query: ListMyPendingRequestsDep,
) -> AppointmentListView:
    """Aucune permission d'église n'ouvre cet écran : c'est le **routage** qui décide. Un admin
    ne voit pas les demandes des autres du seul fait qu'il est admin."""
    dtos = await query.execute(actor_account_id=user.account_id, tenant_id=tenant_id)
    return AppointmentListView.from_dtos(dtos)


@router.post(
    "/tenants/{tenant_id}/open",
    response_model=AppointmentView,
    status_code=201,
    summary="Ouvrir un rendez-vous au bureau (pour un membre, ou un walk-in nom+tél)",
)
async def open_appointment(
    tenant_id: UUID,
    payload: OpenAppointmentBody,
    user: CurrentBackofficeUser,
    command: OpenAppointmentDep,
) -> AppointmentView:
    dto = await command.execute(
        actor_account_id=user.account_id,
        tenant_id=tenant_id,
        subject=payload.subject,
        category=payload.category,
        requester_account_id=payload.requester_account_id,
        requester_name=payload.requester_name,
        requester_phone=payload.requester_phone,
        with_pastor_account_id=payload.with_pastor_account_id,
        scheduled_at=payload.scheduled_at,
        preferred_at=payload.preferred_at,
        note=payload.note,
    )
    return AppointmentView.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}/availability",
    response_model=AvailabilityRuleView,
    status_code=201,
    summary="Poser une disponibilité récurrente pour un pasteur (jour + fenêtre + durée)",
)
async def add_availability(
    tenant_id: UUID,
    payload: AvailabilityRuleBody,
    user: CurrentBackofficeUser,
    command: AddAvailabilityRuleDep,
) -> AvailabilityRuleView:
    dto = await command.execute(
        actor_account_id=user.account_id,
        tenant_id=tenant_id,
        pastor_account_id=payload.pastor_account_id,
        weekday=payload.weekday,
        start_minute=payload.start_minute,
        end_minute=payload.end_minute,
        slot_minutes=payload.slot_minutes,
    )
    return AvailabilityRuleView.from_dto(dto)


@router.post(
    "/availability/{rule_id}/deactivate",
    status_code=204,
    summary="Retirer une disponibilité récurrente",
)
async def deactivate_availability(
    rule_id: UUID,
    user: CurrentBackofficeUser,
    command: DeactivateAvailabilityRuleDep,
) -> None:
    await command.execute(actor_account_id=user.account_id, rule_id=rule_id)


@router.post(
    "/{appointment_id}/confirm",
    response_model=AppointmentView,
    summary="Confirmer (ou déplacer) le créneau d'un rendez-vous",
)
async def confirm(
    appointment_id: UUID,
    payload: ConfirmAppointmentBody,
    user: CurrentBackofficeUser,
    command: ConfirmAppointmentDep,
) -> AppointmentView:
    dto = await command.execute(
        actor_account_id=user.account_id,
        appointment_id=appointment_id,
        scheduled_at=payload.scheduled_at,
    )
    return AppointmentView.from_dto(dto)


@router.post(
    "/{appointment_id}/decline",
    response_model=AppointmentView,
    summary="Décliner une demande — toujours avec un mot doux",
)
async def decline(
    appointment_id: UUID,
    payload: DeclineAppointmentBody,
    user: CurrentBackofficeUser,
    command: DeclineAppointmentDep,
) -> AppointmentView:
    dto = await command.execute(
        actor_account_id=user.account_id,
        appointment_id=appointment_id,
        reason=payload.reason,
    )
    return AppointmentView.from_dto(dto)


@router.post(
    "/{appointment_id}/complete",
    response_model=AppointmentView,
    summary="Marquer un rendez-vous honoré (il a eu lieu)",
)
async def complete(
    appointment_id: UUID,
    user: CurrentBackofficeUser,
    command: CompleteAppointmentDep,
) -> AppointmentView:
    dto = await command.execute(
        actor_account_id=user.account_id, appointment_id=appointment_id
    )
    return AppointmentView.from_dto(dto)


@router.post(
    "/{appointment_id}/close",
    response_model=AppointmentView,
    summary="Fermer un rendez-vous qui ne se fera pas (sans jugement)",
)
async def close(
    appointment_id: UUID,
    user: CurrentBackofficeUser,
    command: CloseAppointmentDep,
) -> AppointmentView:
    dto = await command.execute(
        actor_account_id=user.account_id, appointment_id=appointment_id
    )
    return AppointmentView.from_dto(dto)
