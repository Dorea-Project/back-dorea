"""Requêtes du module Event — le fil d'événements, le détail, la liste des confirmés.

`ListChurchEvents` / `GetEvent` : ouverts aux membres, avec le **nombre de présences** et mes
propres marques. Le décompte agrégé des réactions n'est **pas** exposé sur la carte ni le détail
(invariant anti-compteur d'engagement) — il ne vit que dans `/stats`, réservé à l'organisateur.
`ListParticipants` : la **liste** des confirmés, réservée à l'organisateur (les autres n'en voient
que le nombre).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.contexts.events.application.dtos import EventDTO, ParticipantDTO
from app.contexts.events.application.mapping import to_event_dto, to_participant_dto
from app.contexts.events.application.ports import EventAudiencePort
from app.contexts.events.domain.aggregates import NEARBY_RADIUS_KM, Event
from app.contexts.events.domain.enums import EventScope
from app.contexts.events.domain.errors import (
    EventNotFoundError,
    NotAChurchMemberError,
    NotEventAuthorError,
)
from app.contexts.events.domain.geo import distance_km
from app.contexts.events.domain.repositories import (
    EventParticipantRepository,
    EventReactionRepository,
    EventRepository,
)
from app.contexts.iam.domain.repositories import MembershipRepository


def _upcoming(events: list[Event], now: datetime) -> list[Event]:
    """Ce qui n'est pas terminé, du plus proche au plus lointain.

    Le tri existait, le filtre non — et le commentaire disait déjà « les prochains d'abord ». Il
    était faux : rien n'écartait le passé, et comme l'ordre est croissant, **le plus ancien
    ouvrait le fil**. Un membre voyait en premier une sortie de janvier terminée depuis sept
    mois, et devait faire défiler pour trouver ce qui a lieu demain.

    `ends_at` existait aussi, écrit, validé, et lu nulle part. C'est ici qu'il sert."""
    return sorted(
        (e for e in events if not e.is_over(now)), key=lambda e: e.starts_at
    )


async def _decorate(
    event: Event,
    participants: EventParticipantRepository,
    reactions: EventReactionRepository,
    *,
    viewer_account_id: UUID | None,
) -> EventDTO:
    # Le décompte n'est plus servi au public : sans capacité, c'est un score. Il vit dans
    # `/stats`, pour l'organisateur.
    participant_count = None
    my_reaction = None
    i_confirmed = False
    if viewer_account_id is not None:
        mine = await reactions.get_for(event.id, viewer_account_id)
        my_reaction = mine.kind.value if mine is not None else None
        i_confirmed = await participants.get(event.id, viewer_account_id) is not None
    return to_event_dto(
        event,
        participant_count=participant_count,
        my_reaction=my_reaction,
        i_confirmed=i_confirmed,
    )


class ListChurchEvents:
    def __init__(
        self,
        events: EventRepository,
        participants: EventParticipantRepository,
        reactions: EventReactionRepository,
        *,
        clock=None,
    ) -> None:
        self._events = events
        self._participants = participants
        self._reactions = reactions
        # Sans horloge, on ne filtre pas : un appelant d'ancienne génération garde son
        # comportement plutôt que de recevoir une liste tronquée sans l'avoir demandé.
        self._clock = clock or (lambda: datetime.min.replace(tzinfo=UTC))

    async def execute(
        self, *, tenant_id: UUID, viewer_account_id: UUID
    ) -> list[EventDTO]:
        events = _upcoming(await self._events.list_published_by_tenant(tenant_id), self._clock())
        return [
            await _decorate(
                e, self._participants, self._reactions, viewer_account_id=viewer_account_id
            )
            for e in events
        ]


class ListVisibleEvents:
    """Le fil qui M'atteint : les événements de mon église + ceux de ma dénomination (portée
    dénomination) + ceux de toute la plateforme (portée plateforme). C'est ici que le rayonnement
    Business devient visible côté spectateur."""

    def __init__(
        self,
        events: EventRepository,
        participants: EventParticipantRepository,
        reactions: EventReactionRepository,
        audience: EventAudiencePort,
        memberships: MembershipRepository,
        *,
        clock=None,
    ) -> None:
        self._events = events
        self._participants = participants
        self._reactions = reactions
        self._audience = audience
        self._memberships = memberships
        self._clock = clock or (lambda: datetime.min.replace(tzinfo=UTC))

    async def execute(
        self, *, tenant_id: UUID, viewer_account_id: UUID
    ) -> list[EventDTO]:
        # Isolation inter-église : le fil « qui m'atteint » est celui de MON église (+ dénomination
        # + plateforme). On exige d'être membre actif du tenant demandé.
        if await self._memberships.get_active(viewer_account_id, tenant_id) is None:
            raise NotAChurchMemberError(
                "Rejoignez d'abord cette église pour en voir les événements.",
                details={"tenant_id": str(tenant_id)},
            )
        by_id: dict = {}
        for e in await self._events.list_published_by_tenant(tenant_id):
            by_id[e.id] = e  # tout ce que publie mon église (toutes portées)
        denomination = await self._audience.denomination_of(tenant_id)
        if denomination is not None:
            peers = await self._audience.tenants_in_denomination(denomination)
            for e in await self._events.list_published_by_scope(EventScope.DENOMINATION, peers):
                by_id.setdefault(e.id, e)
        for e in await self._events.list_published_by_scope(EventScope.PLATFORM, None):
            by_id.setdefault(e.id, e)  # toute la plateforme

        # **Le voisinage, vu depuis le spectateur.** C'est ici que la portée géographique devient
        # réelle : elle n'a poussé aucune notification, elle apparaît quand on ouvre l'application.
        #
        # Le rayon est mesuré depuis le **lieu de l'événement** vers **mon église** — le même
        # calcul que celui qui a défini l'audience à la publication, donc la même réponse. Le
        # faire depuis ma position à moi rendrait le fil dépendant d'où je me trouve à cet
        # instant, et un événement disparaîtrait parce que je suis parti au village.
        me = await self._audience.location_of(tenant_id)
        if me is not None:
            my_lat, my_lon = me
            for e in await self._events.list_published_by_scope(EventScope.NEARBY, None):
                if e.latitude is None or e.id in by_id:
                    continue
                if distance_km(e.latitude, e.longitude, my_lat, my_lon) <= NEARBY_RADIUS_KM:
                    by_id[e.id] = e

        ordered = _upcoming(list(by_id.values()), self._clock())
        return [
            await _decorate(
                e, self._participants, self._reactions, viewer_account_id=viewer_account_id
            )
            for e in ordered
        ]


class GetEvent:
    def __init__(
        self,
        events: EventRepository,
        participants: EventParticipantRepository,
        reactions: EventReactionRepository,
        audience: EventAudiencePort,
        memberships: MembershipRepository,
    ) -> None:
        self._events = events
        self._participants = participants
        self._reactions = reactions
        self._audience = audience
        self._memberships = memberships

    async def execute(self, *, event_id: UUID, viewer_account_id: UUID) -> EventDTO:
        event = await self._events.get(event_id)
        if event is None:
            raise EventNotFoundError(
                "Événement introuvable.", details={"event_id": str(event_id)}
            )
        await self._ensure_can_view(event, viewer_account_id)
        return await _decorate(
            event, self._participants, self._reactions, viewer_account_id=viewer_account_id
        )

    async def _ensure_can_view(self, event: Event, viewer_account_id: UUID) -> None:
        """La visibilité suit la portée : plateforme ouverte ; église → membre de l'église ;
        voisinage → membre d'une église à portée ; dénomination → membre du même corps.

        Le `else` valait « dénomination » tant qu'il n'existait que trois portées. Ajouter
        `NEARBY` sans toucher à cette branche aurait fait juger un événement de voisinage sur la
        dénomination de son auteur — donc invisible pour précisément ceux qu'il vise."""
        if event.scope is EventScope.PLATFORM:
            return
        if event.scope is EventScope.CHURCH:
            if await self._memberships.get_active(viewer_account_id, event.tenant_id) is not None:
                return
        elif event.scope is EventScope.NEARBY:
            if event.latitude is not None:
                near = set(
                    await self._audience.tenants_near(
                        latitude=event.latitude,
                        longitude=event.longitude,
                        radius_km=NEARBY_RADIUS_KM,
                    )
                )
                mine = {
                    m.tenant_id
                    for m in await self._memberships.list_active_by_account(viewer_account_id)
                }
                if mine & near:
                    return
        else:  # DENOMINATION
            denomination = await self._audience.denomination_of(event.tenant_id)
            if denomination is not None:
                peers = set(await self._audience.tenants_in_denomination(denomination))
                mine = {
                    m.tenant_id
                    for m in await self._memberships.list_active_by_account(viewer_account_id)
                }
                if mine & peers:
                    return
        raise NotAChurchMemberError(
            "Cet événement n'est pas visible depuis votre église.",
            details={"event_id": str(event.id)},
        )


class ListParticipants:
    def __init__(
        self, events: EventRepository, participants: EventParticipantRepository
    ) -> None:
        self._events = events
        self._participants = participants

    async def execute(
        self, *, actor_account_id: UUID, event_id: UUID
    ) -> list[ParticipantDTO]:
        event = await self._events.get(event_id)
        if event is None:
            raise EventNotFoundError(
                "Événement introuvable.", details={"event_id": str(event_id)}
            )
        if event.author_account_id != actor_account_id:
            raise NotEventAuthorError(
                "Seul l'organisateur voit la liste des participants.",
                details={"event_id": str(event_id)},
            )
        rows = await self._participants.list_by_event(event_id)
        rows.sort(key=lambda p: p.confirmed_at)
        return [to_participant_dto(p) for p in rows]
