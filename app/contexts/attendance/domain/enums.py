"""Énumérations du contexte Présence (M6). Valeurs = source de vérité, stables."""

from enum import StrEnum


class GatheringType(StrEnum):
    """M6 §3 — nature de la rencontre : un rassemblement *pour* quelque chose, pas une horloge."""

    MEETING = "meeting"  # réunion (de cellule)
    TRAINING = "training"  # formation
    SERVICE = "service"  # culte
    EVENT = "event"  # événement


class GatheringStatus(StrEnum):
    OPEN = "open"  # saisie possible
    CLOSED = "closed"  # figée (la trajectoire est arrêtée)


class AttendanceMark(StrEnum):
    """On n'enregistre que les **signaux** ; l'absence est déduite (M6 §3)."""

    PRESENT = "present"
    EXCUSED = "excused"  # absence pré-déclarée (M6-2)


class AttendanceSource(StrEnum):
    """Qui a produit le signal — trace la « conversation à deux voix » (M6 §2)."""

    LEADER = "leader"  # pointé par le responsable
    SELF = "self"  # self-check-in du membre (M6-1)
    DECLARED = "declared"  # présence déclarée via le compagnon du sermon (S-4) — confiance la plus
    # basse : **additive**, n'éteint JAMAIS une alerte « sans nouvelles ». Un scan reste roi.


class AbsenceReason(StrEnum):
    """Tags d'absence (M6-2) — on **tape un tag**, on n'écrit pas ; exploitable par M7.

    La plupart = « je reviens » ; `MOVED` est **structurel** (M7 pourra ajuster l'effectif).
    """

    SICK = "sick"  # malade
    TRAVEL = "travel"  # voyage
    WORK = "work"  # travail
    FAMILY = "family"  # famille (événement, deuil…)
    STUDIES = "studies"  # études / examens
    UNAVAILABLE = "unavailable"  # empêchement de dernière minute
    MOVED = "moved"  # déménagement — structurel
    OTHER = "other"  # autre (note libre optionnelle)


class AbsenceSource(StrEnum):
    """**Qui** a posé l'absence — la dignité de prévenir, ou une annonce faite pour vous.

    `ANNOUNCEMENT` marque une **neutralisation** : le membre n'a rien déclaré, c'est l'église qui
    sait pourquoi il ne sera pas là (deuil, maladie, voyage annoncés). Même effet sur le roster,
    origine différente — et c'est l'origine qui rend le rejeu d'une annonce idempotent."""

    SELF_DECLARED = "self_declared"
    ANNOUNCEMENT = "announcement"


class AbsenceOutcome(StrEnum):
    """Comment une absence s'est terminée — jamais dérivé à l'affichage, toujours stocké.

    `NO_RETURN` n'accuse personne : il dit qu'on attendait quelqu'un et qu'on ne l'a pas revu.
    C'est ce qui appellera un geste, une fois le moteur de signaux construit."""

    RETURNED = "returned"  # revenu(e) — la fin heureuse
    NO_RETURN = "no_return"  # l'échéance est passée, pas de retour constaté
    DECEASED = "deceased"  # clos par un décès annoncé (l'absorbant)


class WatchExclusionReason(StrEnum):
    """Pourquoi une personne est **définitivement** hors veille."""

    DECEASED = "deceased"
