"""Ports du contexte Groupes vers l'extérieur (écriture IAM/Tenant via anti-corruption)."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.contexts.iam.domain.aggregates import Membership
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.ownership import Ownership


class ChurchRoleStore(ABC):
    """Écrit un rôle IAM scopé pour le compte d'une action de gestion de groupe.

    Le leadership de groupe **est** un rôle IAM (pour que l'autorisation par sous-arbre le
    lise). Le contexte Groupes le pose via ce port ; l'adaptateur écrit la table détenue
    par IAM (`role_assignments`) — dépendance groups → iam, sens autorisé.
    """

    @abstractmethod
    async def add_group_role(
        self,
        *,
        membership_id: UUID,
        tenant_id: UUID,
        role: str,
        group_id: UUID,
        assigned_by_account_id: UUID,
        now: datetime,
    ) -> UUID:
        """Ajoute une attribution de rôle scopée et renvoie son id."""
        ...

    @abstractmethod
    async def revoke_group_role(
        self, *, membership_id: UUID, role: str, group_id: UUID, now: datetime
    ) -> int:
        """Révoque l'attribution active (membership, role, group) — renvoie le nb touché (G-5)."""
        ...

    @abstractmethod
    async def revoke_all_group_roles(self, *, group_id: UUID, now: datetime) -> None:
        """Révoque **toutes** les attributions actives d'un groupe (cascade de clôture, G-5)."""
        ...


class ChurchPlantStore(ABC):
    """Écrit atomiquement la naissance d'une église-fille (émancipation, G-4).

    Tenant (fille) + Ownership (émancipation) + les Memberships re-pointées, en une
    transaction. Les **comptes** existent déjà (membres du groupe) : on ne les recrée pas.
    """

    @abstractmethod
    async def plant(
        self,
        *,
        tenant: Tenant,
        ownership: Ownership,
        memberships: list[Membership],
        actor_account_id: UUID,
    ) -> None: ...


class InvitationCodeGenerator(ABC):
    """Génère un code d'invitation opaque, imprévisible (G-1b)."""

    @abstractmethod
    def generate(self) -> str: ...


class ChurchEnrollmentStore(ABC):
    """Crée une appartenance église **invited** pour un compte existant (onboarding par lien, G-1b).

    Le join-par-lien est une **porte d'onboarding explicite** : il rattache le compte à
    l'église si besoin (≠ effet caché). Écrit la table IAM `memberships`.
    """

    @abstractmethod
    async def enroll_invited(
        self, *, account_id: UUID, tenant_id: UUID, actor_account_id: UUID, now: datetime
    ) -> UUID:
        """Crée l'appartenance `invited` et renvoie son id."""
        ...
