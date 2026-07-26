"""Erreurs de domaine IAM — codes préfixés `IAM_` (M1 §6).

Le catalogue complet des codes commande (transitions, cascade de rôles…) est
servi par la surface backoffice (`/api/backoffice`) ; sur la surface mobile on
n'en instancie qu'un sous-ensemble utile à la lecture, plus les invariants
vérifiés localement.
"""

from app._shared.domain.errors import DomainError, ForbiddenError, NotFoundError


class IamError(DomainError):
    """Base des erreurs du contexte IAM."""

    code = "IAM_ERROR"


class InvalidPhoneNumberError(IamError):
    code = "IAM_INVALID_PHONE_NUMBER"
    http_status = 422


class MembershipNotFoundError(NotFoundError):
    code = "IAM_MEMBERSHIP_NOT_FOUND"


class AccountNotFoundError(NotFoundError):
    code = "IAM_ACCOUNT_NOT_FOUND"


class UnauthorizedScopeError(ForbiddenError):
    """M1 §6 — rôle valide mais ressource hors de sa portée (RBAC borné par la propriété)."""

    code = "IAM_UNAUTHORIZED_SCOPE"


class RoleRequiresGroupError(IamError):
    """Invariant M1 §4 : une attribution `group_leader` porte obligatoirement un `group_id`."""

    code = "IAM_ROLE_REQUIRES_GROUP"
    http_status = 422


class RoleNotEnrollableError(IamError):
    """L'Owner n'enrôle directement que Pasteur/Admin (§5.3/§5.6)."""

    code = "IAM_ROLE_NOT_ENROLLABLE"
    http_status = 422


class AccountPhoneAlreadyExistsError(IamError):
    """M1 §6 — le téléphone (identité globale) existe déjà : réutilisation à traiter à part."""

    code = "IAM_ACCOUNT_PHONE_ALREADY_EXISTS"
    http_status = 409


class DuplicateActiveMembershipError(IamError):
    """M1 §6 — appartenance active déjà présente pour ce compte dans ce tenant."""

    code = "IAM_DUPLICATE_ACTIVE_MEMBERSHIP"
    http_status = 409


class GroupLeaderCapExceededError(IamError):
    """M1 §6 — 7ᵉ `group_leader` sur un même groupe (cap 1 à 6, §6)."""

    code = "IAM_GROUP_LEADER_CAP_EXCEEDED"
    http_status = 409


class InvalidTransitionError(IamError):
    """M1 §6 — transition de statut hors table (§5.5)."""

    code = "IAM_INVALID_TRANSITION"
    http_status = 409


class StatusSkipForbiddenError(IamError):
    """M1 §6 — saut de palier (ex. `invited → confirmed_member` direct) interdit en V1."""

    code = "IAM_STATUS_SKIP_FORBIDDEN"
    http_status = 409


class RoleAssignmentNotFoundError(NotFoundError):
    """Le rôle visé n'est pas attribué (activement) à ce membre."""

    code = "IAM_ROLE_ASSIGNMENT_NOT_FOUND"


class GroupLastLeaderRemovalBlockedError(IamError):
    """M1 §6 — retrait du dernier `group_leader` d'un groupe sans remplaçant."""

    code = "IAM_GROUP_LAST_LEADER_REMOVAL_BLOCKED"
    http_status = 409


class LastOwnerRemovalBlockedError(IamError):
    """Invariant I1 (M0 §5) — on ne clôture pas le dernier Owner d'un tenant.

    La succession du siège Owner est un acte Plateforme (`TransferOwnership`), pas
    une clôture backoffice.
    """

    code = "IAM_LAST_OWNER_REMOVAL_BLOCKED"
    http_status = 409


# --- Transfert de membre entre églises (poignée de main) ---


class TransferNotFoundError(NotFoundError):
    """Transfert introuvable."""

    code = "IAM_TRANSFER_NOT_FOUND"


class TransferAlreadyResolvedError(IamError):
    """Le transfert n'est plus en attente (déjà accepté / refusé / annulé)."""

    code = "IAM_TRANSFER_ALREADY_RESOLVED"
    http_status = 409


class SameTenantTransferError(IamError):
    """Source et destination identiques : il n'y a rien à transférer."""

    code = "IAM_TRANSFER_SAME_TENANT"
    http_status = 422


# --- Rejoindre une église par lien/code (M-5) ---


class ChurchInvitationNotFoundError(NotFoundError):
    """Code d'invitation église inconnu."""

    code = "IAM_CHURCH_INVITATION_NOT_FOUND"


class ChurchInvitationInactiveError(IamError):
    """Le lien d'invitation église a expiré ou a été révoqué."""

    code = "IAM_CHURCH_INVITATION_INACTIVE"
    http_status = 409


class DuplicatePendingTransferError(IamError):
    """Une demande de transfert est déjà en attente pour ce membre sur ce trajet."""

    code = "IAM_TRANSFER_DUPLICATE_PENDING"
    http_status = 409
