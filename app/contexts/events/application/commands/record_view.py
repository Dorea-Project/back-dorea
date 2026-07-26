"""Use case `RecordEventView` — tracer une **vue** de l'événement (spectateurs distincts).

Une vue par membre (distincte, idempotente), portant la **dénomination** de l'église regardée —
c'est la matière de « les vus par dénomination ». En E-0 (portée église), tous les spectateurs
sont de l'église de l'événement ; l'attribution par dénomination du spectateur s'affinera avec les
portées élargies.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.events.application.ports import EventAudiencePort
from app.contexts.events.domain.aggregates import EventView
from app.contexts.events.domain.errors import EventNotFoundError, NotAChurchMemberError
from app.contexts.events.domain.repositories import EventRepository, EventViewRepository
from app.contexts.iam.domain.repositories import MembershipRepository


class RecordEventView:
    def __init__(
        self,
        events: EventRepository,
        views: EventViewRepository,
        memberships: MembershipRepository,
        audience: EventAudiencePort,
        *,
        clock,
    ) -> None:
        self._events = events
        self._views = views
        self._memberships = memberships
        self._audience = audience
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, event_id: UUID) -> None:
        event = await self._events.get(event_id)
        if event is None:
            raise EventNotFoundError(
                "Événement introuvable.", details={"event_id": str(event_id)}
            )
        if await self._memberships.get_active(actor_account_id, event.tenant_id) is None:
            raise NotAChurchMemberError("Réservé aux membres de l'église.")
        if await self._views.get(event_id, actor_account_id) is not None:
            return  # une vue distincte par spectateur
        denomination = await self._audience.denomination_of(event.tenant_id)
        await self._views.add(
            EventView(
                id=uuid4(),
                event_id=event_id,
                viewer_account_id=actor_account_id,
                denomination=denomination,
                viewed_at=self._clock(),
            )
        )
