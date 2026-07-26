"""Routes **mobile** du module Rendez-vous — le demandeur (un membre).

Demander à rencontrer le pasteur, voir *ses* demandes et leur statut, annuler. JWT mobile.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.appointments.interface.dependencies import (
    BookSlotDep,
    CancelAppointmentDep,
    ListMyAppointmentsDep,
    ListOpenSlotsDep,
    RequestAppointmentDep,
)
from app.contexts.appointments.interface.schemas import (
    AppointmentListView,
    AppointmentView,
    BookSlotBody,
    RequestAppointmentBody,
    SlotListView,
)
from app.contexts.auth.interface.dependencies import CurrentActor

router = APIRouter()


@router.get(
    "/tenants/{tenant_id}/open-slots",
    response_model=SlotListView,
    summary="Les créneaux disponibles (tous pasteurs) entre deux dates — pour se réserver",
)
async def open_slots(
    tenant_id: UUID,
    from_date: date,
    to_date: date,
    actor: CurrentActor,
    query: ListOpenSlotsDep,
    pastor_account_id: UUID | None = None,
) -> SlotListView:
    dtos = await query.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        pastor_account_id=pastor_account_id,
    )
    return SlotListView.from_dtos(dtos)


@router.post(
    "/tenants/{tenant_id}/book",
    response_model=AppointmentView,
    status_code=status.HTTP_201_CREATED,
    summary="Réserver un créneau ouvert → rendez-vous confirmé (pasteur déduit du créneau)",
)
async def book_slot(
    tenant_id: UUID,
    payload: BookSlotBody,
    actor: CurrentActor,
    command: BookSlotDep,
) -> AppointmentView:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        with_pastor_account_id=payload.with_pastor_account_id,
        starts_at=payload.starts_at,
        subject=payload.subject,
        category=payload.category,
        note=payload.note,
    )
    return AppointmentView.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}",
    response_model=AppointmentView,
    status_code=status.HTTP_201_CREATED,
    summary="Demander un rendez-vous avec le pasteur (sujet confidentiel, créneau souhaité)",
)
async def request_appointment(
    tenant_id: UUID,
    payload: RequestAppointmentBody,
    actor: CurrentActor,
    command: RequestAppointmentDep,
) -> AppointmentView:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        subject=payload.subject,
        preferred_at=payload.preferred_at,
        note=payload.note,
    )
    return AppointmentView.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/mine",
    response_model=AppointmentListView,
    summary="Mes demandes de rendez-vous et leur statut",
)
async def my_appointments(
    tenant_id: UUID,
    actor: CurrentActor,
    query: ListMyAppointmentsDep,
) -> AppointmentListView:
    dtos = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return AppointmentListView.from_dtos(dtos)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentView,
    summary="Annuler ma demande (le demandeur seul)",
)
async def cancel_appointment(
    appointment_id: UUID,
    actor: CurrentActor,
    command: CancelAppointmentDep,
) -> AppointmentView:
    dto = await command.execute(actor_account_id=actor.account_id, appointment_id=appointment_id)
    return AppointmentView.from_dto(dto)
