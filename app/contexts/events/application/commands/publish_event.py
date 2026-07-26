"""Use cases **auteur** de l'événement — publier, annuler.

`PublishEvent` — tout **membre actif** publie un événement pour son église (portée CHURCH en E-0 ;
au-delà exige le compte Business, à venir). `CancelEvent` — l'auteur seul annule.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.events.application.dtos import EventDTO
from app.contexts.events.application.mapping import to_event_dto
from app.contexts.events.application.ports import BusinessTierPort, EventAudiencePort
from app.contexts.events.domain.aggregates import Event
from app.contexts.events.domain.enums import EventCategory, EventScope
from app.contexts.events.domain.errors import (
    EventNotFoundError,
    NotAChurchMemberError,
    NotEventAuthorError,
)
from app.contexts.events.domain.repositories import (
    EventParticipantRepository,
    EventRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.notifications.application.notifier import (
    NotificationScheduler,
    Notifier,
    PushNotification,
)


class PublishEvent:
    def __init__(
        self,
        events: EventRepository,
        memberships: MembershipRepository,
        business: BusinessTierPort,
        audience: EventAudiencePort | None = None,
        notifier: Notifier | None = None,
        scheduler: NotificationScheduler | None = None,
        *,
        clock,
    ) -> None:
        self._events = events
        self._memberships = memberships
        self._business = business
        self._audience = audience
        self._notifier = notifier
        self._scheduler = scheduler
        self._clock = clock

    async def _broadcast(self, event: Event) -> None:
        """Prévenir l'audience atteinte (best-effort). Église/dénomination : envoi synchrone.
        Plateforme : audience trop large → **enqueue** dans l'outbox (dispatché hors requête)."""
        if self._audience is None:
            return
        notification = PushNotification(
            title="Nouvel événement",
            body=f"« {event.title} »",
            data={"type": "event", "id": str(event.id)},
        )
        if event.scope is EventScope.PLATFORM:
            await self._broadcast_platform(event, notification)
            return
        if self._notifier is None:
            return
        if event.scope is EventScope.CHURCH:
            tenant_ids = [event.tenant_id]
        else:  # DENOMINATION
            denomination = await self._audience.denomination_of(event.tenant_id)
            tenant_ids = (
                await self._audience.tenants_in_denomination(denomination)
                if denomination is not None
                else []
            )
        targets = await self._targets(event, tenant_ids)
        await self._notifier.notify(targets, notification)

    async def _broadcast_platform(self, event: Event, notification: PushNotification) -> None:
        """Portée plateforme : on résout l'audience puis on l'**enqueue** (envoi différé)."""
        if self._scheduler is None:
            return
        tenant_ids = await self._audience.all_tenant_ids()
        targets = await self._targets(event, tenant_ids)
        await self._scheduler.schedule(targets, notification, at=self._clock())

    async def _targets(self, event: Event, tenant_ids: list[UUID]) -> list[UUID]:
        accounts = await self._audience.member_account_ids(tenant_ids)
        return [a for a in accounts if a != event.author_account_id]  # pas soi-même

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        category: EventCategory,
        title: str,
        starts_at: datetime,
        scope: EventScope = EventScope.CHURCH,
        description: str | None = None,
        ends_at: datetime | None = None,
        place_label: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        media_urls: list[str] | None = None,
    ) -> EventDTO:
        if await self._memberships.get_active(actor_account_id, tenant_id) is None:
            raise NotAChurchMemberError(
                "Rejoignez d'abord cette église pour y publier un événement.",
                details={"tenant_id": str(tenant_id)},
            )
        # La porte du rayonnement : au-delà de l'église, il faut le compte Business de l'auteur.
        business_active = scope is not EventScope.CHURCH and await self._business.is_business(
            actor_account_id
        )
        event = Event.publish(
            id=uuid4(),
            tenant_id=tenant_id,
            author_account_id=actor_account_id,
            category=category,
            title=title,
            starts_at=starts_at,
            now=self._clock(),
            scope=scope,
            description=description,
            ends_at=ends_at,
            place_label=place_label,
            latitude=latitude,
            longitude=longitude,
            media_urls=media_urls,
            business_active=business_active,
        )
        await self._events.add(event)
        await self._broadcast(event)
        return to_event_dto(event, participant_count=0)


class CancelEvent:
    def __init__(
        self,
        events: EventRepository,
        participants: EventParticipantRepository | None = None,
        notifier: Notifier | None = None,
        *,
        clock,
    ) -> None:
        self._events = events
        self._participants = participants
        self._notifier = notifier
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, event_id: UUID) -> EventDTO:
        event = await self._events.get(event_id)
        if event is None:
            raise EventNotFoundError(
                "Événement introuvable.", details={"event_id": str(event_id)}
            )
        if event.author_account_id != actor_account_id:
            raise NotEventAuthorError(
                "Seul l'organisateur peut annuler cet événement.",
                details={"event_id": str(event_id)},
            )
        event.cancel()
        await self._events.save(event)
        # Prévenir les présents confirmés (best-effort) : c'était prévu, c'est annulé.
        if self._notifier is not None and self._participants is not None:
            confirmed = await self._participants.list_by_event(event_id)
            await self._notifier.notify(
                [p.account_id for p in confirmed],
                PushNotification(
                    title="Événement annulé",
                    body=f"« {event.title} » a été annulé.",
                    data={"type": "event", "id": str(event.id)},
                ),
            )
        return to_event_dto(event, participant_count=0)
