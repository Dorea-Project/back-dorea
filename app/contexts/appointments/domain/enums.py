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
    """Jamais un verdict : un rendez-vous décliné/annulé porte un mot doux, pas un rejet froid.

    **Les chemins d'échec portent le plus d'information.** Une demande est une main levée ; ce
    qui arrive ensuite dit beaucoup plus qu'un créneau posé. C'est pourquoi aucun de ces états
    ne se perd : chacun devient un fait, et l'annulation par le demandeur est probablement le
    signal le plus urgent que le système sache produire."""

    REQUESTED = "requested"  # le membre a demandé — en attente du discernement de la secrétaire
    CONFIRMED = "confirmed"  # un créneau a été posé (scheduled_at)
    DECLINED = "declined"  # la secrétaire n'a pas retenu la demande (avec un mot)
    # Servie autrement : le pasteur ne peut pas, mais quelqu'un rappelle. **Pas un refus
    # déguisé** — le cas de veille reste ouvert et change de main.
    ORIENTED = "oriented"
    CANCELLED = "cancelled"  # le demandeur s'est rétracté — il a demandé, puis a reculé
    NO_SHOW = "no_show"  # il n'est pas venu, sans même prévenir
    COMPLETED = "completed"  # le rendez-vous a eu lieu (honoré)
