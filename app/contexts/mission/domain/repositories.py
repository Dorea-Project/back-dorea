"""Ports de persistance du contexte Mission."""

from abc import abstractmethod
from uuid import UUID

from app._shared.domain.repository import Repository
from app.contexts.mission.domain.aggregates import MissionLink, MissionReaction, Seeker
from app.contexts.mission.domain.enums import SeekerReaction


class MissionLinkRepository(Repository):
    @abstractmethod
    async def add(self, link: MissionLink) -> None: ...

    @abstractmethod
    async def get(self, link_id: UUID) -> MissionLink | None: ...

    @abstractmethod
    async def get_by_code(self, code: str) -> MissionLink | None: ...

    @abstractmethod
    async def save(self, link: MissionLink) -> None: ...

    @abstractmethod
    async def get_active_personal(
        self, account_id: UUID, tenant_id: UUID
    ) -> MissionLink | None:
        """Le lien personnel actif d'un membre (un par membre et église — idempotence)."""
        ...

    @abstractmethod
    async def get_active_group(self, group_id: UUID) -> MissionLink | None:
        """Le lien actif d'un groupe (idempotence de la campagne)."""
        ...


class SeekerRepository(Repository):
    @abstractmethod
    async def add(self, seeker: Seeker) -> None: ...

    @abstractmethod
    async def get(self, seeker_id: UUID) -> Seeker | None: ...

    @abstractmethod
    async def save(self, seeker: Seeker) -> None:
        """Persiste une transition (accompagnement / clôture)."""
        ...

    @abstractmethod
    async def list_by_inviter_account(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[Seeker]:
        """Les chercheurs qu'un membre a amenés (« mon fruit »)."""
        ...

    @abstractmethod
    async def list_by_inviter_group(self, group_id: UUID) -> list[Seeker]:
        """Les chercheurs amenés par une campagne de groupe."""
        ...

    @abstractmethod
    async def count_by_link(self, link_id: UUID) -> int: ...


class MissionReactionRepository(Repository):
    @abstractmethod
    async def add(self, reaction: MissionReaction) -> None: ...

    @abstractmethod
    async def counts_by_kind(self, link_id: UUID) -> dict[SeekerReaction, int]:
        """Combien de touché / édifié / Amen sur ce lien (le signal, remis à l'inviteur)."""
        ...
