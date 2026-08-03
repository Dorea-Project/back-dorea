"""Agrégats du module Event : `Event`, `EventParticipant`, `EventReaction`.

L'**événement** est un happening publié (date + lieu) auquel les membres **réagissent** (signal
léger) et **confirment leur présence** (RSVP « je serai là »). En E-0, seule la portée **église**
est publiable ; les portées plus larges (dénomination, plateforme) viendront avec le Business.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.events.domain.enums import (
    CoverKind,
    EventCategory,
    EventReaction,
    EventScope,
    EventStatus,
)
from app.contexts.events.domain.errors import (
    EventCancelledError,
    EventTakenDownError,
    InvalidEventError,
    WiderReachRequiresBusinessError,
)

# **Le rayon du voisinage, fixé par le produit — jamais par le publicateur.**
#
# C'est le point de sûreté de cette portée. Un rayon choisi à la publication serait une porte
# dérobée : « autour de moi, dans 20 000 km » atteindrait toute la plateforme sans le compte
# Business ni le mandat de l'église. Le publicateur choisit *où* a lieu son événement ; le produit
# décide *jusqu'où* « autour » veut dire quelque chose.
#
# 10 km est un pari, comme les seuils du moteur de veille : à Abidjan c'est la commune et ses
# voisines, en zone rurale c'est plusieurs villages. À calibrer au pilote, pas à deviner ici.
NEARBY_RADIUS_KM = 10.0

# Une couverture en texte est une **phrase**, pas un paragraphe : elle doit tenir sur une carte,
# lisible d'un coup d'œil dans un fil. Au-delà, ce n'est plus une couverture, c'est la description
# — qui existe déjà et vit juste en dessous.
MAX_COVER_TEXT = 140


@dataclass(frozen=True)
class EventCover:
    """La couverture — **une seule**, et d'une seule sorte.

    Un événement n'a pas trois visages. Porter à la fois une image et un texte obligerait chaque
    client à trancher lequel afficher, et deux clients trancheraient différemment : la même
    soirée n'aurait pas la même tête sur deux téléphones.

    `media_urls` reste à côté pour la galerie. La couverture est ce qu'on voit **avant** d'ouvrir.
    """

    kind: CoverKind
    url: str | None = None
    text: str | None = None

    def __post_init__(self) -> None:
        if self.kind is CoverKind.TEXT:
            phrase = (self.text or "").strip()
            if not phrase:
                raise InvalidEventError("Une couverture texte demande un texte.")
            if len(phrase) > MAX_COVER_TEXT:
                raise InvalidEventError(
                    f"Une couverture texte tient en {MAX_COVER_TEXT} caractères.",
                    details={"length": len(phrase), "max": MAX_COVER_TEXT},
                )
            if self.url:
                raise InvalidEventError("Une couverture texte ne porte pas de fichier.")
        else:
            if not (self.url or "").strip():
                raise InvalidEventError(
                    "Une couverture image ou vidéo demande son fichier.",
                    details={"kind": self.kind.value},
                )
            if self.text:
                raise InvalidEventError(
                    "Une couverture image ou vidéo ne porte pas de texte."
                )


# **La cadence de publication.** Une semaine entre deux événements d'une même personne.
#
# Publier n'est pas un geste anodin : ça fait sonner tous les téléphones de l'église. Le moteur de
# veille borne déjà ses propres sorties (`CHECK_BURST_CAP`) avec cette justification — « le
# responsable ouvre l'application sur cinquante lignes et n'ouvre plus rien du tout ». Events était
# le seul endroit du produit où un compte sans aucun rôle déclenchait une diffusion à toute
# l'église, autant de fois qu'il le voulait.
#
# Sept jours, parce que c'est le rythme de l'Église : on annonce ce qu'on annonce le dimanche.
PUBLICATION_COOLDOWN_DAYS = 7

# Ce qui n'exige pas le compte Business : mon église, et le voisinage de mon événement.
FREE_SCOPES: frozenset[EventScope] = frozenset(
    {EventScope.CHURCH, EventScope.NEARBY}
)


class Event(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        author_account_id: UUID,
        category: EventCategory,
        title: str,
        description: str | None,
        starts_at: datetime,
        ends_at: datetime | None,
        place_label: str | None,
        latitude: float | None,
        longitude: float | None,
        media_urls: list[str] | None,
        scope: EventScope,
        status: EventStatus,
        created_at: datetime,
        cover: EventCover | None = None,
        moderation_reason: str | None = None,
        taken_down_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.author_account_id = author_account_id
        self.category = category
        self.title = title
        self.description = description
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.place_label = place_label
        self.latitude = latitude
        self.longitude = longitude
        self.media_urls = media_urls or []
        # Ce qu'on voit **avant** d'ouvrir. `media_urls` reste la galerie de dedans.
        self.cover = cover
        self.scope = scope
        self.status = status
        self.created_at = created_at
        self.moderation_reason = moderation_reason
        self.taken_down_at = taken_down_at

    @classmethod
    def publish(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        author_account_id: UUID,
        category: EventCategory,
        title: str,
        starts_at: datetime,
        now: datetime,
        scope: EventScope = EventScope.CHURCH,
        description: str | None = None,
        ends_at: datetime | None = None,
        place_label: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        media_urls: list[str] | None = None,
        cover: EventCover | None = None,
        business_active: bool = False,
    ) -> Event:
        title = title.strip()
        if not title:
            raise InvalidEventError("Le titre de l'événement est requis.")
        if (latitude is None) != (longitude is None):
            raise InvalidEventError("La géolocalisation exige latitude ET longitude.")
        if ends_at is not None and ends_at < starts_at:
            raise InvalidEventError("La fin ne peut pas précéder le début.")
        # **« Autour » exige un « ici ».** Une portée de voisinage sans coordonnées n'a aucun
        # centre : elle ne désignerait aucune église, et l'auteur croirait rayonner.
        if scope is EventScope.NEARBY and latitude is None:
            raise InvalidEventError(
                "Toucher les églises voisines demande le lieu de l'événement "
                "(latitude et longitude)."
            )
        # E-0 : au-delà de l'église, il faut le compte Business (le rayonnement institutionnel).
        # `NEARBY` en est exempte : le voisinage n'est pas une institution, c'est le corps local
        # élargi — faire payer un repas de quartier serait taxer ce qu'on veut encourager.
        if scope not in FREE_SCOPES and not business_active:
            raise WiderReachRequiresBusinessError(
                "Rayonner au-delà de ton église arrive avec le compte Business.",
                details={"scope": scope.value},
            )
        return cls(
            id=id,
            tenant_id=tenant_id,
            author_account_id=author_account_id,
            category=category,
            title=title,
            description=(description.strip() or None) if description else None,
            starts_at=starts_at,
            ends_at=ends_at,
            place_label=place_label,
            latitude=latitude,
            longitude=longitude,
            media_urls=media_urls,
            cover=cover,
            scope=scope,
            status=EventStatus.PUBLISHED,
            created_at=now,
        )

    @property
    def is_published(self) -> bool:
        return self.status is EventStatus.PUBLISHED

    def ends_on(self) -> datetime:
        """Quand cet événement cesse d'être à venir.

        `ends_at` quand l'organisateur l'a donné ; sinon **la fin de la journée** de `starts_at`.
        Prendre `starts_at` seul ferait disparaître du fil un repas de 18 h à 18 h 01, pendant que
        les gens s'y rendent. Une journée est la plus petite unité qu'un événement sans heure de
        fin puisse honnêtement revendiquer."""
        if self.ends_at is not None:
            return self.ends_at
        return self.starts_at.replace(hour=23, minute=59, second=59, microsecond=0)

    def is_over(self, now: datetime) -> bool:
        return self.ends_on() < now

    def ensure_live(self) -> None:
        if self.status is EventStatus.CANCELLED:
            raise EventCancelledError(
                "Cet événement a été annulé.", details={"event_id": str(self.id)}
            )
        if self.status is EventStatus.TAKEN_DOWN:
            raise EventTakenDownError(
                "Cet événement a été retiré.", details={"event_id": str(self.id)}
            )

    def cancel(self) -> None:
        self.status = EventStatus.CANCELLED

    def take_down(self, *, reason: str | None, now: datetime) -> None:
        """Retrait par la modération (Plateforme) — le rayonnement élargi est gouverné."""
        if self.status is not EventStatus.PUBLISHED:
            raise EventTakenDownError(
                "Cet événement n'est plus publié.",
                details={"event_id": str(self.id), "status": self.status.value},
            )
        self.status = EventStatus.TAKEN_DOWN
        self.moderation_reason = (reason.strip() or None) if reason else None
        self.taken_down_at = now


class EventParticipant(AggregateRoot):
    """Un membre qui a **confirmé sa présence** (« je serai là »)."""

    def __init__(
        self,
        *,
        id: UUID,
        event_id: UUID,
        tenant_id: UUID,
        account_id: UUID,
        confirmed_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.event_id = event_id
        self.tenant_id = tenant_id
        self.account_id = account_id
        self.confirmed_at = confirmed_at


class EventView(AggregateRoot):
    """Une **vue** distincte de l'événement — qui l'a regardé, et de quelle dénomination.

    Sert le tableau de bord de rayonnement (« les vus par dénomination ») : une vue par
    spectateur (distincte), portant la dénomination de son église (None = indépendante)."""

    def __init__(
        self,
        *,
        id: UUID,
        event_id: UUID,
        viewer_account_id: UUID,
        denomination: str | None,
        viewed_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.event_id = event_id
        self.viewer_account_id = viewer_account_id
        self.denomination = denomination
        self.viewed_at = viewed_at


class EventReport(AggregateRoot):
    """Un **signalement** — un membre alerte qu'un événement ne devrait pas rayonner ainsi.

    Le garde-fou de la diffusion élargie : les signalements s'accumulent et remontent à la
    Plateforme, qui décide (retrait) — *révélateur, pas juge* : le signalement éclaire, l'humain
    tranche."""

    def __init__(
        self,
        *,
        id: UUID,
        event_id: UUID,
        reporter_account_id: UUID,
        reason: str | None,
        created_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.event_id = event_id
        self.reporter_account_id = reporter_account_id
        self.reason = reason
        self.created_at = created_at


class EventReactionEntry(AggregateRoot):
    """La réaction d'un membre à l'événement (une par membre, changeable)."""

    def __init__(
        self,
        *,
        id: UUID,
        event_id: UUID,
        account_id: UUID,
        kind: EventReaction,
        reacted_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.event_id = event_id
        self.account_id = account_id
        self.kind = kind
        self.reacted_at = reacted_at
