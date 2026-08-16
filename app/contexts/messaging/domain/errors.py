"""Erreurs du contexte Messagerie — préfixe `MSG_`."""

from app._shared.domain.errors import DomainError


class MessagingError(DomainError):
    code = "MSG_ERROR"
    http_status = 502


class ChannelUnavailableError(MessagingError):
    """Le fournisseur n'a pas pris le message : panne, quota, jeton refusé.

    Réessayable, ou repliable sur un autre canal — c'est l'appelant qui
    tranche, parce que lui seul sait si le message peut attendre.
    """

    code = "MSG_CHANNEL_UNAVAILABLE"
    http_status = 502


class MessageRejectedError(MessagingError):
    """Le fournisseur a refusé le message lui-même : numéro invalide, modèle
    inconnu, destinataire hors périmètre.

    Distinct de l'indisponibilité, et c'est tout l'intérêt : réessayer ne
    servira à rien, et se replier sur un autre canal n'aidera que si la cause
    est propre à celui-ci.
    """

    code = "MSG_REJECTED"
    http_status = 422
