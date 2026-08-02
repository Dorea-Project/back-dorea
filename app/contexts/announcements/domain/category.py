"""Le **profil d'un type d'annonce** — le type pilote, l'intention est dérivée (choix figé).

L'utilisateur choisit ce à quoi il pense (« décès », « naissance », « mariage »…) ; le type porte :
- sa **couleur** (`tone`, clé sémantique — le client rend l'effet visuel) ;
- ses **emojis** autorisés (palette fixe *suggérée par le type* : on ne met pas 🎉 sur un décès) ;
- son **intention par défaut** (surchargeable — un mariage peut aussi convoquer avec RSVP).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contexts.announcements.domain.enums import (
    AnnouncementCategory,
    AnnouncementIntent,
    AnnouncementTone,
)

C, T, Intent = AnnouncementCategory, AnnouncementTone, AnnouncementIntent


@dataclass(frozen=True)
class CategoryProfile:
    tone: AnnouncementTone
    default_intent: AnnouncementIntent
    emojis: tuple[str, ...]  # palette autorisée pour les réactions


CATEGORY_PROFILE: dict[AnnouncementCategory, CategoryProfile] = {
    # Un décès n'est pas une information qu'on like : c'est une **mobilisation** (veillée,
    # cotisation, accompagnement). 40 🙏 et personne à la veillée = un échec, pas un succès.
    C.DEATH: CategoryProfile(T.MOURNING, Intent.MOBILIZE, ("🙏", "🖤", "😢")),
    C.BIRTH: CategoryProfile(T.JOY, Intent.INFORM, ("🎉", "❤️", "👶")),
    C.WEDDING: CategoryProfile(T.CELEBRATION, Intent.INFORM, ("🎉", "❤️", "👏")),
    C.BAPTISM: CategoryProfile(T.CELEBRATION, Intent.INFORM, ("🎉", "🙏", "👏")),
    # Une fête **convoque** : elle n'existe que si les gens viennent. C'est la différence avec un
    # baptême, qu'on annonce d'abord pour le faire savoir — ici, « je viens » est le geste utile.
    C.CELEBRATION: CategoryProfile(T.CELEBRATION, Intent.CONVENE, ("🎉", "🙌", "👏")),
    # La maladie appelle à porter, pas à liker : intention « prier », palette sobre.
    C.SICKNESS: CategoryProfile(T.SOLEMN, Intent.PRAY, ("🙏", "❤️")),
    # Le voyage informe (« je serai loin N semaines ») — son effet est dans la veille, pas au fil.
    C.TRAVEL: CategoryProfile(T.NEUTRAL, Intent.INFORM, ("👍", "🙏")),
    C.SERVICE: CategoryProfile(T.SOLEMN, Intent.CONVENE, ("🙏", "❤️")),
    C.MEETING: CategoryProfile(T.NEUTRAL, Intent.CONVENE, ("👍", "🙏")),
    C.CALL: CategoryProfile(T.CALL, Intent.MOBILIZE, ("🙌", "👏")),
    C.PRAYER: CategoryProfile(T.SOLEMN, Intent.PRAY, ("🙏", "❤️")),
    C.TESTIMONY: CategoryProfile(T.JOY, Intent.INFORM, ("🎉", "🙏", "👏")),
    # Une capsule du sermon : la Parole méditée, sans mécanique d'engagement (informer).
    C.SERMON: CategoryProfile(T.SOLEMN, Intent.INFORM, ("🙏", "❤️", "🕊️")),
    C.INFO: CategoryProfile(T.NEUTRAL, Intent.INFORM, ("👍",)),
}


def profile_of(category: AnnouncementCategory) -> CategoryProfile:
    return CATEGORY_PROFILE[category]
