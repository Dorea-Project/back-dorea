"""Ports du contexte Mission vers l'extérieur."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.contexts.mission.domain.scripture import VerseReference


class InvitationCodeGenerator(ABC):
    @abstractmethod
    def generate(self) -> str: ...


class VerseResolver(ABC):
    """Le **moteur IA** (M9-1) : d'une citation floue → la **référence** (jamais le texte).

    C'est tout le garde-fou : le résolveur ne rend que livre/chapitre/verset ; le texte vient
    ensuite d'une `ScriptureSource` canonique. `None` si aucune référence n'a pu être reconnue."""

    @abstractmethod
    async def resolve(self, query: str) -> VerseReference | None: ...


class ScriptureSource(ABC):
    """La Bible **canonique** (Louis Segond 1910, domaine public) : la référence → le texte exact.

    Jamais la mémoire de l'IA — zéro hallucination sur l'Écriture. `None` si la référence n'est pas
    couverte par la source."""

    @abstractmethod
    async def text_of(self, ref: VerseReference) -> str | None: ...

    @abstractmethod
    def all_references(self) -> list[VerseReference]:
        """Les références disponibles — sert au repli par mots-clés (sans IA)."""
        ...


class CardRenderer(ABC):
    """Compose la **carte designée** (fond + typographie du verset) et rend ses octets."""

    @abstractmethod
    def render(self, *, reference_label: str, verse_text: str) -> tuple[bytes, str]:
        """Renvoie (octets, content_type) de la carte."""
        ...


class InviterDirectory(ABC):
    """Résout le **visage** de la carte (nom de la personne / du groupe) et le nom de l'église.

    Mission lit iam / groups / tenant à travers ce port : la carte publique nomme qui invite et
    quelle église, sans exposer autre chose."""

    @abstractmethod
    async def person_label(self, account_id: UUID) -> str | None: ...

    @abstractmethod
    async def group_label(self, group_id: UUID) -> str | None: ...

    @abstractmethod
    async def church_label(self, tenant_id: UUID) -> str | None: ...
