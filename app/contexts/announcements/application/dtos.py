"""DTO applicatifs du contexte Annonces — la carte du fil d'actualité."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AnnouncementDTO:
    id: UUID
    tenant_id: UUID | None  # None = annonce plateforme (Dorea)
    scope: str  # platform | church | group
    category: str  # death | birth | wedding | … (le sujet)
    tone: str  # mourning | joy | celebration | … (la couleur, clé sémantique)
    intent: str  # inform | convene | mobilize | pray (la mécanique)
    scope_group_id: UUID | None
    title: str
    body: str | None
    media_urls: list[str]
    # --- l'identité est *dé-identifiée* dans le fil (l'Église parle, pas la personne) ---
    author_account_id: UUID | None  # None dans le fil ; révélé au backoffice (redevabilité)
    concerns_account_id: UUID | None  # idem : None dans le fil, révélé au backoffice
    concerns_me: bool  # « ceci vous concerne » — le sujet le sait sans exposer son id à tous
    published_at: datetime
    expires_at: datetime | None
    status: str
    occurred_at: datetime | None  # quand c'est arrivé (≠ publication, ≠ convocation)
    event_at: datetime | None
    gathering_id: UUID | None
    slots_needed: int | None  # None sur une mobilisation **sans plafond** (la veillée)
    # --- l'engagement se compte **quand il a un dénominateur** ---
    #
    # Un compteur public n'est légitime que s'il a un dénominateur. « 12 / 15 places » ne se lit
    # pas comme une popularité : ça se lit *reste-t-il une place*, et sans ce nombre le membre ne
    # peut pas décider — c'est de la capacité. « 24 confirmés » et « 32 portent » sont des nombres
    # nus, donc comparables d'une annonce à l'autre, donc des scores. Et « 32 personnes portent »
    # sur une annonce de décès a déjà son destinataire légitime : la famille, par `GetConsolation`.
    accepts_engagement: bool
    engagement_count: int | None  # None = **non divulgué** (voir `ConsolationDTO`)
    engaged: bool  # le membre courant s'est-il engagé ?
    slots_remaining: int | None  # None si sans plafond
    invitation: str | None  # le geste vers lequel le clic ouvre (None si déjà engagé / inform)
    # --- la réaction NE SE COMPTE PAS en public : c'est de l'affection ---
    allowed_emojis: list[str]  # la palette du type
    my_reaction: str | None  # mon emoji (je dois savoir que j'ai réagi)
    reaction_counts: dict[str, int] | None  # None = **non divulgué** (voir ConsolationDTO)


@dataclass(frozen=True)
class ConsolationDTO:
    """Ce que reçoit **le sujet** de l'annonce — jamais l'auteur, jamais le fil.

    « 32 personnes portent votre famille. » Le décompte existe, mais il est **remis à qui il
    console**, pas exposé comme un score."""

    announcement_id: UUID
    title: str
    total: int  # combien de personnes, tous emojis confondus
    reaction_counts: dict[str, int]
    engagement_count: int  # combien viennent réellement (veillée, accompagnement)


@dataclass(frozen=True)
class AnnouncementFeedDTO:
    tenant_id: UUID
    count: int
    announcements: list[AnnouncementDTO]  # plus récentes d'abord
    next_before: datetime | None  # curseur de pagination (None = fin du fil)


@dataclass(frozen=True)
class ResponderDTO:
    account_id: UUID
    responded_at: datetime


@dataclass(frozen=True)
class ResponderListDTO:
    announcement_id: UUID
    count: int
    responders: list[ResponderDTO]  # les noms — auteur / responsable de la portée
