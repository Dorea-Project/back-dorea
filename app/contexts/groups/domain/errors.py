"""Erreurs du contexte Groupes — codes préfixés `GROUP_`."""

from app._shared.domain.errors import DomainError, ForbiddenError, NotFoundError


class GroupError(DomainError):
    code = "GROUP_ERROR"


class GroupNotFoundError(NotFoundError):
    code = "GROUP_NOT_FOUND"


class ParentGroupNotFoundError(NotFoundError):
    """Le `parent_group_id` fourni n'existe pas."""

    code = "GROUP_PARENT_NOT_FOUND"


class CrossTenantParentError(GroupError):
    """Le parent appartient à un autre tenant — un groupe ne franchit pas la frontière d'église."""

    code = "GROUP_PARENT_CROSS_TENANT"
    http_status = 422


class UnauthorizedGroupActionError(ForbiddenError):
    """Droit insuffisant : la portée de l'acteur ne couvre pas le nœud visé (M4 §4)."""

    code = "GROUP_FORBIDDEN"


class RequiresChurchMembershipError(GroupError):
    """Rejoindre un groupe exige une appartenance active à l'église (M4 §6)."""

    code = "GROUP_REQUIRES_CHURCH_MEMBERSHIP"
    http_status = 422


class DuplicateGroupMembershipError(GroupError):
    """Le compte est déjà membre actif de ce groupe."""

    code = "GROUP_DUPLICATE_MEMBERSHIP"
    http_status = 409


class GroupMembershipNotFoundError(NotFoundError):
    """Aucune appartenance active de ce compte dans ce groupe."""

    code = "GROUP_MEMBERSHIP_NOT_FOUND"


class DuplicateLeadershipError(GroupError):
    """Le compte porte déjà ce grade de leadership sur ce groupe."""

    code = "GROUP_DUPLICATE_LEADERSHIP"
    http_status = 409


class LeaderCapExceededError(GroupError):
    """Cap de responsables (`group_leader`) atteint sur ce groupe (M4 §5)."""

    code = "GROUP_LEADER_CAP_EXCEEDED"
    http_status = 422


class NotACellError(GroupError):
    """Seule une cellule se multiplie (M4 §1/G-3)."""

    code = "GROUP_NOT_A_CELL"
    http_status = 422


class MemberNotInCellError(GroupError):
    """Un membre à déplacer n'appartient pas à la cellule-mère."""

    code = "GROUP_MEMBER_NOT_IN_CELL"
    http_status = 422


class GroupAlreadyPromotedError(GroupError):
    """Le groupe est déjà clôturé/promu — on ne peut pas le promouvoir deux fois (G-4)."""

    code = "GROUP_ALREADY_PROMOTED"
    http_status = 409


class GroupClosedError(GroupError):
    """Le groupe est clôturé : plus de modification/fermeture possible (G-5)."""

    code = "GROUP_CLOSED"
    http_status = 409


class GroupHasActiveChildrenError(GroupError):
    """Fermeture bloquée : des sous-groupes actifs subsistent (fermer les enfants d'abord, G-5)."""

    code = "GROUP_HAS_ACTIVE_CHILDREN"
    http_status = 409


class InvalidGroupStatusError(GroupError):
    """Statut cible invalide pour une modification (seuls `active`/`dormant`, G-5)."""

    code = "GROUP_INVALID_STATUS"
    http_status = 422


class LeadershipNotFoundError(NotFoundError):
    """Aucune attribution de leadership active à révoquer pour ce compte sur ce groupe (G-5)."""

    code = "GROUP_LEADERSHIP_NOT_FOUND"


class InvitationNotFoundError(NotFoundError):
    """Code d'invitation inconnu (G-1b)."""

    code = "GROUP_INVITATION_NOT_FOUND"


class InvitationInactiveError(GroupError):
    """Invitation expirée ou révoquée (G-1b)."""

    code = "GROUP_INVITATION_INACTIVE"
    http_status = 410
