"""Mappage agrégat → DTO (module Rendez-vous)."""

from __future__ import annotations

from app.contexts.appointments.application.dtos import (
    AppointmentDTO,
    AvailabilityRuleDTO,
    SlotDTO,
)
from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.availability import AvailabilityRule, Slot


def to_appointment_dto(a: Appointment) -> AppointmentDTO:
    return AppointmentDTO(
        id=a.id,
        requester_account_id=a.requester_account_id,
        requester_name=a.requester_name,
        with_pastor_account_id=a.with_pastor_account_id,
        category=a.category.value,
        subject=a.subject,
        preferred_at=a.preferred_at,
        note=a.note,
        status=a.status.value,
        scheduled_at=a.scheduled_at,
        decision_note=a.decision_note,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def to_rule_dto(r: AvailabilityRule) -> AvailabilityRuleDTO:
    return AvailabilityRuleDTO(
        id=r.id,
        pastor_account_id=r.pastor_account_id,
        weekday=r.weekday,
        start_minute=r.start_minute,
        end_minute=r.end_minute,
        slot_minutes=r.slot_minutes,
    )


def to_slot_dto(s: Slot) -> SlotDTO:
    return SlotDTO(
        pastor_account_id=s.pastor_account_id, starts_at=s.starts_at, ends_at=s.ends_at
    )
