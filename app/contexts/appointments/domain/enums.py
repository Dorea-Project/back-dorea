"""États et catégories d'un rendez-vous (module Rendez-vous)."""

from enum import StrEnum


class AppointmentCategory(StrEnum):
    """De quoi il s'agit — pour trier l'agenda et adapter l'accueil (extensible)."""

    PRAYER = "prayer"  # demande de prière
    MARRIAGE = "marriage"  # mariage (préparation, entretien)
    VISIT = "visit"  # visite (à domicile, à l'hôpital…)
    COUNSEL = "counsel"  # conseil, accompagnement personnel
    ADMINISTRATIVE = "administrative"  # affaire administrative
    OTHER = "other"  # autre


class AppointmentStatus(StrEnum):
    """Jamais un verdict : un rendez-vous décliné/annulé porte un mot doux, pas un rejet froid."""

    REQUESTED = "requested"  # le membre a demandé — en attente du discernement de la secrétaire
    CONFIRMED = "confirmed"  # un créneau a été posé (scheduled_at)
    DECLINED = "declined"  # la secrétaire n'a pas retenu la demande (avec un mot)
    CANCELLED = "cancelled"  # le demandeur s'est rétracté
    COMPLETED = "completed"  # le rendez-vous a eu lieu (honoré)
