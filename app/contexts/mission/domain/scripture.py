"""La **référence** d'un verset — l'os du garde-fou M9-1.

Le générateur de carte ne manipule que des **références** (livre, chapitre, verset) : l'IA
*retrouve* la référence à partir d'une citation floue, puis une Bible canonique donne le **texte
exact**. La référence est donc le seul pont entre le moteur IA et l'Écriture — jamais le texte.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


def normalize_book(name: str) -> str:
    """Clé de comparaison d'un nom de livre : minuscules, sans accent, sans espace.

    « Ésaïe », « esaie », « ESAÏE » → « esaie ». Rend le rapprochement robuste entre ce que
    renvoie l'IA et les clés de la Bible embarquée / du dataset.
    """
    stripped = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return "".join(stripped.lower().split())


@dataclass(frozen=True)
class VerseReference:
    """Livre + chapitre + verset. `book` porte le libellé d'affichage (accentué)."""

    book: str
    chapter: int
    verse: int

    @property
    def label(self) -> str:
        return f"{self.book} {self.chapter}.{self.verse}"

    @property
    def key(self) -> tuple[str, int, int]:
        """Clé normalisée pour la recherche dans une source d'Écriture."""
        return (normalize_book(self.book), self.chapter, self.verse)
