"""Énumérations du contexte Messagerie."""

from enum import StrEnum


class Channel(StrEnum):
    """Le transport d'un message."""

    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"


class TemplateCategory(StrEnum):
    """Catégorie d'un modèle WhatsApp — elle décide du prix et des règles.

    Ce n'est pas une classification interne : c'est celle de l'opérateur, et
    elle conditionne ce qu'on a le droit d'envoyer hors de la fenêtre de 24 h.
    """

    #: Codes de connexion. La moins chère, la plus encadrée : rien d'autre
    #: qu'un code ne doit passer par là.
    AUTHENTICATION = "authentication"

    #: Suite d'une action de l'utilisateur : rappel d'un RSVP déjà donné,
    #: confirmation d'un rendez-vous.
    UTILITY = "utility"

    #: Tout ce qui sollicite — une invitation en fait partie, même sans
    #: intention commerciale. La plus chère, et celle qui exige l'opt-in le
    #: plus explicite.
    MARKETING = "marketing"


class DeliveryOutcome(StrEnum):
    """Ce que le fournisseur a répondu à la remise du message.

    S'arrête à ce que l'on sait **au moment de l'appel**. La suite — remis, lu,
    échoué — arrive par webhook (étape 2) et n'est pas de ce type.
    """

    #: Le fournisseur a pris le message en charge.
    ACCEPTED = "accepted"

    #: Refusé d'emblée : numéro invalide, modèle inconnu, compte sans crédit.
    REJECTED = "rejected"
