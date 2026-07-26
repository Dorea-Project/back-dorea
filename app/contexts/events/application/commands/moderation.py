"""Use cases de **modération** de la diffusion élargie.

- `ReportEvent` — tout **membre actif** signale un événement qui ne devrait pas rayonner ainsi
  (spam, abus). Un signalement par membre et par événement.
- `TakeDownEvent` — la **Plateforme** (jeton de service) retire un événement. *Révélateur, pas
  juge* : le signalement éclaire, l'humain de la Plateforme tranche.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.events.application.dtos import EventDTO
from app.contexts.events.application.mapping import to_event_dto
from app.contexts.events.domain.aggregates import EventReport
from app.contexts.events.domain.errors import EventNotFoundError, NotAChurchMemberError
from app.contexts.events.domain.repositories import (
    EventReportRepository,
    EventRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.notifications.application.notifier import Notifier, PushNotification


class ReportEvent:
    def __init__(
        self,
        events: EventRepository,
        reports: EventReportRepository,
        memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._events = events
        self._reports = reports
        self._memberships = memberships
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, event_id: UUID, reason: str | None = None
    ) -> None:
        event = await self._events.get(event_id)
        if event is None:
            raise EventNotFoundError(
                "Événement introuvable.", details={"event_id": str(event_id)}
            )
        if await self._memberships.get_active(actor_account_id, event.tenant_id) is None:
            # Le signaleur peut appartenir à une autre église (portée élargie) : on n'exige
            # l'appartenance qu'à l'église de l'événement en E-0 (portée majoritairement locale).
            raise NotAChurchMemberError("Réservé aux membres de l'église.")
        if await self._reports.get(event_id, actor_account_id) is not None:
            return  # un signalement par membre (idempotent)
        await self._reports.add(
            EventReport(
                id=uuid4(),
                event_id=event_id,
                reporter_account_id=actor_account_id,
                reason=(reason.strip() or None) if reason else None,
                created_at=self._clock(),
            )
        )


class TakeDownEvent:
    """Réservé à la Plateforme (la route est gardée par le jeton de service)."""

    def __init__(
        self, events: EventRepository, notifier: Notifier | None = None, *, clock
    ) -> None:
        self._events = events
        self._notifier = notifier
        self._clock = clock

    async def execute(self, *, event_id: UUID, reason: str | None = None) -> EventDTO:
        event = await self._events.get(event_id)
        if event is None:
            raise EventNotFoundError(
                "Événement introuvable.", details={"event_id": str(event_id)}
            )
        event.take_down(reason=reason, now=self._clock())
        await self._events.save(event)
        # Prévenir l'auteur (best-effort) que son événement a été retiré.
        if self._notifier is not None:
            await self._notifier.notify(
                [event.author_account_id],
                PushNotification(
                    title="Événement retiré",
                    body="Votre événement a été retiré par la modération.",
                    data={"type": "event", "id": str(event.id)},
                ),
            )
        return to_event_dto(event, participant_count=0)
