"""DTO applicatifs — objets de transfert entre application et interface.

Volontairement découplés du framework (dataclasses) : la couche interface les
projette en schémas Pydantic pour la sérialisation HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RoleDTO:
    role: str
    group_id: UUID | None


@dataclass(frozen=True)
class MembershipStatusDTO:
    membership_id: UUID
    account_id: UUID
    tenant_id: UUID
    status: str
    is_confirmed_member: bool
    active_absence_reason: str | None
    active_roles: list[RoleDTO]
    is_owner: bool  # propriété (1ᵉʳ étage d'autorisation)
    permissions: list[str]  # verbes résolus dans ce tenant (M-3)


@dataclass(frozen=True)
class EnrollMemberResult:
    account_id: UUID
    membership_id: UUID
    role: str
    group_id: UUID | None


@dataclass(frozen=True)
class TransitionResult:
    membership_id: UUID
    status: str
    previous_status: str


@dataclass(frozen=True)
class RevokeRoleResult:
    membership_id: UUID
    role: str
    group_id: UUID | None


@dataclass(frozen=True)
class CloseMembershipResult:
    membership_id: UUID
    status: str
    closure_reason: str


@dataclass(frozen=True)
class EnrollInvitedMemberResult:
    account_id: UUID
    membership_id: UUID
    status: str


@dataclass(frozen=True)
class InvitedMemberInput:
    phone_number: str
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True)
class EnrolledRow:
    phone_number: str
    account_id: UUID


@dataclass(frozen=True)
class FailedRow:
    phone_number: str
    reason: str  # code d'erreur (ex. IAM_ACCOUNT_PHONE_ALREADY_EXISTS)


@dataclass(frozen=True)
class BulkEnrollResult:
    enrolled: list[EnrolledRow]
    failed: list[FailedRow]


# --- Transfert de membre entre églises ---


@dataclass(frozen=True)
class TransferDTO:
    id: UUID
    account_id: UUID
    from_tenant_id: UUID
    to_tenant_id: UUID
    to_group_id: UUID | None
    status: str
    requested_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True)
class TransferListDTO:
    tenant_id: UUID
    incoming: list[TransferDTO]  # demandes où l'on est la source (à accepter/refuser)
    outgoing: list[TransferDTO]  # demandes où l'on est la destination (que l'on a émises)


# --- Rejoindre une église par lien/code (M-5) ---


@dataclass(frozen=True)
class ChurchInvitationDTO:
    id: UUID
    tenant_id: UUID
    code: str
    expires_at: datetime
    revoked: bool


@dataclass(frozen=True)
class JoinChurchResult:
    account_id: UUID
    tenant_id: UUID
    membership_id: UUID
    status: str  # invited
    already_member: bool  # le compte était déjà membre → aucune appartenance créée
