"""Énumérations du module Event — le happening publié (la première chose qui peut dépasser
les murs d'une église). Valeurs = source de vérité (base + surfaces), stables, extensibles.
"""

from enum import StrEnum


class EventScope(StrEnum):
    """Le cercle qu'atteint l'événement — l'échelle du rayonnement.

    CHURCH est gratuit (le corps local) ; DENOMINATION et PLATFORM demandent le compte Business
    (à venir) — rayonner plus loin est un acte institutionnel, pas un geste personnel."""

    CHURCH = "church"  # les membres de mon église (gratuit)
    DENOMINATION = "denomination"  # toutes les églises de ma dénomination (Business, à venir)
    PLATFORM = "platform"  # toute la plateforme Dorea (Business, à venir)


class EventCategory(StrEnum):
    CONVENTION = "convention"
    VIGIL = "vigil"  # veillée
    CONCERT = "concert"
    SEMINAR = "seminar"  # séminaire
    SERVICE = "service"  # culte spécial
    OUTING = "outing"  # sortie
    TRAINING = "training"  # formation
    OTHER = "other"


class EventReaction(StrEnum):
    """Le signal léger devant l'événement — « ça résonne » (compté, pas un score de vitrine)."""

    INTERESTED = "interested"  # ça m'intéresse
    BLESSED = "blessed"  # ça m'édifie
    PRAY = "pray"  # je prie pour


class EventStatus(StrEnum):
    PUBLISHED = "published"
    CANCELLED = "cancelled"  # retiré par l'auteur
    TAKEN_DOWN = "taken_down"  # retiré par la modération (Plateforme) — le rayonnement gouverné
