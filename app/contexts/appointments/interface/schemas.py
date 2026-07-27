"""Schémas HTTP du module Rendez-vous."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.appointments.application.dtos import (
    AgendaEntryDTO,
    AppointmentDTO,
    AvailabilityRuleDTO,
    SlotDTO,
)
from app.contexts.appointments.domain.enums import AppointmentCategory


class RequestAppointmentBody(BaseModel):
    subject: str = Field(examples=["J'aimerais un temps de prière et de conseil"])
    category: AppointmentCategory = Field(default=AppointmentCategory.OTHER)
    preferred_at: datetime | None = Field(default=None, description="Créneau souhaité (optionnel)")
    note: str | None = Field(default=None, description="Contexte utile pour la secrétaire")


class OpenAppointmentBody(BaseModel):
    """La secrétaire ouvre un RDV au bureau : pour un membre (compte) ou un walk-in (nom)."""

    subject: str = Field(examples=["Préparation de mariage"])
    category: AppointmentCategory = Field(default=AppointmentCategory.OTHER)
    requester_account_id: UUID | None = Field(default=None, description="Si c'est un membre")
    requester_name: str | None = Field(default=None, description="Si walk-in (sans compte)")
    requester_phone: str | None = Field(default=None)
    with_pastor_account_id: UUID | None = Field(default=None, description="Le pasteur du RDV")
    scheduled_at: datetime | None = Field(
        default=None, description="Poser un créneau tout de suite → RDV confirmé"
    )
    preferred_at: datetime | None = Field(default=None)
    note: str | None = Field(default=None)


class AvailabilityRuleBody(BaseModel):
    """Une disponibilité récurrente. Heures en minutes depuis minuit, UTC (ex. 14h00 = 840)."""

    pastor_account_id: UUID
    weekday: int = Field(ge=0, le=6, description="0 = lundi … 6 = dimanche")
    start_minute: int = Field(ge=0, le=1440, examples=[840])
    end_minute: int = Field(ge=0, le=1440, examples=[1020])
    slot_minutes: int = Field(gt=0, examples=[30])


class AvailabilityRuleView(BaseModel):
    id: UUID
    pastor_account_id: UUID
    weekday: int
    start_minute: int
    end_minute: int
    slot_minutes: int

    @classmethod
    def from_dto(cls, d: AvailabilityRuleDTO) -> AvailabilityRuleView:
        return cls(
            id=d.id,
            pastor_account_id=d.pastor_account_id,
            weekday=d.weekday,
            start_minute=d.start_minute,
            end_minute=d.end_minute,
            slot_minutes=d.slot_minutes,
        )


class SlotView(BaseModel):
    pastor_account_id: UUID
    starts_at: datetime
    ends_at: datetime

    @classmethod
    def from_dto(cls, d: SlotDTO) -> SlotView:
        return cls(
            pastor_account_id=d.pastor_account_id, starts_at=d.starts_at, ends_at=d.ends_at
        )


class SlotListView(BaseModel):
    total: int
    slots: list[SlotView]

    @classmethod
    def from_dtos(cls, dtos: list[SlotDTO]) -> SlotListView:
        return cls(total=len(dtos), slots=[SlotView.from_dto(d) for d in dtos])


class BookSlotBody(BaseModel):
    with_pastor_account_id: UUID
    starts_at: datetime = Field(description="Le début du créneau choisi (doit être ouvert)")
    subject: str = Field(examples=["Un temps de prière"])
    category: AppointmentCategory = Field(default=AppointmentCategory.OTHER)
    note: str | None = Field(default=None)


class ConfirmAppointmentBody(BaseModel):
    scheduled_at: datetime = Field(description="Le créneau confirmé du rendez-vous")


class DeclineAppointmentBody(BaseModel):
    reason: str | None = Field(default=None, description="Un mot doux (jamais un rejet froid)")


class AppointmentView(BaseModel):
    id: UUID
    requester_account_id: UUID | None
    requester_name: str | None
    with_pastor_account_id: UUID | None
    category: str
    subject: str
    preferred_at: datetime | None
    note: str | None
    status: str
    scheduled_at: datetime | None
    decision_note: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, d: AppointmentDTO) -> AppointmentView:
        return cls(
            id=d.id,
            requester_account_id=d.requester_account_id,
            requester_name=d.requester_name,
            with_pastor_account_id=d.with_pastor_account_id,
            category=d.category,
            subject=d.subject,
            preferred_at=d.preferred_at,
            note=d.note,
            status=d.status,
            scheduled_at=d.scheduled_at,
            decision_note=d.decision_note,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )


class AgendaEntryView(BaseModel):
    """Un créneau à organiser. **Ni sujet, ni note, ni mot de décision** — ils n'existent pas
    dans ce schéma, donc ils ne peuvent pas fuir par oubli."""

    id: UUID
    requester_account_id: UUID | None
    requester_name: str | None
    with_pastor_account_id: UUID | None
    category: str
    scheduled_at: datetime
    created_at: datetime

    @classmethod
    def from_dto(cls, d: AgendaEntryDTO) -> AgendaEntryView:
        return cls(
            id=d.id,
            requester_account_id=d.requester_account_id,
            requester_name=d.requester_name,
            with_pastor_account_id=d.with_pastor_account_id,
            category=d.category,
            scheduled_at=d.scheduled_at,
            created_at=d.created_at,
        )


class AgendaView(BaseModel):
    total: int
    entries: list[AgendaEntryView]

    @classmethod
    def from_dtos(cls, dtos: list[AgendaEntryDTO]) -> AgendaView:
        return cls(total=len(dtos), entries=[AgendaEntryView.from_dto(d) for d in dtos])


class AppointmentListView(BaseModel):
    total: int
    appointments: list[AppointmentView]

    @classmethod
    def from_dtos(cls, dtos: list[AppointmentDTO]) -> AppointmentListView:
        return cls(
            total=len(dtos),
            appointments=[AppointmentView.from_dto(d) for d in dtos],
        )
