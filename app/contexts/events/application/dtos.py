"""DTO applicatifs du module Event."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class EventDTO:
    id: UUID
    author_account_id: UUID
    category: str
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime | None
    place_label: str | None
    latitude: float | None
    longitude: float | None
    media_urls: list[str]
    # La couverture, à plat : ce qu'on voit **avant** d'ouvrir. `None` = pas de
    # couverture, et c'est un cas légitime — le client affiche alors le titre.
    cover_kind: str | None
    cover_url: str | None
    cover_text: str | None
    scope: str
    status: str
    created_at: datetime
    # **Non divulgué au public** : `Event` n'a pas de capacité, donc ce nombre n'aurait aucun
    # dénominateur — « 24 confirmés » est un nombre nu, comparable d'un événement à l'autre,
    # donc un score. Il reste servi à l'organisateur par `/stats`, où il éclaire au lieu de
    # classer. Le jour où la billetterie apportera une capacité, il pourra revenir sous forme
    # de fraction — « 24 / 80 » se lit *reste-t-il une place*, ce qui est de la capacité.
    participant_count: int | None
    my_reaction: str | None = None  # ma réaction (si je suis le lecteur)
    i_confirmed: bool = False  # ai-je confirmé ma présence ?


@dataclass(frozen=True)
class ParticipantDTO:
    """Un confirmé — servi seulement à l'organisateur (la liste des présents)."""

    account_id: UUID
    confirmed_at: datetime


@dataclass(frozen=True)
class ReportedEventDTO:
    """Un événement signalé, pour la file de revue de la Plateforme."""

    id: UUID
    tenant_id: UUID
    author_account_id: UUID
    title: str
    scope: str
    status: str
    starts_at: datetime
    report_count: int


@dataclass(frozen=True)
class EventStatsDTO:
    """Le tableau de bord de rayonnement — réservé à l'organisateur."""

    reach: int  # l'audience potentielle (membres de l'église, pour la portée « église »)
    views_total: int  # les spectateurs distincts
    views_by_denomination: dict[str, int]  # les vues ventilées par dénomination
    interested_count: int  # ceux qui ont manifesté de l'intérêt (réaction « ça m'intéresse »)
    confirmed_count: int  # les présences confirmées
    reaction_counts: dict[str, int]  # toutes les réactions par type
