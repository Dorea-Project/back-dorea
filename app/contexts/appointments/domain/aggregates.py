"""Agrégat `Appointment` (module Rendez-vous) — l'agenda du pasteur, gardé par la secrétaire.

Un membre **demande** ; la secrétaire (les mains du pasteur) **confirme** un créneau, **décline**
avec un mot, ou le rendez-vous est **honoré**. Le demandeur peut **annuler**. Le sujet est
confidentiel : porté par l'agrégat, visible seulement du demandeur et des gardiens de l'agenda.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.appointments.domain.enums import AppointmentCategory, AppointmentStatus
from app.contexts.appointments.domain.errors import (
    AppointmentClosedError,
    AppointmentSubjectRequiredError,
    RequesterIdentityRequiredError,
)

_TERMINAL = (
    AppointmentStatus.DECLINED,
    AppointmentStatus.CANCELLED,
    AppointmentStatus.COMPLETED,
)


class Appointment(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        requester_account_id: UUID | None,
        requester_name: str | None,
        requester_phone: str | None,
        with_pastor_account_id: UUID | None,
        category: AppointmentCategory,
        subject: str,
        preferred_at: datetime | None,
        note: str | None,
        status: AppointmentStatus,
        scheduled_at: datetime | None,
        handled_by_account_id: UUID | None,
        decision_note: str | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        # Émetteur : un **membre** (compte) OU un **walk-in** au bureau (nom + tél, sans compte).
        self.requester_account_id = requester_account_id
        self.requester_name = requester_name
        self.requester_phone = requester_phone
        self.with_pastor_account_id = with_pastor_account_id  # pasteur du RDV (déduit du créneau)
        self.category = category
        self.subject = subject
        self.preferred_at = preferred_at
        self.note = note
        self.status = status
        self.scheduled_at = scheduled_at
        self.handled_by_account_id = handled_by_account_id
        self.decision_note = decision_note
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def request(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        requester_account_id: UUID,
        subject: str,
        category: AppointmentCategory,
        now: datetime,
        preferred_at: datetime | None = None,
        note: str | None = None,
    ) -> Appointment:
        """Un **membre** demande lui-même (mobile) : il est l'émetteur, statut `requested`."""
        return cls._new(
            id=id,
            tenant_id=tenant_id,
            requester_account_id=requester_account_id,
            requester_name=None,
            requester_phone=None,
            category=category,
            subject=subject,
            now=now,
            preferred_at=preferred_at,
            note=note,
        )

    @classmethod
    def open_at_office(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        opened_by_account_id: UUID,
        subject: str,
        category: AppointmentCategory,
        now: datetime,
        requester_account_id: UUID | None = None,
        requester_name: str | None = None,
        requester_phone: str | None = None,
        with_pastor_account_id: UUID | None = None,
        scheduled_at: datetime | None = None,
        preferred_at: datetime | None = None,
        note: str | None = None,
    ) -> Appointment:
        """La **secrétaire ouvre** un RDV au bureau : pour un membre (compte) ou un walk-in (nom).

        Si un créneau est donné, le RDV naît **confirmé** (elle le pose sur-le-champ) ; sinon il
        naît `requested` (à traiter plus tard)."""
        name = (requester_name.strip() or None) if requester_name else None
        if requester_account_id is None and name is None:
            raise RequesterIdentityRequiredError(
                "Précisez le membre, ou au moins le nom de la personne."
            )
        appointment = cls._new(
            id=id,
            tenant_id=tenant_id,
            requester_account_id=requester_account_id,
            requester_name=name,
            requester_phone=(requester_phone.strip() or None) if requester_phone else None,
            with_pastor_account_id=with_pastor_account_id,
            category=category,
            subject=subject,
            now=now,
            preferred_at=preferred_at,
            note=note,
        )
        if scheduled_at is not None:
            appointment.confirm(at=scheduled_at, by_account_id=opened_by_account_id, now=now)
        return appointment

    @classmethod
    def book(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        requester_account_id: UUID | None,
        with_pastor_account_id: UUID,
        subject: str,
        category: AppointmentCategory,
        scheduled_at: datetime,
        now: datetime,
        booked_by_account_id: UUID | None = None,
        requester_name: str | None = None,
        requester_phone: str | None = None,
        note: str | None = None,
    ) -> Appointment:
        """Réserver un **créneau** ouvert → le RDV naît **confirmé** sur ce pasteur et cette heure.

        Le pasteur (`with_pastor_account_id`) est déduit du créneau choisi (« premier dispo »).
        `booked_by_account_id` = qui a réservé (le membre lui-même, ou la secrétaire)."""
        appointment = cls._new(
            id=id,
            tenant_id=tenant_id,
            requester_account_id=requester_account_id,
            requester_name=requester_name,
            requester_phone=requester_phone,
            with_pastor_account_id=with_pastor_account_id,
            category=category,
            subject=subject,
            now=now,
            preferred_at=None,
            note=note,
        )
        appointment.confirm(
            at=scheduled_at, by_account_id=booked_by_account_id or with_pastor_account_id, now=now
        )
        return appointment

    @classmethod
    def _new(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        requester_account_id: UUID | None,
        requester_name: str | None,
        requester_phone: str | None,
        category: AppointmentCategory,
        subject: str,
        now: datetime,
        preferred_at: datetime | None,
        note: str | None,
        with_pastor_account_id: UUID | None = None,
    ) -> Appointment:
        subject = subject.strip()
        if not subject:
            raise AppointmentSubjectRequiredError("Dites en un mot l'objet de la rencontre.")
        return cls(
            id=id,
            tenant_id=tenant_id,
            requester_account_id=requester_account_id,
            requester_name=requester_name,
            requester_phone=requester_phone,
            with_pastor_account_id=with_pastor_account_id,
            category=category,
            subject=subject,
            preferred_at=preferred_at,
            note=(note.strip() or None) if note else None,
            status=AppointmentStatus.REQUESTED,
            scheduled_at=None,
            handled_by_account_id=None,
            decision_note=None,
            created_at=now,
            updated_at=now,
        )

    def confirm(self, *, at: datetime, by_account_id: UUID, now: datetime) -> None:
        """Poser (ou déplacer) le créneau — depuis une demande en attente ou déjà confirmée."""
        if self.status not in (AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED):
            raise AppointmentClosedError(
                "Ce rendez-vous est déjà résolu.",
                details={"appointment_id": str(self.id), "status": self.status.value},
            )
        self.status = AppointmentStatus.CONFIRMED
        self.scheduled_at = at
        self.handled_by_account_id = by_account_id
        self.updated_at = now

    def decline(self, *, by_account_id: UUID, reason: str | None, now: datetime) -> None:
        """Ne pas retenir une demande **en attente** — toujours avec un mot doux."""
        if self.status is not AppointmentStatus.REQUESTED:
            raise AppointmentClosedError(
                "On ne décline qu'une demande en attente.",
                details={"appointment_id": str(self.id), "status": self.status.value},
            )
        self.status = AppointmentStatus.DECLINED
        self.handled_by_account_id = by_account_id
        self.decision_note = (reason.strip() or None) if reason else None
        self.updated_at = now

    def complete(self, *, by_account_id: UUID, now: datetime) -> None:
        """Marquer honoré — seul un rendez-vous confirmé peut l'être."""
        if self.status is not AppointmentStatus.CONFIRMED:
            raise AppointmentClosedError(
                "Seul un rendez-vous confirmé se marque honoré.",
                details={"appointment_id": str(self.id), "status": self.status.value},
            )
        self.status = AppointmentStatus.COMPLETED
        self.handled_by_account_id = by_account_id
        self.updated_at = now

    def cancel(self, *, now: datetime) -> None:
        """Le demandeur se rétracte — tant que le rendez-vous n'est pas déjà résolu."""
        if self.status in _TERMINAL:
            raise AppointmentClosedError(
                "Ce rendez-vous est déjà résolu.",
                details={"appointment_id": str(self.id), "status": self.status.value},
            )
        self.status = AppointmentStatus.CANCELLED
        self.updated_at = now
