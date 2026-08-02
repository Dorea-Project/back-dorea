"""Énumérations du contexte Annonces (M8).

**Deux axes** (choix figé) :
- le **type** (`AnnouncementCategory`) = de quoi ça parle → porte la **couleur** (`tone`), les
  **emojis** suggérés et une **intention par défaut** (surchargeable) ;
- l'**intention** (`AnnouncementIntent`) = la mécanique du retour (quel engagement attendu).

Les valeurs sont la source de vérité (base + surfaces) — stables, on peut en ajouter.
"""

from enum import StrEnum

# Le vocabulaire de la veille appartient au **moteur** : une source parle sa langue, jamais
# l'inverse. On le réexporte ici pour que les Annonces n'aient qu'un import à faire.
from app.contexts.watch.domain.role_rules import (  # noqa: F401
    SubjectRole,
    WatchEffect,
    WatchScope,
)


class AnnouncementIntent(StrEnum):
    """La mécanique : quel **engagement** l'annonce attend (la seconde voix structurante)."""

    INFORM = "inform"  # info pure — aucun engagement (les réactions restent possibles)
    CONVENE = "convene"  # convoquer (→ rencontre M6) — « je viens »
    MOBILIZE = "mobilize"  # appel à servir (N places) — « je sers », se remplit
    PRAY = "pray"  # porter dans la prière — « je porte »


class AnnouncementCategory(StrEnum):
    """Le sujet — ce que l'utilisateur choisit. Pilote couleur, emojis et intention par défaut."""

    DEATH = "death"  # décès / deuil
    BIRTH = "birth"  # naissance
    WEDDING = "wedding"  # mariage
    BAPTISM = "baptism"  # baptême
    # **La fête** — anniversaire de l'église, jubilé d'un ministère, fin d'année, kermesse.
    # Le catalogue couvrait les grands passages de la vie (naissance, mariage, deuil) et le
    # formel (culte, réunion, appel), et rien de ce qui réjouit une communauté sans marquer
    # une étape. C'est pourtant ce qu'une église annonce le plus souvent après le culte.
    CELEBRATION = "celebration"
    SICKNESS = "sickness"  # maladie / hospitalisation
    TRAVEL = "travel"  # voyage / absence prolongée annoncée
    SERVICE = "service"  # culte
    MEETING = "meeting"  # réunion
    CALL = "call"  # appel à servir
    PRAYER = "prayer"  # requête de prière
    TESTIMONY = "testimony"  # témoignage
    SERMON = "sermon"  # capsule d'un sermon (le sermon qui vit au fil, cf. contexte sermon)
    INFO = "info"  # info générale


class AnnouncementTone(StrEnum):
    """La **couleur** de l'annonce — clé sémantique ; le client choisit la palette réelle."""

    MOURNING = "mourning"  # deuil (sombre)
    JOY = "joy"  # joie (douce)
    CELEBRATION = "celebration"  # fête (éclatante)
    SOLEMN = "solemn"  # solennel
    CALL = "call"  # appel (chaud)
    NEUTRAL = "neutral"


class Invitation(StrEnum):
    """La réaction est une **porte, pas une fin** : le clic ouvre un geste plus coûteux.

    Clé sémantique (le client formule) — pas un accusé, une invitation."""

    COME = "come"  # mobiliser (la veillée, l'appel) → « viens »
    CONFIRM = "confirm"  # convoquer → « confirme ta venue »
    REACH_OUT = "reach_out"  # prier → « prends de ses nouvelles cette semaine »


class AnnouncementStatus(StrEnum):
    PUBLISHED = "published"  # vivante — dans le fil
    ARCHIVED = "archived"  # sortie du fil (à la main ou par expiration), reste consultable
    # Un sujet dont le rôle exige son accord ne l'a pas encore donné : l'annonce **n'est pas
    # dans le fil**, seuls l'auteur et les sujets la voient. Rien n'est dit à l'église avant.
    PENDING_CONSENT = "pending_consent"
    DECLINED = "declined"  # un sujet a refusé — terminal, jamais publiée


class AnnouncementScope(StrEnum):
    """Trois niveaux de portée — dérivés (pas stockés)."""

    PLATFORM = "platform"  # Dorea → toutes les églises (admin central)
    CHURCH = "church"  # toute l'église
    GROUP = "group"  # un groupe + son sous-arbre


class SubjectConsent(StrEnum):
    """Accord du sujet à être nommé. Exigé là où la donnée est intime (la maladie).

    `NOT_REQUIRED` n'est pas « accordé » : c'est « la question ne se pose pas pour ce rôle »."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    GRANTED = "granted"
    DECLINED = "declined"
