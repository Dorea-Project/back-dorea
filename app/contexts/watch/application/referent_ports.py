"""Ce que la résolution du référent a besoin de savoir du reste du produit.

Trois questions, trois ports. Le moteur ne connaît ni les tables de Groupes, ni celles d'IAM,
ni celles de Mission — il demande, un adaptateur répond.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.parameters import WatchParam
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

    @abstractmethod
    async def pastor_of_branch(self, group_id: UUID, tenant_id: UUID) -> UUID | None:
        """Le pasteur dont dépend ce groupe, en remontant l'arbre — ou None.

        Même logique de pointeur calculé : changer le pasteur d'une annexe rebascule tout son
        monde sans une seule écriture."""
        ...


class PeopleDirectory(ABC):
    """L'éligibilité d'un candidat référent."""

    @abstractmethod
    async def is_eligible(self, account_id: UUID, tenant_id: UUID) -> bool:
        """Compte actif, appartenance vivante, pas retiré de la veille.

        Un référent inéligible ne bloque pas : la cascade continue sous lui."""
        ...

    @abstractmethod
    async def member_since(self, account_id: UUID, tenant_id: UUID) -> datetime | None:
        """Depuis quand cette personne appartient à cette église.

        C'est le repli du trou de couverture : quelqu'un que **personne n'a jamais connu** n'a
        aucune entrée d'historique, et son trou doit malgré tout avoir une durée — sinon elle
        n'a pas de clé de tri et reste en bas de l'écran de couverture indéfiniment."""
        ...

    @abstractmethod
    async def church_admin(self, tenant_id: UUID) -> UUID | None: ...

    @abstractmethod
    async def pastor(self, tenant_id: UUID) -> UUID | None: ...

    @abstractmethod
    async def pastors(self, tenant_id: UUID) -> list[UUID]:
        """Tous les pasteurs actifs — les candidats au relais, dans un ordre déterministe."""
        ...

    @abstractmethod
    async def agenda_keeper(self, tenant_id: UUID) -> UUID | None:
        """Qui tient l'agenda du pasteur — détenteur de `MANAGE_APPOINTMENTS` église-entière.

        Une demande de rendez-vous déclinée est une dette de **l'agenda**, pas du référent : le
        référent n'a rien décliné. Sans cette question, le cas retombait sur le responsable de
        cellule, qui lisait au passage que son membre avait demandé à voir un pasteur — la fuite
        que le chantier ferme."""
        ...

    @abstractmethod
    async def tenant_owner(self, tenant_id: UUID) -> UUID | None:
        """Le propriétaire de l'église — le **dernier échelon**, jamais le premier.

        Il existe toujours (une église sans propriétaire n'existe pas), et c'est ce qui permet à
        `owner_account_id` d'être NOT NULL sans qu'aucune inquiétude ne soit jamais perdue faute
        de configuration. Le trou reste consigné : recevoir un cas parce que personne d'autre
        n'est configuré n'est pas la même chose que le recevoir parce qu'on est le bon."""
        ...


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


class CoverageGapStore(ABC):
    """Là où remontent les trous du dispositif — pas dans un journal applicatif.

    Un défaut consigné dans les logs n'existe pour personne. Celui-ci doit apparaître sur
    l'écran de couverture, sinon l'église mal configurée reste silencieuse et son silence
    passe pour de la santé."""

    @abstractmethod
    async def record_once(self, record: CoverageGapRecord) -> bool:
        """Consigne le défaut s'il n'est pas déjà ouvert. Renvoie True s'il a été créé."""
        ...

    @abstractmethod
    async def open_gaps(self, tenant_id: UUID) -> list[CoverageGapRecord]: ...


class ReferentHistoryRepository(ABC):
    """Append-only : aucune méthode ne modifie ni ne supprime une entrée."""

    @abstractmethod
    async def append(self, entry: ReferentHistoryEntry) -> None: ...

    @abstractmethod
    async def last_for(
        self, person_id: UUID, tenant_id: UUID, *, before: datetime | None = None
    ) -> ReferentHistoryEntry | None: ...


class WatchParameterRepository(ABC):
    """Les valeurs calibrables, par église, avec repli sur le défaut du produit."""

    @abstractmethod
    async def get_int(self, tenant_id: UUID, param: WatchParam) -> int:
        """La valeur pour cette église, sinon le défaut. **Jamais une constante lue au vol.**"""
        ...
