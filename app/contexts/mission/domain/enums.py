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
    """Où en est le chercheur — **dérivé**, plus jamais stocké ni écrit.

    Il confondait deux choses qui ont chacune leur propriétaire : *où en est la personne*
    (`MembershipStatus`, IAM) et *où en est le cas* (`Signal`, watch). Il subsiste comme valeur
    de lecture, calculée par `derive_seeker_status` — la compatibilité du client mobile, pas une
    seconde machine à états."""

    ACCEPTED = "accepted"  # a laissé un contact, personne ne s'en occupe encore
    ACCOMPANIED = "accompanied"  # un membre a pris le relais — le cas est en contact
    INTEGRATED = "integrated"  # devenu membre
    CLOSED = "closed"  # le cas de veille est clos, quelle qu'en soit l'issue


class SeekerOutcome(StrEnum):
    """Les issues qu'un parcours de chercheur peut prendre — **sous-ensemble** des issues du
    `Signal`, dont elles reprennent les valeurs à l'identique (un test le fige).

    Elles ne sont pas toutes des échecs : `known_and_followed` dit « elle vient, on la connaît
    par son nom, elle ne veut pas encore de cellule », et c'est une réussite."""

    UNREACHABLE_ARCHIVED = "unreachable_archived"  # n'a pas donné suite, sans jugement
    KNOWN_AND_FOLLOWED = "known_and_followed"
    CHANGED_CHURCH = "changed_church"
    DO_NOT_CONTACT = "do_not_contact"
    RESTORED = "restored"
