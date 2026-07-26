"""Port de persistance du module Sermon."""

from abc import abstractmethod
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.sermon.domain.aggregates import Sermon
from app.contexts.sermon.domain.companion import CompanionSession


class SermonRepository(Repository):
    @abstractmethod
    async def add(self, sermon: Sermon) -> None: ...

    @abstractmethod
    async def get(self, sermon_id: UUID) -> Sermon | None: ...

    @abstractmethod
    async def save(self, sermon: Sermon) -> None:
        """Persiste une transition de cycle de vie (approbation, publication)."""
        ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> list[Sermon]:
        """Les sermons de l'église (tous statuts) — la vue du gardien (pasteur/admin)."""
        ...


class CompanionSessionRepository(Repository):
    @abstractmethod
    async def add(self, session: CompanionSession) -> None: ...

    @abstractmethod
    async def get(self, session_id: UUID) -> CompanionSession | None: ...

    @abstractmethod
    async def save(self, session: CompanionSession) -> None: ...

    @abstractmethod
    async def find_active(
        self, member_account_id: UUID, sermon_id: UUID
    ) -> CompanionSession | None:
        """La session en cours d'un membre sur un sermon (pour reprendre au lieu de dupliquer)."""
        ...
