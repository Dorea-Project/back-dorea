"""Use cases **d'engagement** — la voix des membres devant l'événement.

Deux registres, comme partout dans Dorea : la **réaction** légère (« ça me parle ») et la
**confirmation de présence** (« je serai là », l'engagement). Réservé aux membres actifs.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.events.domain.aggregates import EventParticipant, EventReactionEntry
from app.contexts.events.domain.enums import EventReaction
from app.contexts.events.domain.errors import (
    EventNotFoundError,
    NotAChurchMemberError,
)
from app.contexts.events.domain.repositories import (
    EventParticipantRepository,
    EventReactionRepository,
    EventRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.notifications.application.notifier import Notifier, PushNotification


async def _load_live_event(events: EventRepository, event_id: UUID):
    event = await events.get(event_id)
    if event is None:
        raise EventNotFoundError("Événement introuvable.", details={"event_id": str(event_id)})
    event.ensure_live()  # on ne s'engage pas sur un événement annulé
    return event


class ReactToEvent:
    def __init__(
        self,
        events: EventRepository,
        reactions: EventReactionRepository,
        memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._events = events
        self._reactions = reactions
        self._memberships = memberships
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, event_id: UUID, kind: EventReaction
    ) -> None:
        event = await _load_live_event(self._events, event_id)
        if await self._memberships.get_active(actor_account_id, event.tenant_id) is None:
            raise NotAChurchMemberError("Réservé aux membres de l'église.")
        # Une réaction par membre : re-réagir change simplement le type.
        if await self._reactions.get_for(event_id, actor_account_id) is not None:
            await self._reactions.remove(event_id, actor_account_id)
        await self._reactions.add(
            EventReactionEntry(
                id=uuid4(),
                event_id=event_id,
                account_id=actor_account_id,
                kind=kind,
                reacted_at=self._clock(),
            )
        )


class ConfirmParticipation:
    def __init__(
        self,
        events: EventRepository,
        participants: EventParticipantRepository,
        memberships: MembershipRepository,
        notifier: Notifier | None = None,
        *,
        clock,
    ) -> None:
        self._events = events
        self._participants = participants
        self._memberships = memberships
        self._notifier = notifier
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, event_id: UUID) -> None:
        event = await _load_live_event(self._events, event_id)
        if await self._memberships.get_active(actor_account_id, event.tenant_id) is None:
            raise NotAChurchMemberError("Réservé aux membres de l'église.")
        if await self._participants.get(event_id, actor_account_id) is not None:
            return  # idempotent : déjà confirmé
        await self._participants.add(
            EventParticipant(
                id=uuid4(),
                event_id=event_id,
                tenant_id=event.tenant_id,
                account_id=actor_account_id,
                confirmed_at=self._clock(),
            )
        )
        # Prévenir l'organisateur qu'une présence de plus se confirme (pas soi-même) — best-effort.
        if self._notifier is not None and actor_account_id != event.author_account_id:
            await self._notifier.notify(
                [event.author_account_id],
                PushNotification(
                    title="Nouvelle présence confirmée",
                    body=f"Quelqu'un sera présent à « {event.title} ».",
                    data={"type": "event", "id": str(event.id)},
                ),
            )


class WithdrawParticipation:
    def __init__(self, participants: EventParticipantRepository) -> None:
        self._participants = participants

    async def execute(self, *, actor_account_id: UUID, event_id: UUID) -> None:
        await self._participants.remove(event_id, actor_account_id)  # tolérant si absent
