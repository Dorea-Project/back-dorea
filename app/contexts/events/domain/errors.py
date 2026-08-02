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


class PublicationCadenceError(EventError):
    """**Un événement à la fois, et un par semaine.**

    Publier envoie une notification à toute l'église. Rien ne bornait ce geste : cinq
    publications d'affilée faisaient sonner cinq fois quarante téléphones en quelques secondes,
    et la sanction n'est pas la désinstallation — c'est la coupure des notifications, après quoi
    le canal de veille ne passe plus non plus.

    Le message dit **quand** on pourra publier de nouveau : un refus sans échéance se lit comme
    une panne, et on réessaie."""

    code = "EVT_PUBLICATION_CADENCE"
    http_status = 429


class WiderReachRequiresBusinessError(EventError):
    """Rayonner au-delà de son église (dénomination, plateforme) exige le compte Business."""

    code = "EVT_WIDER_REACH_REQUIRES_BUSINESS"
    http_status = 403


class WiderReachRequiresMandateError(EventError):
    """Le compte Business est le droit de **payer** ; le mandat est le droit de **parler**.

    Erreur distincte, et ce n'est pas un détail d'implémentation : un refus de mandat n'est pas un
    refus de paiement, et le message doit dire lequel. Quelqu'un qui a payé et qu'on renvoie vers
    une page d'abonnement ne comprendra jamais ce qu'on lui demande — c'est à son pasteur qu'il
    doit s'adresser."""

    code = "EVT_WIDER_REACH_REQUIRES_MANDATE"
    http_status = 403
