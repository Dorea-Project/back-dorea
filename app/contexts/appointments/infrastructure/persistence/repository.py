"""Dépôt SQLAlchemy du module Rendez-vous."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.availability import AvailabilityRule
from app.contexts.appointments.domain.enums import AppointmentCategory, AppointmentStatus
from app.contexts.appointments.domain.repositories import (
    AppointmentRepository,
    AvailabilityRuleRepository,
    PastorUnavailabilityRepository,
)
from app.contexts.appointments.domain.unavailability import PastorUnavailability
from app.contexts.appointments.infrastructure.persistence.models import (
    AppointmentModel,
    AvailabilityRuleModel,
    PastorUnavailabilityModel,
)

# L'agenda vivant = ce qui reste à traiter ou à venir (pas les rendez-vous résolus).
_OPEN = (AppointmentStatus.REQUESTED.value, AppointmentStatus.CONFIRMED.value)


def _to_appointment(row: AppointmentModel) -> Appointment:
    return Appointment(
        id=row.id,
        tenant_id=row.tenant_id,
        requester_account_id=row.requester_account_id,
        requester_name=row.requester_name,
        requester_phone=row.requester_phone,
        with_pastor_account_id=row.with_pastor_account_id,
        category=AppointmentCategory(row.category),
        subject=row.subject,
        preferred_at=row.preferred_at,
        note=row.note,
        status=AppointmentStatus(row.status),
        scheduled_at=row.scheduled_at,
        handled_by_account_id=row.handled_by_account_id,
        decision_note=row.decision_note,
        oriented_to_account_id=row.oriented_to_account_id,
        cancelled_by_account_id=row.cancelled_by_account_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAppointmentRepository(AppointmentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, appointment: Appointment) -> None:
        self._session.add(
            AppointmentModel(
                id=appointment.id,
                tenant_id=appointment.tenant_id,
                requester_account_id=appointment.requester_account_id,
                requester_name=appointment.requester_name,
                requester_phone=appointment.requester_phone,
                with_pastor_account_id=appointment.with_pastor_account_id,
                category=appointment.category.value,
                subject=appointment.subject,
                preferred_at=appointment.preferred_at,
                note=appointment.note,
                status=appointment.status.value,
                scheduled_at=appointment.scheduled_at,
                handled_by_account_id=appointment.handled_by_account_id,
                decision_note=appointment.decision_note,
                oriented_to_account_id=appointment.oriented_to_account_id,
                cancelled_by_account_id=appointment.cancelled_by_account_id,
                created_at=appointment.created_at,
                updated_at=appointment.updated_at,
            )
        )
        await self._session.flush()

    async def get(self, appointment_id: UUID) -> Appointment | None:
        row = await self._session.get(AppointmentModel, appointment_id)
        return _to_appointment(row) if row is not None else None

    async def save(self, appointment: Appointment) -> None:
        row = await self._session.get(AppointmentModel, appointment.id)
        if row is None:
            return
        row.status = appointment.status.value
        row.scheduled_at = appointment.scheduled_at
        row.handled_by_account_id = appointment.handled_by_account_id
        row.decision_note = appointment.decision_note
        row.oriented_to_account_id = appointment.oriented_to_account_id
        row.cancelled_by_account_id = appointment.cancelled_by_account_id
        row.updated_at = appointment.updated_at
        await self._session.flush()

    async def list_by_requester(
        self, requester_account_id: UUID, tenant_id: UUID
    ) -> list[Appointment]:
        stmt = select(AppointmentModel).where(
            AppointmentModel.requester_account_id == requester_account_id,
            AppointmentModel.tenant_id == tenant_id,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_appointment(r) for r in rows]

    async def list_open_for_tenant(self, tenant_id: UUID) -> list[Appointment]:
        stmt = select(AppointmentModel).where(
            AppointmentModel.tenant_id == tenant_id,
            AppointmentModel.status.in_(_OPEN),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_appointment(r) for r in rows]

    async def list_confirmed_between(
        self, tenant_id: UUID, from_dt: datetime, to_dt: datetime
    ) -> list[Appointment]:
        stmt = select(AppointmentModel).where(
            AppointmentModel.tenant_id == tenant_id,
            AppointmentModel.status == AppointmentStatus.CONFIRMED.value,
            AppointmentModel.scheduled_at >= from_dt,
            AppointmentModel.scheduled_at <= to_dt,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_appointment(r) for r in rows]


def _to_rule(row: AvailabilityRuleModel) -> AvailabilityRule:
    return AvailabilityRule(
        id=row.id,
        tenant_id=row.tenant_id,
        pastor_account_id=row.pastor_account_id,
        weekday=row.weekday,
        start_minute=row.start_minute,
        end_minute=row.end_minute,
        slot_minutes=row.slot_minutes,
        active=row.active,
        created_at=row.created_at,
    )


class SqlAvailabilityRuleRepository(AvailabilityRuleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, rule: AvailabilityRule) -> None:
        self._session.add(
            AvailabilityRuleModel(
                id=rule.id,
                tenant_id=rule.tenant_id,
                pastor_account_id=rule.pastor_account_id,
                weekday=rule.weekday,
                start_minute=rule.start_minute,
                end_minute=rule.end_minute,
                slot_minutes=rule.slot_minutes,
                active=rule.active,
                created_at=rule.created_at,
            )
        )
        await self._session.flush()

    async def get(self, rule_id: UUID) -> AvailabilityRule | None:
        row = await self._session.get(AvailabilityRuleModel, rule_id)
        return _to_rule(row) if row is not None else None

    async def save(self, rule: AvailabilityRule) -> None:
        row = await self._session.get(AvailabilityRuleModel, rule.id)
        if row is None:
            return
        row.active = rule.active
        await self._session.flush()

    async def list_active_by_tenant(self, tenant_id: UUID) -> list[AvailabilityRule]:
        stmt = select(AvailabilityRuleModel).where(
            AvailabilityRuleModel.tenant_id == tenant_id,
            AvailabilityRuleModel.active.is_(True),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_rule(r) for r in rows]

    async def list_active_by_pastor(
        self, pastor_account_id: UUID, tenant_id: UUID
    ) -> list[AvailabilityRule]:
        stmt = select(AvailabilityRuleModel).where(
            AvailabilityRuleModel.pastor_account_id == pastor_account_id,
            AvailabilityRuleModel.tenant_id == tenant_id,
            AvailabilityRuleModel.active.is_(True),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_rule(r) for r in rows]


def _to_unavailability(row: PastorUnavailabilityModel) -> PastorUnavailability:
    return PastorUnavailability(
        id=row.id,
        tenant_id=row.tenant_id,
        pastor_account_id=row.pastor_account_id,
        unavailable_from=row.unavailable_from,
        unavailable_until=row.unavailable_until,
        declared_by_account_id=row.declared_by_account_id,
        declared_at=row.declared_at,
        reason=row.reason,
        canceled_at=row.canceled_at,
    )


class SqlPastorUnavailabilityRepository(PastorUnavailabilityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, unavailability: PastorUnavailability) -> None:
        self._session.add(
            PastorUnavailabilityModel(
                id=unavailability.id,
                tenant_id=unavailability.tenant_id,
                pastor_account_id=unavailability.pastor_account_id,
                unavailable_from=unavailability.unavailable_from,
                unavailable_until=unavailability.unavailable_until,
                reason=unavailability.reason,
                declared_by_account_id=unavailability.declared_by_account_id,
                declared_at=unavailability.declared_at,
                canceled_at=unavailability.canceled_at,
            )
        )
        await self._session.flush()

    async def get(self, unavailability_id: UUID) -> PastorUnavailability | None:
        row = await self._session.get(PastorUnavailabilityModel, unavailability_id)
        return _to_unavailability(row) if row is not None else None

    async def save(self, unavailability: PastorUnavailability) -> None:
        row = await self._session.get(PastorUnavailabilityModel, unavailability.id)
        if row is None:
            return
        row.canceled_at = unavailability.canceled_at
        await self._session.flush()

    async def list_active_for(
        self, pastor_account_id: UUID, tenant_id: UUID
    ) -> list[PastorUnavailability]:
        stmt = select(PastorUnavailabilityModel).where(
            PastorUnavailabilityModel.pastor_account_id == pastor_account_id,
            PastorUnavailabilityModel.tenant_id == tenant_id,
            PastorUnavailabilityModel.canceled_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_unavailability(r) for r in rows]
