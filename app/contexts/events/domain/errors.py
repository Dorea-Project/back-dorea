"""Erreurs du module Event — codes préfixés `EVT_`."""

from app._shared.domain.errors import DomainError, NotFoundError


class EventError(DomainError):
    code = "EVT_ERROR"


class EventNotFoundError(NotFoundError):
    code = "EVT_NOT_FOUND"


class InvalidEventError(EventError):
    """Événement incohérent (titre vide, géo incomplète…)."""

    code = "EVT_INVALID"
    http_status = 422


class EventCancelledError(EventError):
    """L'événement a été annulé — on n'agit plus dessus."""

    code = "EVT_CANCELLED"
    http_status = 409


class EventTakenDownError(EventError):
    """L'événement a été retiré par la modération — on n'agit plus dessus."""

    code = "EVT_TAKEN_DOWN"
    http_status = 409


class NotEventAuthorError(EventError):
    """Seul l'auteur (l'organisateur) peut annuler ou voir la liste des participants."""

    code = "EVT_NOT_AUTHOR"
    http_status = 403


class NotAChurchMemberError(EventError):
    """Seul un membre de l'église peut publier, réagir ou confirmer sa présence."""

    code = "EVT_NOT_A_CHURCH_MEMBER"
    http_status = 403


class WiderReachRequiresBusinessError(EventError):
    """Rayonner au-delà de son église (dénomination, plateforme) exige le compte Business."""

    code = "EVT_WIDER_REACH_REQUIRES_BUSINESS"
    http_status = 403
