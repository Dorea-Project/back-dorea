"""Énumérations du contexte Mission (M9) — l'écosystème missionnaire (la main tendue).

Les valeurs sont la source de vérité (base + surfaces) — stables, on peut en ajouter.
"""

from enum import StrEnum


class InviterKind(StrEnum):
    """Un lien d'invitation appartient à une **personne** ou à un **groupe** (dérivé)."""

    PERSON = "person"  # attribution individuelle — le fruit de chaque membre
    GROUP = "group"  # attribution collective — une campagne, une équipe


class SeekerReaction(StrEnum):
    """La voix (légère, anonyme) du chercheur devant la carte — du ressenti à l'assentiment."""

    TOUCHED = "touched"  # « je suis touché »
    EDIFIED = "edified"  # « je suis édifié »
    AMEN = "amen"  # « Amen »


class SeekerStatus(StrEnum):
    """Où en est le chercheur — jamais un verdict définitif (posture révélateur, cf. M7)."""

    ACCEPTED = "accepted"  # a accepté l'invitation (a laissé un contact)
    ACCOMPANIED = "accompanied"  # un membre a pris le relais (à venir : Accompagner)
    INTEGRATED = "integrated"  # devenu membre (à venir : Intégrer → tunnel existant)
    CLOSED = "closed"  # n'a pas donné suite (sans jugement)
