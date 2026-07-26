"""Requête `ListOpenSlots` — « qui est libre quand » (tous pasteurs confondus).

Engendre les créneaux depuis les disponibilités et **retire** ceux déjà réservés et le passé.
C'est la réponse à « autre pasteur disponible » : si l'un n'a rien, la liste montre les autres.
Ouverte à tout **membre actif** (pour se réserver lui-même) et aux gardiens.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from app.contexts.appointments.application.dtos import SlotDTO
from app.contexts.appointments.application.mapping import to_slot_dto
from app.contexts.appointments.application.slots_service import open_slots_from
from app.contexts.appointments.domain.errors import RequesterNotMemberError
from app.contexts.appointments.domain.repositories import (
    AppointmentRepository,
    AvailabilityRuleRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository

_MAX_WINDOW_DAYS = 62  # borne l'engendrement (2 mois d'offre à la fois)


class ListOpenSlots:
    def __init__(
        self,
        rules: AvailabilityRuleRepository,
        appointments: AppointmentRepository,
        memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._rules = rules
        self._appointments = appointments
        self._memberships = memberships
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
        pastor_account_id: UUID | None = None,
    ) -> list[SlotDTO]:
        if await self._memberships.get_active(actor_account_id, tenant_id) is None:
            raise RequesterNotMemberError(
                "Rejoignez d'abord cette église pour voir les disponibilités.",
                details={"tenant_id": str(tenant_id)},
            )
        # Borne la fenêtre pour éviter un engendrement démesuré.
        if to_date > from_date + timedelta(days=_MAX_WINDOW_DAYS):
            to_date = from_date + timedelta(days=_MAX_WINDOW_DAYS)

        rules = await self._rules.list_active_by_tenant(tenant_id)
        if pastor_account_id is not None:
            rules = [r for r in rules if r.pastor_account_id == pastor_account_id]

        booked = await self._appointments.list_confirmed_between(
            tenant_id,
            datetime.combine(from_date, time.min, tzinfo=UTC),
            datetime.combine(to_date, time.max, tzinfo=UTC),
        )
        slots = open_slots_from(
            rules, booked, from_date=from_date, to_date=to_date, now=self._clock()
        )
        return [to_slot_dto(s) for s in slots]
