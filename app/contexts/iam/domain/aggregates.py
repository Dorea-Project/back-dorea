"""Agrégats racines du contexte IAM : `Account` et `Membership`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.iam.domain.entities import RoleAssignment
from app.contexts.iam.domain.enums import (
    AbsenceReason,
    AccountStatus,
    MembershipStatus,
    RoleCode,
)

# Statuts considérés « membre installé » pour la portée des rôles.
_CONFIRMED = MembershipStatus.CONFIRMED_MEMBER


class Account(AggregateRoot):
    """Compte — identité **globale** de la personne (spec métier §5.1).

    Racine d'agrégat. Une église ne possède jamais un compte : elle ne fait que
    clôturer une `Membership`. Les credentials sont optionnelles (le visiteur
    existe avant l'app).
    """

    def __init__(
        self,
        *,
        id: UUID,
        phone_number: str,
        status: AccountStatus,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        is_phone_verified: bool = False,
    ) -> None:
        super().__init__()
        self.id = id
        self.phone_number = phone_number
        self.status = status
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.is_phone_verified = is_phone_verified

    @property
    def is_active(self) -> bool:
        return self.status is AccountStatus.ACTIVE


class Membership(AggregateRoot):
    """Appartenance — lien Compte ↔ Église/Annexe, porteur du **statut** (spec §5).

    Racine d'agrégat contenant ses `RoleAssignment` (entités internes). La
    rétrogradation révoque les rôles dans la même transaction (cascade atomique,
    spec §5.2) — logique servie par la surface backoffice ; sur la surface mobile
    l'agrégat est reconstitué en lecture.
    """

    def __init__(
        self,
        *,
        id: UUID,
        account_id: UUID,
        tenant_id: UUID,
        status: MembershipStatus,
        last_transition_at: datetime,
        active_absence_reason: AbsenceReason | None = None,
        closed_at: datetime | None = None,
        role_assignments: list[RoleAssignment] | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.account_id = account_id
        self.tenant_id = tenant_id
        self.status = status
        self.last_transition_at = last_transition_at
        self.active_absence_reason = active_absence_reason
        self.closed_at = closed_at
        self._role_assignments: list[RoleAssignment] = role_assignments or []

    # --- Requêtes de domaine (miroir M1 §8.2) ---

    @property
    def is_closed(self) -> bool:
        return self.status is MembershipStatus.CLOSED or self.closed_at is not None

    @property
    def is_confirmed_member(self) -> bool:
        """`IsConfirmedMember` — condition d'attribution d'un rôle (spec §5.6)."""
        return self.status is _CONFIRMED

    def active_roles(self) -> list[RoleAssignment]:
        """`GetActiveRoles` — attributions non révoquées."""
        return [ra for ra in self._role_assignments if ra.is_active]

    def has_role(self, role: RoleCode, *, group_id: UUID | None = None) -> bool:
        """RBAC borné par la propriété (spec §5.6) : rôle **et** portée.

        Le rôle accorde le verbe ; l'attribution doit en plus couvrir la
        ressource visée (le `group_id` pour un rôle de portée groupe).
        """
        return any(ra.role is role and ra.covers(group_id=group_id) for ra in self.active_roles())

    def list_group_leaders(self) -> list[RoleAssignment]:
        """`ListGroupLeaders` — responsables de groupe actifs (1 à 6, spec §6)."""
        return [ra for ra in self.active_roles() if ra.role is RoleCode.GROUP_LEADER]
