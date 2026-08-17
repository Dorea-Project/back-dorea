"""Ports du contexte Mission vers l'extérieur."""

from abc import ABC, abstractmethod
from uuid import UUID

from app._shared.domain.locale import DEFAULT_LOCALE, Locale
from app.contexts.mission.domain.scripture import VerseReference


class InvitationCodeGenerator(ABC):
    @abstractmethod
    def generate(self) -> str: ...


class VerseResolver(ABC):
    """Le **moteur IA** (M9-1) : d'une citation floue → la **référence** (jamais le texte).

    C'est tout le garde-fou : le résolveur ne rend que livre/chapitre/verset ; le texte vient
    ensuite d'une `ScriptureSource` canonique. `None` si aucune référence n'a pu être reconnue.

    ⚠️ **`locale` n'est pas ici une langue d'interface — c'est le nom du livre.** « Jean » et
    « John » ne sont pas deux traductions du même mot : ce sont deux **clés de jointure**
    différentes (`VerseReference.key` → `normalize_book`). Demander « John » à une Bible indexée
    en français, c'est chercher un verset qui n'existe pas. D'où l'invariant du lot : la langue
    donnée ici est **toujours** celle de la Bible qui sera interrogée ensuite — jamais celle du
    lecteur si les deux diffèrent."""

    @abstractmethod
    async def resolve(
        self, query: str, *, locale: Locale = DEFAULT_LOCALE
    ) -> VerseReference | None: ...


class ScriptureSource(ABC):
    """Une Bible **canonique** en domaine public : la référence → le texte exact.

    Jamais la mémoire de l'IA — zéro hallucination sur l'Écriture. `None` si la référence n'est pas
    couverte par la source. Une source **est** une traduction : la Segond 1910 pour le français,
    la World English Bible pour l'anglais. On n'en interroge jamais une pour une référence
    nommée dans la langue d'une autre."""

    @abstractmethod
    async def text_of(self, ref: VerseReference) -> str | None: ...

    @abstractmethod
    def all_references(self) -> list[VerseReference]:
        """Les références disponibles — sert au repli par mots-clés (sans IA)."""
        ...


class ScriptureLibrary(ABC):
    """Les Bibles dont Dorea dispose, et **laquelle répond réellement** pour une langue donnée.

    🔴 C'est l'organe qui empêche le défaut central du bilingue biblique : un prompt anglais
    devant une Bible française. Le nom du livre que rend l'IA est la clé de recherche du texte ;
    si les deux ne parlent pas la même langue, l'IA reconnaît « John 3:16 » et la Bible ne trouve
    rien — l'anglophone reçoit une erreur là où il avait au moins une carte française avant.

    `serving()` tranche **une fois** : la langue rendue vaut pour le prompt *et* pour la Bible.
    Le jour où le dataset anglais n'est pas déployé, elle rend le français, et la carte sort —
    en français, ce qui est un service dégradé mais pas une panne."""

    @abstractmethod
    def serving(self, locale: Locale) -> Locale:
        """La langue réellement servie — celle demandée si une Bible existe, le repli sinon."""
        ...

    @abstractmethod
    def source(self, locale: Locale) -> ScriptureSource:
        """La Bible de cette langue. À appeler avec le retour de `serving`, jamais autrement."""
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
