"""Injection de dépendances du module Rendez-vous."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.api.deps import DbSession
from app.contexts.appointments.application.commands.availability import (
    AddAvailabilityRule,
    DeactivateAvailabilityRule,
)
from app.contexts.appointments.application.commands.book_slot import BookSlot
from app.contexts.appointments.application.commands.manage import (
    CloseAppointment,
    CompleteAppointment,
    ConfirmAppointment,
    DeclineAppointment,
    OpenAppointment,
)
from app.contexts.appointments.application.commands.request import (
    CancelAppointment,
    RequestAppointment,
)
from app.contexts.appointments.application.queries.list_appointments import (
    ListMyAppointments,
    ListTenantAgenda,
)
from app.contexts.appointments.application.queries.open_slots import ListOpenSlots
from app.contexts.appointments.infrastructure.persistence.repository import (
    SqlAppointmentRepository,
    SqlAvailabilityRuleRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.infrastructure.persistence.repositories import (
    SqlAlchemyMembershipRepository,
)
from app.contexts.notifications.interface.dependencies import build_notifier, build_scheduler
from app.contexts.tenant.infrastructure.persistence.ownership_repo import SqlOwnershipRepository


def _now() -> datetime:
    return datetime.now(UTC)


def _access(session) -> GroupAccessPolicy:
    return GroupAccessPolicy(
        SqlOwnershipRepository(session), SqlAlchemyMembershipRepository(session)
    )


# --- demandeur (mobile) ---


def get_request_command(session: DbSession) -> RequestAppointment:
    return RequestAppointment(
        SqlAppointmentRepository(session), SqlAlchemyMembershipRepository(session), clock=_now
    )


def get_cancel_command(session: DbSession) -> CancelAppointment:
    return CancelAppointment(SqlAppointmentRepository(session), clock=_now)


def get_my_appointments_query(session: DbSession) -> ListMyAppointments:
    return ListMyAppointments(SqlAppointmentRepository(session))


# --- gardien de l'agenda (backoffice) ---


def get_open_command(session: DbSession) -> OpenAppointment:
    return OpenAppointment(SqlAppointmentRepository(session), _access(session), clock=_now)


def get_close_command(session: DbSession) -> CloseAppointment:
    return CloseAppointment(SqlAppointmentRepository(session), _access(session), clock=_now)


def get_confirm_command(session: DbSession) -> ConfirmAppointment:
    return ConfirmAppointment(
        SqlAppointmentRepository(session),
        _access(session),
        build_notifier(session),
        build_scheduler(session),
        clock=_now,
    )


def get_decline_command(session: DbSession) -> DeclineAppointment:
    return DeclineAppointment(
        SqlAppointmentRepository(session), _access(session), build_notifier(session), clock=_now
    )


def get_complete_command(session: DbSession) -> CompleteAppointment:
    return CompleteAppointment(SqlAppointmentRepository(session), _access(session), clock=_now)


def get_agenda_query(session: DbSession) -> ListTenantAgenda:
    return ListTenantAgenda(SqlAppointmentRepository(session), _access(session))


# --- disponibilités (récurrence) + réservation de créneaux ---


def get_add_rule_command(session: DbSession) -> AddAvailabilityRule:
    return AddAvailabilityRule(
        SqlAvailabilityRuleRepository(session),
        SqlAlchemyMembershipRepository(session),
        _access(session),
        clock=_now,
    )


def get_deactivate_rule_command(session: DbSession) -> DeactivateAvailabilityRule:
    return DeactivateAvailabilityRule(SqlAvailabilityRuleRepository(session), _access(session))


def get_open_slots_query(session: DbSession) -> ListOpenSlots:
    return ListOpenSlots(
        SqlAvailabilityRuleRepository(session),
        SqlAppointmentRepository(session),
        SqlAlchemyMembershipRepository(session),
        clock=_now,
    )


def get_book_slot_command(session: DbSession) -> BookSlot:
    return BookSlot(
        SqlAvailabilityRuleRepository(session),
        SqlAppointmentRepository(session),
        SqlAlchemyMembershipRepository(session),
        clock=_now,
    )


RequestAppointmentDep = Annotated[RequestAppointment, Depends(get_request_command)]
CancelAppointmentDep = Annotated[CancelAppointment, Depends(get_cancel_command)]
ListMyAppointmentsDep = Annotated[ListMyAppointments, Depends(get_my_appointments_query)]
OpenAppointmentDep = Annotated[OpenAppointment, Depends(get_open_command)]
CloseAppointmentDep = Annotated[CloseAppointment, Depends(get_close_command)]
ConfirmAppointmentDep = Annotated[ConfirmAppointment, Depends(get_confirm_command)]
DeclineAppointmentDep = Annotated[DeclineAppointment, Depends(get_decline_command)]
CompleteAppointmentDep = Annotated[CompleteAppointment, Depends(get_complete_command)]
ListTenantAgendaDep = Annotated[ListTenantAgenda, Depends(get_agenda_query)]
AddAvailabilityRuleDep = Annotated[AddAvailabilityRule, Depends(get_add_rule_command)]
DeactivateAvailabilityRuleDep = Annotated[
    DeactivateAvailabilityRule, Depends(get_deactivate_rule_command)
]
ListOpenSlotsDep = Annotated[ListOpenSlots, Depends(get_open_slots_query)]
BookSlotDep = Annotated[BookSlot, Depends(get_book_slot_command)]
