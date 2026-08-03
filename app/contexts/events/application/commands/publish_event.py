"""Use cases **auteur** de l'événement — publier, annuler.

`PublishEvent` — tout **membre actif** publie un événement pour son église. Au-delà, il faut
**deux clés** : le compte Business de la personne (le droit de payer) et le mandat de son église
(le droit de parler au nom d'un corps). Un seul verrou portait les deux significations, et
n'importe quel membre diffusait à toute sa dénomination en enregistrant une carte.

`CancelEvent` — l'auteur seul annule.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.contexts.events.application.dtos import EventDTO
from app.contexts.events.application.mapping import to_event_dto
from app.contexts.events.application.ports import BusinessTierPort, EventAudiencePort
from app.contexts.events.domain.aggregates import (
    FREE_SCOPES,
    PUBLICATION_COOLDOWN_DAYS,
    Event,
    EventCover,
)
from app.contexts.events.domain.enums import EventCategory, EventScope
from app.contexts.events.domain.errors import (
    EventNotFoundError,
    NotAChurchMemberError,
    NotEventAuthorError,
    PublicationCadenceError,
    WiderReachRequiresMandateError,
)
from app.contexts.events.domain.repositories import (
    EventParticipantRepository,
    EventRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.notifications.application.notifier import (
    NotificationScheduler,
    Notifier,
    PushNotification,
)
from app.contexts.watch.domain.signal import spoken_date


class PublishEvent:
    def __init__(
        self,
        events: EventRepository,
        memberships: MembershipRepository,
        business: BusinessTierPort,
        access: GroupAccessPolicy | None = None,
        audience: EventAudiencePort | None = None,
        notifier: Notifier | None = None,
        scheduler: NotificationScheduler | None = None,
        *,
        clock,
    ) -> None:
        self._events = events
        self._memberships = memberships
        self._business = business
        # **Deux clés, pas une.** Le compte Business est le droit de payer ; le mandat est le
        # droit de parler au nom d'un corps. Un seul verrou portait les deux significations.
        self._access = access
        self._audience = audience
        self._notifier = notifier
        self._scheduler = scheduler
        self._clock = clock

    async def _broadcast(self, event: Event) -> None:
        """Prévenir l'audience atteinte (best-effort). Église/dénomination : envoi synchrone.
        Plateforme : audience trop large → **enqueue** dans l'outbox (dispatché hors requête).

        **Le voisinage ne pousse rien au-delà de l'église de l'auteur**, et c'est le cœur du
        compromis. Rayonner et déranger sont deux choses différentes : les membres de Shalom
        verront l'événement en ouvrant Dorea, personne ne verra son téléphone s'allumer. C'est ce
        qui permet à cette portée d'être gratuite *et* sans mandat — un membre ordinaire ne peut
        pas faire sonner six cents téléphones dans des églises qui ne sont pas la sienne.
        """
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
        if event.scope in (EventScope.CHURCH, EventScope.NEARBY):
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

    async def _ensure_mandate(
        self, actor_account_id: UUID, tenant_id: UUID, scope: EventScope
    ) -> None:
        """Le **mandat** : le droit de parler au nom d'un corps, distinct du droit de payer.

        Sans lui, n'importe quel membre actif diffusait à toute sa dénomination en enregistrant
        une carte — la légitimité invoquée était institutionnelle, le porteur du droit individuel.
        L'argument à donner au pasteur n'est pas bureaucratique : *si un de tes membres diffuse une
        bêtise à toute la dénomination, c'est ton église qu'on blâmera, pas lui.*

        Attribué par défaut à l'Owner, au Pasteur et à l'Admin — les voix qui engagent
        l'institution. Un responsable de jeunesse qui veut une conférence dénominationnelle passe
        par son pasteur : c'est le geste ecclésial normal.
        """
        if self._access is None:
            return
        try:
            await self._access.ensure_church_wide(
                actor_account_id=actor_account_id,
                tenant_id=tenant_id,
                permission=Permission.BROADCAST_WIDER,
            )
        except UnauthorizedGroupActionError as refused:
            raise WiderReachRequiresMandateError(
                "Diffuser au-delà de votre église engage l'église elle-même : demandez le "
                "mandat à votre pasteur.",
                details={"scope": scope.value},
            ) from refused

    async def _ensure_cadence(self, actor_account_id: UUID, tenant_id: UUID) -> None:
        """**Un événement par semaine et par personne.**

        Publier fait sonner tous les téléphones de l'église. C'était le seul geste du produit
        qu'un compte sans aucun rôle pouvait répéter sans limite — cinq publications d'affilée,
        cinq notifications à quarante personnes en quelques secondes. Le moteur de veille borne
        déjà ses propres sorties pour exactement cette raison.

        Le refus dit **quand** on pourra publier de nouveau : sans échéance, il se lit comme une
        panne et on réessaie. Et ce qui est refusé, c'est la *publication* — le lien de
        l'événement en cours reste partageable autant qu'on veut, hors de Dorea.
        """
        last = await self._events.last_published_at_by(actor_account_id, tenant_id)
        if last is None:
            return
        libre_le = last + timedelta(days=PUBLICATION_COOLDOWN_DAYS)
        if self._clock() >= libre_le:
            return
        raise PublicationCadenceError(
            f"Vous avez déjà annoncé un événement cette semaine. Vous pourrez en publier un "
            f"autre à partir du {spoken_date(libre_le)}. D'ici là, partagez le lien du vôtre.",
            details={"next_publication_at": libre_le.isoformat()},
        )

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
        cover: EventCover | None = None,
    ) -> EventDTO:
        if await self._memberships.get_active(actor_account_id, tenant_id) is None:
            raise NotAChurchMemberError(
                "Rejoignez d'abord cette église pour y publier un événement.",
                details={"tenant_id": str(tenant_id)},
            )
        await self._ensure_cadence(actor_account_id, tenant_id)
        # La porte du rayonnement : au-delà de l'église, il faut le compte Business de l'auteur
        # **et** le mandat de son église.
        #
        # `NEARBY` ne franchit ni l'une ni l'autre. Elle n'engage pas l'institution — elle ne
        # parle au nom de personne, elle dit « il se passe ça, ici » — et elle ne pousse aucune
        # notification hors de l'église de l'auteur. Exiger le mandat pour un repas de quartier
        # aurait reconduit exactement le blocage qu'elle existe pour lever.
        needs_keys = scope not in FREE_SCOPES
        business_active = needs_keys and await self._business.is_business(actor_account_id)
        if needs_keys:
            await self._ensure_mandate(actor_account_id, tenant_id, scope)
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
            cover=cover,
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
