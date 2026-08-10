"""Ports d'écriture du contexte IAM (surface backoffice).

`MemberEnrollmentStore` persiste **atomiquement** un nouveau membre : Account +
Membership (`confirmed_member`) + ses RoleAssignment. Même règle d'atomicité que la
genèse (un rôle exige `confirmed_member`, M0 §3.2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import (
    AccountCreationSource,
    MembershipClosureReason,
    MembershipStatus,
    RevocationReason,
)


class OwnershipChecker(ABC):
    """Port lu par l'autorisation (1ᵉʳ étage) — implémenté par le contexte tenant."""

    @abstractmethod
    async def is_active_owner(self, account_id: UUID, tenant_id: UUID) -> bool: ...


@dataclass(frozen=True, slots=True)
class ProfileRow:
    """La personne, telle que le compte la garde — **et rien de plus**.

    ⚠️ Pas de `birth_year`. Elle existe en base, optionnelle, et n'est affichée nulle part :
    l'âge de quelqu'un n'est pas une donnée d'église. La faire remonter jusqu'à un port la
    rendrait affichable par accident, ce qui est la façon dont les données sensibles fuient."""

    account_id: UUID
    phone_number: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    birth_day: int | None = None
    birth_month: int | None = None
    birthday_scope: str = "groups"


class ProfileReader(ABC):
    """Lire **son propre** profil. Aucune méthode ne prend d'autre identité que la sienne."""

    @abstractmethod
    async def read(self, account_id: UUID) -> ProfileRow | None: ...


class InvitationCodeGenerator(ABC):
    """Génère un code d'invitation église court, lisible et non devinable (M-5)."""

    @abstractmethod
    def generate(self) -> str: ...


class MembershipLifecycleStore(ABC):
    @abstractmethod
    async def revoke_role(
        self,
        *,
        role_assignment_id: UUID,
        revoked_at: datetime,
        reason: RevocationReason,
    ) -> None:
        """Révoque une attribution de rôle (retrait ciblé)."""
        ...

    @abstractmethod
    async def close_membership(
        self,
        *,
        membership_id: UUID,
        closed_at: datetime,
        closure_reason: MembershipClosureReason,
    ) -> None:
        """Clôture une appartenance **et révoque tous ses rôles actifs**, en une transaction.

        Cascade atomique (§5.2) : statut → `closed`, `closure_reason`/`closed_at` posés,
        et chaque `RoleAssignment` actif révoqué avec `reason = demotion_cascade`.
        """
        ...


class MembershipTransitionStore(ABC):
    @abstractmethod
    async def apply_transition(
        self,
        *,
        membership_id: UUID,
        new_status: MembershipStatus,
        previous_status: MembershipStatus,
        transitioned_at: datetime,
    ) -> None:
        """Met à jour le statut d'une appartenance + `previous_status` + horodatage."""
        ...


class MemberEnrollmentStore(ABC):
    @abstractmethod
    async def enroll(
        self,
        *,
        account: Account,
        membership: Membership,
        creation_source: AccountCreationSource,
        actor_account_id: UUID,
    ) -> None:
        """Crée le compte (**sans credential**) + l'appartenance + les rôles, en une transaction.

        Personne ne reçoit de credential à l'enrôlement (M-0/décision C) : chacun **active**
        ensuite sur sa surface — PIN mobile (membre) ou mot de passe backoffice (staff).
        `actor_account_id` = l'enrôleur, tracé comme `created_by`/`assigned_by`.
        """
        ...

    @abstractmethod
    async def add_membership(
        self,
        *,
        membership: Membership,
        actor_account_id: UUID,
    ) -> None:
        """Ajoute une appartenance (+ rôles) à un **compte existant** (réutilisation, M-2)."""
        ...


class MemberRosterPort(ABC):
    """Port vers le contexte Groupes pour les mouvements de roster lors d'un transfert.

    iam ne dépend pas de Groupes : il exprime *ce dont il a besoin* (libérer un membre
    de ses groupes ici, le placer dans un groupe là-bas) ; un adaptateur côté Groupes
    l'implémente (Groupes → iam, sens de dépendance correct)."""

    @abstractmethod
    async def release_from_tenant(
        self, *, account_id: UUID, tenant_id: UUID, now: datetime
    ) -> None:
        """Fait quitter au membre **tous ses groupes actifs** dans ce tenant (transfert sortant)."""
        ...

    @abstractmethod
    async def place_in_group(
        self,
        *,
        account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        now: datetime,
        by_account_id: UUID,
    ) -> None:
        """Inscrit le membre dans un groupe du tenant destination (idempotent)."""
        ...
