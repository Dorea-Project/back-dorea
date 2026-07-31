"""Schémas HTTP du contexte Annonces (M8) — la carte du fil d'actualité."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.announcements.application.dtos import (
    AnnouncementDTO,
    AnnouncementFeedDTO,
    ConsolationDTO,
    ResponderListDTO,
)
from app.contexts.announcements.domain.enums import (
    AnnouncementCategory,
    AnnouncementIntent,
    SubjectRole,
    WatchEffect,
)


class AnnouncementSubjectRequest(BaseModel):
    """Une personne nommée dans l'annonce **et le rôle qu'elle y tient**.

    C'est le rôle qui décide de l'effet sur la veille — pas le type d'annonce. Un décès porte un
    `deceased` (qui sort de la veille) et des `bereaved` (qu'on entoure)."""

    account_id: UUID
    role: SubjectRole = Field(
        description="deceased | bereaved | sick | new_parent | newlywed | traveler | honoree — "
        "doit faire partie des rôles proposés par le type d'annonce."
    )
    effects: list[WatchEffect] | None = Field(
        default=None,
        description="Surcharge du publicateur : les effets qu'il **garde** parmi ceux du rôle "
        "(pré-remplis au défaut à l'écran). On peut décocher, jamais inventer. Absent = défaut.",
    )
    declared_duration_days: int | None = Field(
        default=None,
        description="« Jusqu'à quand ? » — exigé pour un rôle qui neutralise sur durée déclarée "
        "(le voyageur) ; l'emporte partout ailleurs sur la durée de la règle.",
    )


class PublishAnnouncementRequest(BaseModel):
    category: AnnouncementCategory = Field(
        description="Le sujet : death | birth | wedding | baptism | sickness | travel | service | "
        "meeting | call | prayer | testimony | info. Pilote couleur, emojis, intention par défaut."
    )
    title: str = Field(examples=["Rappel à Dieu de Frère Yao"])
    intent: AnnouncementIntent | None = Field(
        default=None,
        description="Surcharge l'intention par défaut du type (inform | convene | mobilize | pray)",
    )
    scope_group_id: UUID | None = Field(
        default=None, description="Groupe visé (+ son sous-arbre) ; absent = église entière"
    )
    concerns_account_id: UUID | None = Field(
        default=None,
        description="**De qui** ça parle (la famille en deuil, les parents) — ≠ qui publie. "
        "C'est à ce compte que revient le décompte des réactions (consolation privée).",
    )
    body: str | None = Field(default=None)
    media_urls: list[str] | None = Field(default=None, description="Images (URL)")
    event_at: datetime | None = Field(default=None, description="convene : quand")
    gathering_id: UUID | None = Field(
        default=None, description="convene : rencontre M6 liée (optionnel)"
    )
    slots_needed: int | None = Field(default=None, description="mobilize : nombre de places")
    expires_at: datetime | None = Field(
        default=None, description="Sortie automatique du fil (archivage auto)"
    )
    occurred_at: datetime | None = Field(
        default=None,
        description="**Quand c'est arrivé** — pas quand on le dit, ni quand on se réunit. Toutes "
        "les durées de veille courent depuis là. Absent = la publication fait foi.",
    )
    subjects: list[AnnouncementSubjectRequest] = Field(
        default_factory=list,
        description="Les personnes nommées et leur rôle. Refusé sur un type qui parle d'une "
        "activité (culte, appel, info). Un rôle intime (malade) attend l'accord de l'intéressé : "
        "l'annonce est alors retenue hors du fil jusqu'à sa réponse.",
    )


class ConsentRequest(BaseModel):
    """La réponse **du sujet lui-même** — personne ne consent à sa place."""

    accept: bool = Field(description="true = qu'elle soit publiée ; false = refus, définitif")


class PublishPlatformAnnouncementRequest(BaseModel):
    """Annonce **Dorea** (admin central) → toutes les églises. Pas de portée groupe."""

    category: AnnouncementCategory
    title: str = Field(examples=["Nouvelle version de Dorea"])
    intent: AnnouncementIntent | None = Field(default=None)
    body: str | None = Field(default=None)
    media_urls: list[str] | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)


class ReactRequest(BaseModel):
    emoji: str = Field(
        examples=["🙏"], description="Doit appartenir à la palette du type (allowed_emojis)"
    )


class AnnouncementView(BaseModel):
    id: UUID
    tenant_id: UUID | None
    scope: str  # platform | church | group
    category: str
    tone: str  # la couleur (clé sémantique)
    intent: str
    scope_group_id: UUID | None
    title: str
    body: str | None
    media_urls: list[str]
    author_account_id: UUID | None = Field(
        default=None,
        description="**Tu dans le fil** (l'Église parle, pas la personne). Révélé au backoffice.",
    )
    concerns_account_id: UUID | None = None  # révélé au backoffice ; None dans le fil
    concerns_me: bool = Field(
        default=False, description="« Ceci vous concerne » — sans exposer l'identité du sujet"
    )
    published_at: datetime
    expires_at: datetime | None
    status: str = Field(
        description="published | archived | pending_consent (retenue tant qu'un sujet n'a pas "
        "accepté d'être nommé) | declined (un sujet a refusé — elle ne paraîtra pas)"
    )
    occurred_at: datetime | None = Field(
        default=None, description="Quand l'événement est survenu (origine des durées de veille)"
    )
    event_at: datetime | None
    gathering_id: UUID | None
    slots_needed: int | None
    accepts_engagement: bool
    # `None` = non divulgué : un compteur public n'est légitime qu'avec un
    # dénominateur (« 12 / 15 places »). Sans plafond, le nombre est un score.
    engagement_count: int | None
    engaged: bool
    slots_remaining: int | None
    invitation: str | None = Field(
        default=None,
        description="Le geste plus coûteux vers lequel le clic ouvre : come | confirm | reach_out. "
        "Le clic n'absout pas. None une fois engagé, ou si l'annonce n'attend rien.",
    )
    allowed_emojis: list[str]
    my_reaction: str | None
    reaction_counts: dict[str, int] | None = Field(
        default=None,
        description="**Non divulgué dans le fil** (ce serait un score). Rempli seulement pour "
        "le sujet de l'annonce (consolation) et le pilotage pastoral.",
    )

    @classmethod
    def from_dto(cls, dto: AnnouncementDTO) -> AnnouncementView:
        return cls(
            id=dto.id,
            tenant_id=dto.tenant_id,
            scope=dto.scope,
            category=dto.category,
            tone=dto.tone,
            intent=dto.intent,
            scope_group_id=dto.scope_group_id,
            title=dto.title,
            body=dto.body,
            media_urls=dto.media_urls,
            author_account_id=dto.author_account_id,
            concerns_account_id=dto.concerns_account_id,
            concerns_me=dto.concerns_me,
            published_at=dto.published_at,
            expires_at=dto.expires_at,
            status=dto.status,
            occurred_at=dto.occurred_at,
            event_at=dto.event_at,
            gathering_id=dto.gathering_id,
            slots_needed=dto.slots_needed,
            accepts_engagement=dto.accepts_engagement,
            engagement_count=dto.engagement_count,
            engaged=dto.engaged,
            slots_remaining=dto.slots_remaining,
            invitation=dto.invitation,
            allowed_emojis=dto.allowed_emojis,
            my_reaction=dto.my_reaction,
            reaction_counts=dto.reaction_counts,
        )


class AnnouncementFeedView(BaseModel):
    tenant_id: UUID
    count: int
    announcements: list[AnnouncementView]
    next_before: datetime | None = Field(
        default=None, description="Curseur : rappeler avec ?before=… pour la page suivante"
    )

    @classmethod
    def from_dto(cls, dto: AnnouncementFeedDTO) -> AnnouncementFeedView:
        return cls(
            tenant_id=dto.tenant_id,
            count=dto.count,
            announcements=[AnnouncementView.from_dto(a) for a in dto.announcements],
            next_before=dto.next_before,
        )


class ConsolationView(BaseModel):
    """« 32 personnes vous portent » — remis au **sujet**, jamais affiché sur le post."""

    announcement_id: UUID
    title: str
    total: int
    reaction_counts: dict[str, int]
    engagement_count: int

    @classmethod
    def from_dto(cls, dto: ConsolationDTO) -> ConsolationView:
        return cls(
            announcement_id=dto.announcement_id,
            title=dto.title,
            total=dto.total,
            reaction_counts=dto.reaction_counts,
            engagement_count=dto.engagement_count,
        )


class _Responder(BaseModel):
    account_id: UUID
    responded_at: datetime


class ResponderListView(BaseModel):
    announcement_id: UUID
    count: int
    responders: list[_Responder]

    @classmethod
    def from_dto(cls, dto: ResponderListDTO) -> ResponderListView:
        return cls(
            announcement_id=dto.announcement_id,
            count=dto.count,
            responders=[
                _Responder(account_id=r.account_id, responded_at=r.responded_at)
                for r in dto.responders
            ],
        )
