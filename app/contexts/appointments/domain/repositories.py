"""Ports de persistance du module Rendez-vous."""

from abc import abstractmethod
from datetime import datetime
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.availability import AvailabilityRule


class AppointmentRepository(Repository):
    @abstractmethod
    async def add(self, appointment: Appointment) -> None: ...

    @abstractmethod
    async def get(self, appointment_id: UUID) -> Appointment | None: ...

    @abstractmethod
    async def save(self, appointment: Appointment) -> None:
        """Persiste une transition (confirmation / déclin / annulation / honoré)."""
        ...

    @abstractmethod
    async def list_by_requester(
        self, requester_account_id: UUID, tenant_id: UUID
    ) -> list[Appointment]:
        """Mes rendez-vous (le demandeur voit les siens, tous statuts)."""
        ...

    @abstractmethod
    async def list_open_for_tenant(self, tenant_id: UUID) -> list[Appointment]:
        """L'agenda vivant : demandes en attente + rendez-vous confirmés (pas les résolus)."""
        ...

    @abstractmethod
    async def list_confirmed_between(
        self, tenant_id: UUID, from_dt: datetime, to_dt: datetime
    ) -> list[Appointment]:
        """Les RDV **confirmés** dont le créneau tombe dans [from, to] — pour retirer de
        l'offre les créneaux déjà réservés (et bloquer la double réservation)."""
        ...


class AvailabilityRuleRepository(Repository):
    @abstractmethod
    async def add(self, rule: AvailabilityRule) -> None: ...

    @abstractmethod
    async def get(self, rule_id: UUID) -> AvailabilityRule | None: ...

    @abstractmethod
    async def save(self, rule: AvailabilityRule) -> None:
        """Persiste une désactivation."""
        ...

    @abstractmethod
    async def list_active_by_tenant(self, tenant_id: UUID) -> list[AvailabilityRule]:
        """Toutes les disponibilités actives de l'église (tous pasteurs)."""
        ...

    @abstractmethod
    async def list_active_by_pastor(
        self, pastor_account_id: UUID, tenant_id: UUID
    ) -> list[AvailabilityRule]:
        """Les disponibilités actives d'un pasteur (pour valider un créneau réservé)."""
        ...
