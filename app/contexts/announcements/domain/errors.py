"""Erreurs du contexte Annonces — codes préfixés `ANN_`."""

from app._shared.domain.errors import DomainError, NotFoundError


class AnnouncementError(DomainError):
    code = "ANN_ERROR"


class AnnouncementNotFoundError(NotFoundError):
    code = "ANN_NOT_FOUND"


class InvalidAnnouncementError(AnnouncementError):
    """Champs incohérents avec l'intention (ex. mobiliser sans nombre de places)."""

    code = "ANN_INVALID"
    http_status = 422


class AnnouncementClosedError(AnnouncementError):
    """L'annonce est archivée (ou expirée) : plus de réponse possible."""

    code = "ANN_CLOSED"
    http_status = 409


class ResponsesNotAcceptedError(AnnouncementError):
    """Cette intention n'attend pas d'engagement (ex. « informer »)."""

    code = "ANN_RESPONSES_NOT_ACCEPTED"
    http_status = 422


class EmojiNotAllowedError(AnnouncementError):
    """Emoji hors de la palette du type (pas de 🎉 sur un décès)."""

    code = "ANN_EMOJI_NOT_ALLOWED"
    http_status = 422


class MobilizationFullError(AnnouncementError):
    """Toutes les places de la mobilisation sont prises."""

    code = "ANN_MOBILIZATION_FULL"
    http_status = 409


class NotInAudienceError(AnnouncementError):
    """Le membre n'est pas dans la portée de l'annonce (ne peut y répondre)."""

    code = "ANN_NOT_IN_AUDIENCE"
    http_status = 403


class SubjectNotAllowedError(AnnouncementError):
    """Ce type parle d'une **activité**, pas d'une personne : on ne lui rattache pas de sujet.

    Contrainte d'intégrité, pas convention — c'est ce qui interdit de dériver un effet de veille
    d'une collecte, d'un appel à servir ou d'une info générale."""

    code = "ANN_SUBJECT_NOT_ALLOWED"
    http_status = 422


class RoleNotProposedError(AnnouncementError):
    """Le rôle n'est pas proposé par ce type d'annonce (on ne baptise pas un défunt)."""

    code = "ANN_ROLE_NOT_PROPOSED"
    http_status = 422


class DeclaredDurationRequiredError(AnnouncementError):
    """Ce rôle neutralise sur une durée **déclarée** : sans elle, il n'y a rien à neutraliser."""

    code = "ANN_DECLARED_DURATION_REQUIRED"
    http_status = 422


class DuplicateSubjectError(AnnouncementError):
    """Une personne ne tient qu'un rôle par annonce (on n'est pas défunt *et* endeuillé)."""

    code = "ANN_DUPLICATE_SUBJECT"
    http_status = 422


class ConsentNotPendingError(AnnouncementError):
    """Il n'y a rien à accepter ou refuser : la question ne se pose pas, ou est déjà tranchée."""

    code = "ANN_CONSENT_NOT_PENDING"
    http_status = 409


class NotTheSubjectError(AnnouncementError):
    """Seul le sujet lui-même accepte ou refuse d'être nommé. Personne ne consent à sa place."""

    code = "ANN_NOT_THE_SUBJECT"
    http_status = 403


class NotAChurchMemberError(AnnouncementError):
    """On ne lit le fil d'une église que si l'on en est membre actif (isolation inter-église)."""

    code = "ANN_NOT_MEMBER"
    http_status = 403
