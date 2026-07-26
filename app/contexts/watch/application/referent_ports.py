"""Ce que la résolution du référent a besoin de savoir du reste du produit.

Trois questions, trois ports. Le moteur ne connaît ni les tables de Groupes, ni celles d'IAM,
ni celles de Mission — il demande, un adaptateur répond.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.contexts.watch.domain.referent import (
    GroupTypePolicy,
    MembershipCandidate,
    PrimaryGroupOverride,
    ReferentHistoryEntry,
    ReferentOverride,
)


class GroupDirectory(ABC):
    """Les appartenances, et qui mène quoi."""

    @abstractmethod
    async def active_memberships(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[MembershipCandidate]: ...

    @abstractmethod
    async def active_leader_of(self, group_id: UUID, tenant_id: UUID) -> UUID | None:
        """Le responsable actif d'un groupe, ou None — **pointeur calculé, jamais stocké**.

        C'est ce qui fait que remplacer Jean par Paul change le référent de dix-huit personnes
        sans une seule écriture, tout en laissant leur histoire relationnelle attachée à elles."""
        ...


class PeopleDirectory(ABC):
    """L'éligibilité d'un candidat référent."""

    @abstractmethod
    async def is_eligible(self, account_id: UUID, tenant_id: UUID) -> bool:
        """Compte actif, appartenance vivante, pas retiré de la veille.

        Un référent inéligible ne bloque pas : la cascade continue sous lui."""
        ...

    @abstractmethod
    async def church_admin(self, tenant_id: UUID) -> UUID | None: ...

    @abstractmethod
    async def pastor(self, tenant_id: UUID) -> UUID | None: ...


class InviterDirectory(ABC):
    """Qui a fait entrer cette personne — pertinent pour visiteurs et sympathisants."""

    @abstractmethod
    async def inviter_of(self, account_id: UUID, tenant_id: UUID) -> UUID | None: ...


class GroupTypePolicyRepository(ABC):
    """La politique de veille par type de groupe — **en table**, jamais en dur."""

    @abstractmethod
    async def all_for(self, tenant_id: UUID) -> dict[str, GroupTypePolicy]: ...


class ReferentOverrideRepository(ABC):
    @abstractmethod
    async def add(self, override: ReferentOverride) -> None: ...

    @abstractmethod
    async def save(self, override: ReferentOverride) -> None: ...

    @abstractmethod
    async def active_for(
        self, person_id: UUID, tenant_id: UUID
    ) -> list[ReferentOverride]:
        """Tous les overrides actifs d'une personne, toutes origines — la cascade trie."""
        ...


class PrimaryGroupOverrideRepository(ABC):
    @abstractmethod
    async def add(self, override: PrimaryGroupOverride) -> None: ...

    @abstractmethod
    async def active_for(
        self, person_id: UUID, tenant_id: UUID
    ) -> PrimaryGroupOverride | None: ...


class ReferentHistoryRepository(ABC):
    """Append-only : aucune méthode ne modifie ni ne supprime une entrée."""

    @abstractmethod
    async def append(self, entry: ReferentHistoryEntry) -> None: ...

    @abstractmethod
    async def last_for(
        self, person_id: UUID, tenant_id: UUID, *, before: datetime | None = None
    ) -> ReferentHistoryEntry | None: ...
