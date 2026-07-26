"""Use cases de publication (M8) — trois portées, deux autorités.

- `PublishAnnouncement` — dans une **église** : un `group_leader` publie dans **sa** portée (son
  groupe + sous-arbre), un Admin/Owner publie **église-entière**. Autorité `PUBLISH_ANNOUNCEMENT`
  via `GroupAccessPolicy` (mobile *et* backoffice partagent ce cœur).
- `PublishPlatformAnnouncement` — **Dorea, admin central** : atteint **toutes** les églises.
  Autorité = **jeton de service Plateforme** (garde à la route) ; l'auteur est le compte système.

Le **type** pilote (couleur, emojis, intention par défaut) ; l'intention reste surchargeable.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.announcements.application.dtos import AnnouncementDTO
from app.contexts.announcements.application.mapping import to_announcement_dto
from app.contexts.announcements.application.ports import MemberDirectoryPort
from app.contexts.announcements.application.watch_effects import EmitAnnouncementFacts
from app.contexts.announcements.domain.aggregates import (
    Announcement,
    AnnouncementSubject,
    SubjectDraft,
    attach_subjects,
)
from app.contexts.announcements.domain.enums import AnnouncementCategory, AnnouncementIntent
from app.contexts.announcements.domain.repositories import (
    AnnouncementRepository,
    AnnouncementSubjectRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission
from app.contexts.notifications.application.notifier import (
    NotificationScheduler,
    Notifier,
    PushNotification,
)


class PublishAnnouncement:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        members: MemberDirectoryPort | None = None,
        notifier: Notifier | None = None,
        scheduler: NotificationScheduler | None = None,
        subjects: AnnouncementSubjectRepository | None = None,
        watch_effects: EmitAnnouncementFacts | None = None,
        *,
        clock,
    ) -> None:
        self._announcements = announcements
        self._groups = groups
        self._access = access
        self._members = members
        self._notifier = notifier
        self._scheduler = scheduler
        self._subjects = subjects
        self._watch_effects = watch_effects
        self._clock = clock

    async def _notify(self, announcement: Announcement) -> None:
        """Prévenir (best-effort) : la personne concernée, puis le broadcast selon la portée.
        Église-entière → envoi synchrone ; portée groupe → **enqueue** dans l'outbox (le sous-arbre
        peut être large ; résolu ici, dispatché hors requête)."""
        concerns = announcement.concerns_account_id
        if self._notifier is not None and concerns is not None:
            await self._notifier.notify(
                [concerns],
                PushNotification(
                    title=announcement.title,
                    body="Une annonce vous concerne.",
                    data={"type": "announcement", "id": str(announcement.id)},
                ),
            )
        if self._members is None:
            return
        broadcast = PushNotification(
            title="Nouvelle annonce",
            body=announcement.title,
            data={"type": "announcement", "id": str(announcement.id)},
        )
        if announcement.scope_group_id is None:
            if self._notifier is None:
                return
            accounts = await self._members.member_account_ids(announcement.tenant_id)
            await self._notifier.notify(self._targets(accounts, announcement, concerns), broadcast)
        else:
            if self._scheduler is None:
                return
            accounts = await self._members.member_account_ids_in_subtree(
                announcement.tenant_id, announcement.scope_group_id
            )
            await self._scheduler.schedule(
                self._targets(accounts, announcement, concerns), broadcast, at=self._clock()
            )

    @staticmethod
    def _targets(accounts, announcement: Announcement, concerns) -> list[UUID]:
        return [a for a in accounts if a != announcement.author_account_id and a != concerns]

    async def _ask_consent(
        self, announcement: Announcement, subjects: list[AnnouncementSubject]
    ) -> None:
        """L'annonce est retenue : on ne prévient **que** ceux dont on attend l'accord.

        L'église n'apprend rien tant que l'intéressé n'a pas dit oui — c'est tout l'intérêt."""
        if self._notifier is None:
            return
        awaiting = [s.account_id for s in subjects if s.awaits_consent]
        if not awaiting:
            return
        await self._notifier.notify(
            awaiting,
            PushNotification(
                title="Une annonce vous concerne",
                body="Acceptez-vous qu'elle soit publiée ?",
                data={"type": "announcement_consent", "id": str(announcement.id)},
            ),
        )

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        category: AnnouncementCategory,
        title: str,
        scope_group_id: UUID | None = None,
        intent: AnnouncementIntent | None = None,
        concerns_account_id: UUID | None = None,
        body: str | None = None,
        media_urls: list[str] | None = None,
        event_at: datetime | None = None,
        gathering_id: UUID | None = None,
        slots_needed: int | None = None,
        expires_at: datetime | None = None,
        occurred_at: datetime | None = None,
        subjects: Sequence[SubjectDraft] = (),
    ) -> AnnouncementDTO:
        if scope_group_id is None:
            # Église-entière → autorité pastorale sur toute l'église (Admin/Owner, la secrétaire).
            await self._access.ensure_church_wide(
                actor_account_id=actor_account_id,
                tenant_id=tenant_id,
                permission=Permission.PUBLISH_ANNOUNCEMENT,
            )
        else:
            # Portée groupe → le responsable est borné à SON sous-arbre.
            group = await load_group_in_tenant(self._groups, scope_group_id, tenant_id)
            await self._access.ensure_can(
                actor_account_id=actor_account_id,
                group=group,
                permission=Permission.PUBLISH_ANNOUNCEMENT,
            )

        now = self._clock()
        announcement = Announcement.publish(
            id=uuid4(),
            tenant_id=tenant_id,
            category=category,
            intent=intent,
            scope_group_id=scope_group_id,
            title=title,
            body=body,
            author_account_id=actor_account_id,
            concerns_account_id=concerns_account_id,
            now=now,
            event_at=event_at,
            gathering_id=gathering_id,
            slots_needed=slots_needed,
            media_urls=media_urls,
            expires_at=expires_at,
            occurred_at=occurred_at,
        )
        # Rattacher les sujets **avant** d'écrire : c'est ce qui peut retenir l'annonce hors du
        # fil (accord attendu) et désigner qui reçoit la consolation.
        attached = attach_subjects(announcement, list(subjects), now=now)

        await self._announcements.add(announcement)
        if attached and self._subjects is not None:
            await self._subjects.add_all(attached)

        if announcement.is_pending_consent:
            await self._ask_consent(announcement, attached)
        else:
            if self._watch_effects is not None:
                await self._watch_effects.execute(
                    announcement=announcement, subjects=attached
                )
            await self._notify(announcement)

        return to_announcement_dto(
            announcement,
            viewer_account_id=actor_account_id,
            reveal_identity=True,
            subject_account_ids={s.account_id for s in attached},
        )


class PublishPlatformAnnouncement:
    """Annonce **Dorea** (admin central) → toutes les églises.

    Garde : jeton de service Plateforme."""

    def __init__(
        self,
        announcements: AnnouncementRepository,
        *,
        platform_account_id: UUID,
        clock,
    ) -> None:
        self._announcements = announcements
        self._platform_account_id = platform_account_id
        self._clock = clock

    async def execute(
        self,
        *,
        category: AnnouncementCategory,
        title: str,
        intent: AnnouncementIntent | None = None,
        body: str | None = None,
        media_urls: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> AnnouncementDTO:
        announcement = Announcement.publish(
            id=uuid4(),
            tenant_id=None,  # plateforme : n'appartient à aucune église
            category=category,
            intent=intent,
            scope_group_id=None,
            title=title,
            body=body,
            author_account_id=self._platform_account_id,
            now=self._clock(),
            media_urls=media_urls,
            expires_at=expires_at,
        )
        await self._announcements.add(announcement)
        return to_announcement_dto(
            announcement,
            viewer_account_id=self._platform_account_id,
            reveal_identity=True,
        )
