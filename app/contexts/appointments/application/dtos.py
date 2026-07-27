"""DTO applicatifs du module Rendez-vous."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AppointmentDTO:
    """Un rendez-vous — vu par son demandeur, ou par la secrétaire dans l'agenda.

    Le `subject` est confidentiel : ce DTO n'est servi qu'au demandeur et aux gardiens de
    l'agenda (jamais exposé aux autres membres)."""

    id: UUID
    requester_account_id: UUID | None  # None = walk-in ouvert au bureau (identifié par le nom)
    requester_name: str | None  # renseigné pour un walk-in
    with_pastor_account_id: UUID | None  # le pasteur du RDV (déduit du créneau réservé)
    category: str  # prayer | marriage | visit | counsel | administrative | other
    subject: str
    preferred_at: datetime | None  # le créneau souhaité par le demandeur
    note: str | None
    status: str
    scheduled_at: datetime | None  # le créneau confirmé par la secrétaire
    decision_note: str | None  # le mot doux d'un déclin
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AgendaEntryDTO:
    """Un créneau **à organiser** — ce que le secrétariat a le droit de voir. Rien de plus.

    Ce n'est pas un `AppointmentDTO` amputé : c'est un **type différent**, et c'est délibéré.
    Un filtrage conditionnel s'oublie ; un type qui ne porte pas le champ ne peut pas le fuir.
    Ni `subject`, ni `note`, ni `decision_note` n'existent ici.

    Le secrétariat voit un créneau à préparer, jamais une demande en attente ni son motif —
    sans quoi « on sait qu'il a demandé » circule dans l'église, et le coût social que le canal
    venait de supprimer revient par la porte administrative.
    """

    id: UUID
    requester_account_id: UUID | None
    requester_name: str | None  # walk-in
    with_pastor_account_id: UUID | None
    category: str
    scheduled_at: datetime  # toujours posé : une entrée d'agenda est un créneau
    created_at: datetime


@dataclass(frozen=True)
class AvailabilityRuleDTO:
    """Une disponibilité récurrente d'un pasteur (jour + fenêtre + durée de créneau)."""

    id: UUID
    pastor_account_id: UUID
    weekday: int  # 0 = lundi … 6 = dimanche
    start_minute: int  # minutes depuis minuit (UTC)
    end_minute: int
    slot_minutes: int


@dataclass(frozen=True)
class SlotDTO:
    """Un créneau ouvert, réservable — engendré des règles, moins ceux déjà pris."""

    pastor_account_id: UUID
    starts_at: datetime
    ends_at: datetime
