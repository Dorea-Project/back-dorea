"""Agrégats du contexte Annonces (M8) : `Announcement`, `AnnouncementSubject`, engagement, réaction.

Une annonce **porte un type** (le sujet : décès, naissance, mariage…) qui pilote sa **couleur** et
ses **emojis** ; le type donne aussi l'**intention par défaut** (la mécanique du retour), qu'on peut
surcharger. Deux registres de retour, jamais un accusé de lecture (pas de flicage) :
- la **réaction** (emoji de la palette du type) — légère, sur toute annonce ;
- l'**engagement** (« je viens / je sers / je porte ») — structurant, si l'intention le demande.

**Anti-vitrine** : l'**auteur** (qui publie) n'est pas le **sujet** (`concerns_account_id`, de qui
ça parle). Le décompte des réactions ne s'affiche nulle part comme un score : il est **remis au
sujet** (une consolation privée). L'engagement, lui, se compte — c'est de l'organisation.

Trois **portées** dérivées : `platform` (Dorea → toutes les églises), `church`, `group`.

Une annonce peut nommer des **sujets** (`AnnouncementSubject`) : une personne **et le rôle**
qu'elle y tient (défunt, endeuillé, malade…). C'est le rôle — jamais le type — qui décide de
l'effet sur la veille fraternelle (cf. `watch_rules`). Un type qui parle d'une activité refuse
tout sujet, et un rôle intime (la maladie) attend l'accord de l'intéressé avant d'être publié.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app._shared.domain.entity import AggregateRoot
from app.contexts.announcements.domain.category import profile_of
from app.contexts.announcements.domain.enums import (
    AnnouncementCategory,
    AnnouncementIntent,
    AnnouncementScope,
    AnnouncementStatus,
    AnnouncementTone,
    Invitation,
    SubjectConsent,
    SubjectRole,
    WatchEffect,
)
from app.contexts.announcements.domain.errors import (
    ConsentNotPendingError,
    DeclaredDurationRequiredError,
    DuplicateSubjectError,
    EmojiNotAllowedError,
    InvalidAnnouncementError,
    RoleNotProposedError,
    SubjectNotAllowedError,
)
from app.contexts.announcements.domain.watch_rules import (
    accepts_subjects,
    neutralization_window,
    resolve_effects,
    roles_for,
    rule_for,
)

_INVITATION_OF: dict[AnnouncementIntent, Invitation] = {
    AnnouncementIntent.MOBILIZE: Invitation.COME,
    AnnouncementIntent.CONVENE: Invitation.CONFIRM,
    AnnouncementIntent.PRAY: Invitation.REACH_OUT,
}


class Announcement(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID | None,  # None = annonce **plateforme** (Dorea, admin central)
        category: AnnouncementCategory,
        intent: AnnouncementIntent,
        scope_group_id: UUID | None,  # None = église entière ; sinon ce groupe + son sous-arbre
        title: str,
        body: str | None,
        author_account_id: UUID,
        published_at: datetime,
        status: AnnouncementStatus = AnnouncementStatus.PUBLISHED,
        concerns_account_id: UUID | None = None,  # **de qui** ça parle (≠ qui publie)
        event_at: datetime | None = None,  # CONVENE
        gathering_id: UUID | None = None,  # CONVENE — pointeur souple vers une rencontre M6
        slots_needed: int | None = None,  # MOBILIZE — optionnel : None = sans plafond (veillée)
        media_urls: list[str] | None = None,  # images (URL ; l'upload vit ailleurs)
        expires_at: datetime | None = None,  # sortie automatique du fil
        occurred_at: datetime | None = None,  # **quand c'est arrivé** (≠ quand on l'a dit)
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.category = category
        self.intent = intent
        self.scope_group_id = scope_group_id
        self.title = title
        self.body = body
        self.author_account_id = author_account_id
        self.concerns_account_id = concerns_account_id
        self.published_at = published_at
        self.status = status
        self.event_at = event_at
        self.gathering_id = gathering_id
        self.slots_needed = slots_needed
        self.media_urls = media_urls or []
        self.expires_at = expires_at
        self.occurred_at = occurred_at

    @classmethod
    def publish(
        cls,
        *,
        id: UUID,
        tenant_id: UUID | None,
        category: AnnouncementCategory,
        scope_group_id: UUID | None,
        title: str,
        body: str | None,
        author_account_id: UUID,
        now: datetime,
        intent: AnnouncementIntent | None = None,  # absent → dérivée du type
        concerns_account_id: UUID | None = None,
        event_at: datetime | None = None,
        gathering_id: UUID | None = None,
        slots_needed: int | None = None,
        media_urls: list[str] | None = None,
        expires_at: datetime | None = None,
        occurred_at: datetime | None = None,
    ) -> Announcement:
        """Publie : l'intention est dérivée du **type** (surchargeable), la cohérence validée."""
        if not title.strip():
            raise InvalidAnnouncementError("Le titre est requis.")
        resolved = intent if intent is not None else profile_of(category).default_intent

        # Une mobilisation peut être **sans plafond** (on ne plafonne pas une veillée) ; si un
        # nombre de places est donné, il doit avoir un sens.
        if slots_needed is not None and slots_needed < 1:
            raise InvalidAnnouncementError(
                "Un nombre de places doit être >= 1.", details={"slots_needed": slots_needed}
            )
        if resolved is AnnouncementIntent.CONVENE and event_at is None and gathering_id is None:
            raise InvalidAnnouncementError(
                "Convoquer exige une date (event_at) ou une rencontre (gathering_id).",
                details={"intent": resolved.value},
            )
        if tenant_id is None and scope_group_id is not None:
            raise InvalidAnnouncementError(
                "Une annonce plateforme ne peut viser un groupe d'église.",
            )
        if expires_at is not None and expires_at <= now:
            raise InvalidAnnouncementError("La date d'expiration doit être future.")
        # On annonce ce qui **est arrivé**. Une saisie tardive est normale (« il est parti le 12,
        # on l'apprend le 20 ») ; une date future ne l'est pas — et fausserait toutes les durées.
        if occurred_at is not None and occurred_at > now:
            raise InvalidAnnouncementError(
                "La date de l'événement ne peut être future.",
                details={"occurred_at": occurred_at.isoformat()},
            )

        return cls(
            id=id,
            tenant_id=tenant_id,
            category=category,
            intent=resolved,
            scope_group_id=scope_group_id,
            title=title,
            body=body,
            author_account_id=author_account_id,
            concerns_account_id=concerns_account_id,
            published_at=now,
            event_at=event_at if resolved is AnnouncementIntent.CONVENE else None,
            gathering_id=gathering_id if resolved is AnnouncementIntent.CONVENE else None,
            slots_needed=slots_needed if resolved is AnnouncementIntent.MOBILIZE else None,
            media_urls=media_urls,
            expires_at=expires_at,
            occurred_at=occurred_at,
        )

    # --- Type : couleur & emojis ---

    @property
    def tone(self) -> AnnouncementTone:
        return profile_of(self.category).tone

    @property
    def allowed_emojis(self) -> tuple[str, ...]:
        return profile_of(self.category).emojis

    def ensure_emoji_allowed(self, emoji: str) -> None:
        """Palette **fixe suggérée par le type** : pas de 🎉 sur un décès."""
        if emoji not in self.allowed_emojis:
            raise EmojiNotAllowedError(
                "Cet emoji n'est pas proposé pour ce type d'annonce.",
                details={"emoji": emoji, "allowed": list(self.allowed_emojis)},
            )

    # --- Portée ---

    @property
    def scope(self) -> AnnouncementScope:
        if self.tenant_id is None:
            return AnnouncementScope.PLATFORM
        if self.scope_group_id is None:
            return AnnouncementScope.CHURCH
        return AnnouncementScope.GROUP

    def reaches(self, covering_group_ids: set[UUID]) -> bool:
        """Atteint un membre dont la couverture (ancêtres-ou-soi de ses groupes) est donnée.

        Plateforme et église-entière atteignent tout le monde (le dépôt a déjà borné au tenant) ;
        une annonce de groupe n'atteint que son sous-arbre."""
        if self.scope is AnnouncementScope.GROUP:
            return self.scope_group_id in covering_group_ids
        return True

    # --- Datation ---

    @property
    def event_date(self) -> datetime:
        """**La date de référence de la veille** : quand c'est arrivé, pas quand on l'a dit.

        Toutes les durées (neutralisation, épisode) courent depuis là. À défaut de date déclarée,
        la publication fait foi — c'est le mieux qu'on sache."""
        return self.occurred_at or self.published_at

    # --- Cycle de vie ---

    @property
    def is_archived(self) -> bool:
        return self.status is AnnouncementStatus.ARCHIVED

    @property
    def is_pending_consent(self) -> bool:
        return self.status is AnnouncementStatus.PENDING_CONSENT

    @property
    def is_declined(self) -> bool:
        return self.status is AnnouncementStatus.DECLINED

    def is_live(self, now: datetime) -> bool:
        """Dans le fil : publiée **et** non expirée (l'expiration l'en sort toute seule).

        En attente d'un accord ou refusée, elle n'y est pas — l'église n'en sait rien."""
        if self.status is not AnnouncementStatus.PUBLISHED:
            return False
        return self.expires_at is None or self.expires_at > now

    def hold_for_consent(self) -> None:
        """Retient l'annonce hors du fil tant qu'un sujet n'a pas accepté d'être nommé."""
        if self.status is AnnouncementStatus.PUBLISHED:
            self.status = AnnouncementStatus.PENDING_CONSENT

    def release(self) -> None:
        """Tous les accords sont là : l'annonce entre dans le fil."""
        if self.status is AnnouncementStatus.PENDING_CONSENT:
            self.status = AnnouncementStatus.PUBLISHED

    def decline(self) -> None:
        """Un sujet a refusé d'être nommé. Terminal : elle ne paraîtra jamais."""
        self.status = AnnouncementStatus.DECLINED

    @property
    def accepts_engagement(self) -> bool:
        """« Informer » n'attend aucun engagement ; les réactions restent possibles partout."""
        return self.intent is not AnnouncementIntent.INFORM

    @property
    def is_capped(self) -> bool:
        """Une mobilisation plafonnée (3 places) vs sans plafond (la veillée : tout le monde)."""
        return self.slots_needed is not None

    def invitation(self) -> Invitation | None:
        """Le geste plus coûteux vers lequel la réaction ouvre — « le clic n'absout pas ».

        Réagir 🙏 à un décès ne clôt rien : ça invite à **venir** à la veillée. Une intention qui
        n'attend pas d'engagement (« informer ») n'ouvre sur rien."""
        return _INVITATION_OF.get(self.intent)

    def concerns(self, account_id: UUID) -> bool:
        """Ce compte est-il **le sujet** de l'annonce (la famille en deuil, les parents) ?

        C'est à lui — et à lui seul — que revient le décompte des réactions : une consolation,
        pas un score sur le post de celui qui a publié."""
        return (
            self.concerns_account_id is not None and self.concerns_account_id == account_id
        )

    def archive(self) -> None:
        self.status = AnnouncementStatus.ARCHIVED


@dataclass(frozen=True)
class SubjectDraft:
    """Ce que le publicateur propose : qui, à quel titre, et les effets qu'il garde.

    `effects=None` = les effets par défaut du rôle (l'écran les pré-remplit, il peut en décocher).
    """

    account_id: UUID
    role: SubjectRole
    effects: tuple[WatchEffect, ...] | None = None
    declared_duration_days: int | None = None  # « je pars six semaines »


class AnnouncementSubject(AggregateRoot):
    """Une personne nommée dans une annonce **et le rôle qu'elle y tient**.

    Le rôle n'est pas une étiquette d'affichage : c'est lui qui décide de l'effet sur la veille.
    Tant que le consentement reste `PENDING`, le sujet n'existe pour personne — ni au fil, ni
    dans la veille."""

    def __init__(
        self,
        *,
        id: UUID,
        announcement_id: UUID,
        account_id: UUID,
        role: SubjectRole,
        effects: tuple[WatchEffect, ...],
        consent: SubjectConsent,
        attached_at: datetime,
        declared_duration_days: int | None = None,
        consent_decided_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.announcement_id = announcement_id
        self.account_id = account_id
        self.role = role
        self.effects = effects
        self.consent = consent
        self.attached_at = attached_at
        self.declared_duration_days = declared_duration_days
        self.consent_decided_at = consent_decided_at

    @classmethod
    def attach(
        cls, *, announcement: Announcement, draft: SubjectDraft, now: datetime
    ) -> AnnouncementSubject:
        """Rattache un sujet — et **refuse** ce qui n'a pas de sens (garde d'entrée, §A1)."""
        if not accepts_subjects(announcement.category):
            raise SubjectNotAllowedError(
                "Ce type d'annonce parle d'une activité, pas d'une personne.",
                details={"category": announcement.category.value},
            )
        proposed = roles_for(announcement.category)
        if draft.role not in proposed:
            raise RoleNotProposedError(
                "Ce rôle n'est pas proposé par ce type d'annonce.",
                details={
                    "category": announcement.category.value,
                    "role": draft.role.value,
                    "proposed": [r.value for r in proposed],
                },
            )

        effects = resolve_effects(draft.role, draft.effects)

        # Un rôle qui neutralise sur durée déclarée sans durée déclarée ne neutralise rien :
        # on le dit au publicateur au lieu de poser une veille silencieusement vide.
        if WatchEffect.NEUTRALIZATION in effects and (
            neutralization_window(
                draft.role,
                announcement.event_date,
                declared_days=draft.declared_duration_days,
            )
            is None
        ):
            raise DeclaredDurationRequiredError(
                "Ce rôle demande une durée déclarée (jusqu'à quand ?).",
                details={"role": draft.role.value},
            )

        rule = rule_for(draft.role)
        consent = SubjectConsent.PENDING if rule.requires_consent else SubjectConsent.NOT_REQUIRED
        return cls(
            id=uuid4(),
            announcement_id=announcement.id,
            account_id=draft.account_id,
            role=draft.role,
            effects=effects,
            consent=consent,
            attached_at=now,
            declared_duration_days=draft.declared_duration_days,
        )

    # --- Consentement ---

    @property
    def awaits_consent(self) -> bool:
        return self.consent is SubjectConsent.PENDING

    @property
    def is_effective(self) -> bool:
        """Ce sujet compte-t-il — au fil comme dans la veille ?"""
        return self.consent in (SubjectConsent.NOT_REQUIRED, SubjectConsent.GRANTED)

    def grant(self, *, now: datetime) -> None:
        if not self.awaits_consent:
            raise ConsentNotPendingError("Aucun accord n'est attendu sur ce sujet.")
        self.consent = SubjectConsent.GRANTED
        self.consent_decided_at = now

    def refuse(self, *, now: datetime) -> None:
        if not self.awaits_consent:
            raise ConsentNotPendingError("Aucun accord n'est attendu sur ce sujet.")
        self.consent = SubjectConsent.DECLINED
        self.consent_decided_at = now

    # --- Effets ---

    def has(self, effect: WatchEffect) -> bool:
        """Les effets **retenus**, figés au rattachement. Ils voyagent dans le fait ; c'est le
        moteur qui décide ce qu'il en fait, et le ledger qui porte l'idempotence du rejeu."""
        return effect in self.effects


def attach_subjects(
    announcement: Announcement, drafts: Sequence[SubjectDraft], *, now: datetime
) -> list[AnnouncementSubject]:
    """Rattache tous les sujets d'une annonce et **règle son statut** en conséquence.

    Effet de bord assumé sur l'annonce : si un rôle intime attend un accord, elle sort du fil
    jusqu'à l'obtenir. On renseigne aussi `concerns_account_id` (la consolation) à partir du
    premier sujet **vivant** — on n'envoie pas « 32 personnes vous portent » à un défunt.
    """
    if not drafts:
        return []

    seen: set[UUID] = set()
    subjects: list[AnnouncementSubject] = []
    for draft in drafts:
        if draft.account_id in seen:
            raise DuplicateSubjectError(
                "Cette personne est déjà nommée dans cette annonce.",
                details={"account_id": str(draft.account_id)},
            )
        seen.add(draft.account_id)
        subjects.append(AnnouncementSubject.attach(announcement=announcement, draft=draft, now=now))

    if announcement.concerns_account_id is None:
        consoled = next(
            (s for s in subjects if s.role is not SubjectRole.DECEASED), None
        )
        if consoled is not None:
            announcement.concerns_account_id = consoled.account_id

    if any(s.awaits_consent for s in subjects):
        announcement.hold_for_consent()

    return subjects


class AnnouncementEngagement(AggregateRoot):
    """L'engagement structurant : « je viens / je sers / je porte ». Un par (annonce, compte)."""

    def __init__(
        self,
        *,
        id: UUID,
        announcement_id: UUID,
        account_id: UUID,
        responded_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.announcement_id = announcement_id
        self.account_id = account_id
        self.responded_at = responded_at


class AnnouncementReaction(AggregateRoot):
    """Réaction légère : un emoji de la palette du type. Une par (annonce, compte), changeable."""

    def __init__(
        self,
        *,
        id: UUID,
        announcement_id: UUID,
        account_id: UUID,
        emoji: str,
        reacted_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.announcement_id = announcement_id
        self.account_id = account_id
        self.emoji = emoji
        self.reacted_at = reacted_at
