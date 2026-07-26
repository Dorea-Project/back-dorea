"""Ports de persistance du contexte Annonces."""

from abc import abstractmethod
from datetime import datetime
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.announcements.domain.aggregates import (
    Announcement,
    AnnouncementEngagement,
    AnnouncementReaction,
    AnnouncementSubject,
)


class AnnouncementRepository(Repository):
    @abstractmethod
    async def add(self, announcement: Announcement) -> None: ...

    @abstractmethod
    async def get(self, announcement_id: UUID) -> Announcement | None: ...

    @abstractmethod
    async def save(self, announcement: Announcement) -> None:
        """Persiste un état existant (ex. après archivage)."""
        ...

    @abstractmethod
    async def list_feed_candidates(
        self, tenant_id: UUID, *, now: datetime, before: datetime | None, limit: int
    ) -> list[Announcement]:
        """Le fil : annonces **vivantes** de la plateforme **et** de cette église, plus récentes
        d'abord (curseur `before` sur `published_at`). La portée groupe est filtrée ensuite."""
        ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[Announcement]:
        """Toutes les annonces d'une église, y compris archivées (vue backoffice / archive)."""
        ...


class AnnouncementSubjectRepository(Repository):
    """Les personnes nommées dans une annonce et le rôle qu'elles y tiennent."""

    @abstractmethod
    async def add_all(self, subjects: list[AnnouncementSubject]) -> None: ...

    @abstractmethod
    async def get(self, subject_id: UUID) -> AnnouncementSubject | None: ...

    @abstractmethod
    async def save(self, subject: AnnouncementSubject) -> None:
        """Persiste un état existant (accord donné/refusé, effets posés)."""
        ...

    @abstractmethod
    async def list_for(self, announcement_id: UUID) -> list[AnnouncementSubject]: ...

    @abstractmethod
    async def account_ids_among(
        self, account_id: UUID, announcement_ids: list[UUID]
    ) -> set[UUID]:
        """Parmi ces annonces, celles où **ce compte** est nommé (« ceci vous concerne »)."""
        ...


class AnnouncementEngagementRepository(Repository):
    @abstractmethod
    async def add(self, engagement: AnnouncementEngagement) -> None: ...

    @abstractmethod
    async def get(
        self, announcement_id: UUID, account_id: UUID
    ) -> AnnouncementEngagement | None: ...

    @abstractmethod
    async def remove(self, announcement_id: UUID, account_id: UUID) -> None: ...

    @abstractmethod
    async def count_for(self, announcement_id: UUID) -> int: ...

    @abstractmethod
    async def list_for(self, announcement_id: UUID) -> list[AnnouncementEngagement]:
        """Les engagés (les noms — vus de l'auteur / d'un responsable de la portée)."""
        ...

    @abstractmethod
    async def counts_for_many(self, announcement_ids: list[UUID]) -> dict[UUID, int]: ...

    @abstractmethod
    async def engaged_among(
        self, account_id: UUID, announcement_ids: list[UUID]
    ) -> set[UUID]: ...


class AnnouncementReactionRepository(Repository):
    @abstractmethod
    async def set_for(self, reaction: AnnouncementReaction) -> None:
        """Pose ou **remplace** la réaction du compte (une seule par annonce, changeable)."""
        ...

    @abstractmethod
    async def remove(self, announcement_id: UUID, account_id: UUID) -> None: ...

    @abstractmethod
    async def counts_by_emoji(self, announcement_id: UUID) -> dict[str, int]:
        """Compteurs par emoji (vus de tous)."""
        ...

    @abstractmethod
    async def counts_by_emoji_for_many(
        self, announcement_ids: list[UUID]
    ) -> dict[UUID, dict[str, int]]: ...

    @abstractmethod
    async def reactions_of_account_among(
        self, account_id: UUID, announcement_ids: list[UUID]
    ) -> dict[UUID, str]:
        """Mon emoji par annonce (pour afficher ma réaction dans le fil)."""
        ...
