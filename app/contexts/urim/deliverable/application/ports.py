"""Ce dont le livrable a besoin et qu'il ne sait pas faire lui-même.

Deux ports, et le second existe à cause d'une découverte : **l'index du corpus ne tient le texte
que de la version de repli** (`load_corpus_index` filtre sur `version_id == repli.id`). Q9 exige
de juger contre *toutes* les versions détenues — le texte des autres doit donc venir d'ailleurs.

Il vient de la base, et c'est le bon endroit : le contrôle de citation est un geste **rare et
explicite** (quelques diapositives, une fois par livrable), pas un chemin chaud. Charger quatre
versions entières dans l'index pour cela ferait payer à chaque résolution le prix d'un contrôle
qui a lieu une fois par semaine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TexteServi:
    """Le texte d'un passage **dans une version**, tel que le corpus le porte."""

    version_id: UUID
    label: str
    texte: str


@dataclass(slots=True)
class DiapositiveSoumise:
    """Ce que le pasteur a composé pour l'écran — avant tout jugement."""

    titre: str
    reference: str
    texte_projete: str


@dataclass(slots=True)
class ControleRecord:
    """Une ligne de `urim_citation_check` — **l'archive de ce qui est monté à l'écran**.

    C'est elle qui dispense de conserver le fichier : on sait exactement ce qui a été projeté,
    sous quelle référence et contre quelle version, sans garder un octet de binaire."""

    slide_no: int
    reference: str
    projected_text: str
    verdict: str
    rationale: str
    version_id: UUID | None = None


@dataclass(slots=True)
class LivrableRecord:
    id: UUID
    preparation_id: UUID
    kind: str
    format: str
    generated_at: datetime
    validation: str
    validated_by: UUID | None = None
    validated_at: datetime | None = None
    corpus_snapshot: str | None = None
    content_fingerprint: str | None = None


class VerseTextReader(Protocol):
    async def textes(
        self,
        *,
        book_id: int,
        chapter: int,
        verse_start: int | None,
        verse_end: int | None,
        prefer_version_id: UUID | None = None,
    ) -> list[TexteServi]:
        """Le passage **dans chaque version détenue**, la préférée en tête.

        L'ordre est une préférence, pas une priorité : `juger_parmi` fait gagner `exact` sur
        `extrait` quel que soit le rang."""
        ...


class DeliverableRepository(Protocol):
    async def add(self, record: LivrableRecord, controles: list[ControleRecord]) -> None:
        """Le livrable **et ses contrôles**, dans le même geste.

        Séparer les deux écritures permettrait un livrable `conforme` sans les lignes qui le
        prouvent — un verdict sans son dossier."""
        ...

    async def get(self, deliverable_id: UUID) -> LivrableRecord | None: ...

    async def controles(self, deliverable_id: UUID) -> list[ControleRecord]: ...
