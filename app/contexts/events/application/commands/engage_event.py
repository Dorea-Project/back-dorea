"""Use cases **d'engagement** — la voix des membres devant l'événement.

Deux registres, comme partout dans Dorea : la **réaction** légère (« ça me parle ») et la
**confirmation de présence** (« je serai là », l'engagement). Réservé aux membres actifs.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from app._shared.messages import MessageKey
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
from app.contexts.notifications.application.notifier import (
    NotificationScheduler,
    Notifier,
    PushNotification,
)


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


# Combien de temps avant l'événement on rappelle celui qui a dit « je serai là ».
#
# La veille, pas le matin même : un repas à 18 h rappelé à 17 h ne sert plus à rien — il faut
# encore pouvoir s'organiser, cuisiner, prévenir quelqu'un.
REMINDER_LEAD_HOURS = 24


class ConfirmParticipation:
    """« Je serai là » — et **on le lui rappellera**.

    C'était le seul engagement du produit qui ne revenait jamais vers celui qui l'avait pris :
    l'organisateur était prévenu, le participant non. Quatre notifications existaient dans ce
    module, et la seule qui atteignait un confirmé était l'annulation — on ne lui parlait que
    pour lui dire que ça n'aurait pas lieu.

    **Ce rappel n'est pas une sollicitation**, et c'est ce qui le distingue de l'anniversaire, où
    le produit refuse tout push. Personne ne le reçoit sans l'avoir demandé : il découle d'un
    geste explicite, il part une fois, il ne se rafraîchit pas, et se désinscrire l'annule. Ce
    n'est pas une boucle d'habitude — c'est tenir parole envers quelqu'un qui a donné la sienne.
    """

    def __init__(
        self,
        events: EventRepository,
        participants: EventParticipantRepository,
        memberships: MembershipRepository,
        notifier: Notifier | None = None,
        scheduler: NotificationScheduler | None = None,
        *,
        clock,
    ) -> None:
        self._events = events
        self._participants = participants
        self._memberships = memberships
        self._notifier = notifier
        self._scheduler = scheduler
        self._clock = clock

    async def _remind(self, event, account_id: UUID) -> None:
        """Pose le rappel dans l'outbox. Best-effort : il ne bloque jamais une confirmation."""
        if self._scheduler is None:
            return
        at = event.starts_at - timedelta(hours=REMINDER_LEAD_HOURS)
        if at <= self._clock():
            # On confirme parfois le matin même. Un rappel daté d'hier partirait immédiatement et
            # ferait doublon avec le geste qu'on vient de poser.
            return
        # Deux clés plutôt qu'un bout de f-string : le tiret qui sépare le titre du lieu est de
        # Dorea, pas de l'auteur. Laissé au point d'appel, il serait introuvable en anglais.
        place = event.place_label
        await self._scheduler.schedule(
            [account_id],
            PushNotification(
                key=MessageKey.EVENT_TOMORROW_AT if place else MessageKey.EVENT_TOMORROW,
                params={"title": event.title, "place": place} if place
                else {"title": event.title},
                data={"type": "event", "id": str(event.id)},
            ),
            at=at,
        )

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
        await self._remind(event, actor_account_id)
        # Prévenir l'organisateur qu'une présence de plus se confirme (pas soi-même) — best-effort.
        if self._notifier is not None and actor_account_id != event.author_account_id:
            await self._notifier.notify(
                [event.author_account_id],
                PushNotification(
                    key=MessageKey.EVENT_PARTICIPANT_CONFIRMED,
                    params={"title": event.title},
                    data={"type": "event", "id": str(event.id)},
                ),
            )


class WithdrawParticipation:
    def __init__(self, participants: EventParticipantRepository) -> None:
        self._participants = participants

    async def execute(self, *, actor_account_id: UUID, event_id: UUID) -> None:
        await self._participants.remove(event_id, actor_account_id)  # tolérant si absent
