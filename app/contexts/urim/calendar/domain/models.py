"""Ce qui a le droit de traverser la frontière — et rien d'autre.

Deux formes seulement, toutes deux **non nominatives**. Elles alimentent **l'affichage**,
jamais le moteur : un fait s'affiche à côté du texte, il ne pèse pas sur une proposition de
thème. Recherche oui, génération non.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

#: Seuil de confidentialité : aucun agrégat sous cinq personnes ne traverse.
#: Doublé d'un `CHECK (headcount >= 5)` en base — il tient même si l'adaptateur se trompe.
CONFIDENTIALITY_THRESHOLD: int = 5


class EcclesialEventKind(StrEnum):
    """**Liste blanche** de huit types. Tout type ajouté plus tard est invisible par défaut.

    Les codes restent en **anglais**, comme le reste du vocabulaire d'événements — seul
    l'affichage est traduit.
    """

    WEDDING = "WEDDING"
    BAPTISM = "BAPTISM"
    SPECIAL_SERVICE = "SPECIAL_SERVICE"
    WORSHIP_NIGHT = "WORSHIP_NIGHT"
    FAST = "FAST"
    MEMORIAL_SERVICE = "MEMORIAL_SERVICE"
    CONVENTION = "CONVENTION"
    #: Campagne d'évangélisation (S15, ajouté 2026-08-04). Absent de la liste initiale, il
    #: était donc **invisible par défaut** — le bon comportement (*fail closed*), mais il
    #: fallait le décider. C'est l'événement qui remplit le module Mission ; le pasteur a
    #: besoin de le voir à côté de son texte.
    EVANGELISM = "EVANGELISM"


@dataclass(frozen=True, slots=True)
class EcclesialEvent:
    """Un événement déclaré de l'église — aucune personne, jamais."""

    kind: EcclesialEventKind
    occurs_on: date
    label: str | None = None


@dataclass(frozen=True, slots=True)
class AggregateSignal:
    """Un agrégat de veille — un nombre, un sujet, une fenêtre. **Aucun identifiant.**"""

    topic: str
    headcount: int
    window_days: int

    def __post_init__(self) -> None:
        if self.headcount < CONFIDENTIALITY_THRESHOLD:
            raise ValueError(
                f"agrégat sous le seuil de confidentialité "
                f"({self.headcount} < {CONFIDENTIALITY_THRESHOLD}) — il ne traverse pas"
            )
