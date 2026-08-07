"""L'état d'une préparation — **immuable**, enrichi étage après étage.

Chaque étage renvoie un *nouvel* état ; rien n'est muté. La `trace` accumule le motif de
chaque étage : c'est elle qui s'affiche au pasteur, et c'est elle qui rend une préparation
rejouable. `corpus_snapshot` est la clé du déterminisme — même entrée, même version de
corpus, même sortie.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID


class EntryMode(StrEnum):
    """Par où le pasteur entre dans le texte."""

    REFERENCE = "reference"  # « Romains 8:10-15 »
    CITATION = "citation"  # une phrase citée, parfois écorchée
    CONVICTION = "conviction"  # une intention, pas encore un texte


class EntryOrigin(StrEnum):
    """**Comment** la saisie est arrivée — et c'est une information, pas une déduction (S36).

    Le cas qui l'a rendue nécessaire : un micro resté ouvert transcrit une conversation, et le
    moteur reçoit « Ma voiture 406, a besoin de reparation , jefgf Paradis ». Le détecteur peut
    s'acharner à comprendre ce texte — il n'y a rien à comprendre.

    Le système **sait** d'où vient la chaîne : le module de capture stocke déjà son `provider`.
    Il n'a donc pas à le déduire des mots. Une dictée qui ne produit pas un signal univoque se
    fait **confirmer** ; une saisie tapée, non."""

    TYPED = "typed"
    DICTATED = "dictated"


@dataclass(frozen=True, slots=True)
class Reference:
    """Un passage identifié — le passage, **pas** la version.

    Une référence se **précise par degrés**, et le pasteur entre à n'importe lequel :

    - `chapter = None` ⇒ **le livre entier** (« 1 Rois », « l'histoire de Jézabel ») — S23 ;
    - `verse_start = None` ⇒ **le chapitre entier** (« Galates 5 ») — S7 ;
    - sinon, le verset ou l'intervalle.

    Moins la référence est précise, plus le bornage a de choses à proposer (S8, S24).
    """

    book: str
    chapter: int | None = None  # None = livre entier
    verse_start: int | None = None  # None = chapitre entier
    verse_end: int | None = None

    @property
    def is_whole_book(self) -> bool:
        return self.chapter is None

    @property
    def is_whole_chapter(self) -> bool:
        return self.chapter is not None and self.verse_start is None


@dataclass(frozen=True, slots=True)
class Bounds:
    """L'unité littéraire retenue (péricope), qui peut déborder la demande."""

    start: Reference
    end: Reference


@dataclass(frozen=True, slots=True)
class TraceEntry:
    """Le motif d'un étage — jamais vide (cf. `StageResult`)."""

    stage_code: str
    rationale: str


@dataclass(frozen=True, slots=True)
class StudyState:
    session_id: UUID
    church_id: UUID
    author_id: UUID
    corpus_snapshot: str  # version du corpus — clé du déterminisme

    entry_mode: EntryMode
    raw_input: str

    #: Tapée ou dictée (S36). Par défaut tapée : une saisie dont on ignore l'origine se traite
    #: comme la plus sûre des deux — c'est le sens du repli qui protège.
    entry_origin: EntryOrigin = EntryOrigin.TYPED

    #: Ce qui **relève le risque sans jamais choisir le texte** (S26, S37).
    #:
    #: Une intention déclarée (« je veux motiver ») et la charge émotionnelle d'une conviction
    #: font la même chose : elles n'ajoutent aucun axe, elles élargissent l'ensemble des textes
    #: **résistants** et relèvent `proof_text_risk`. La propriété de sûreté tient à ça — un
    #: signal qui ne peut qu'**ajouter de la protection** ne peut pas nuire en se trompant :
    #:
    #:     faux positif  → des résistants en plus, inoffensif
    #:     faux négatif  → le comportement d'aujourd'hui
    #:     modèle absent → idem, rien ne casse
    #:
    #: ⚠️ **Le motif nomme l'effet, jamais l'état de celui qui écrit.** « Formulation à forte
    #: charge — davantage de textes qui résistent sont affichés » se vérifie et se conteste ;
    #: « vous êtes dans la plainte » est un diagnostic, et S10 l'interdit.
    risk_flags: tuple[str, ...] = ()

    #: Axes que le pasteur **refuse** explicitement (« mais je ne veux pas de X »), S18.
    #: Une contrainte négative ne refuse pas le texte : elle **ordonne les options de
    #: bornage** — on préfère des bornes dont l'axe dominant n'est pas celui-là. Vide =
    #: aucune contrainte. Hors péricopes curées, sans effet (dégradation silencieuse).
    refused_axes: tuple[str, ...] = ()

    resolved: Reference | None = None
    bounds: Bounds | None = None
    #: L'unité curée retenue — **`None` dès que le pasteur force ses bornes**.
    #:
    #: C'est ce champ qui rend S22 mécanique plutôt que déclaratif : tout ce qui est curé
    #: (pesées doctrinales, mises en garde, faisabilité homilétique) est clé sur la péricope.
    #: Sans identité, les étages 4 à 6 n'ont **rien à lire** — et ils dégradent au lieu de
    #: deviner. La liberté accordée au bornage se propage ainsi d'elle-même, sans qu'aucun étage
    #: n'ait à connaître la règle.
    pericope_id: UUID | None = None
    bounds_overridden: bool = False
    version_id: UUID | None = None
    axis: str | None = None
    plan_source: str | None = None
    subject_matter: str | None = None

    #: La proposition du dernier étage — **une proposition, jamais un titre imposé**. Elle se
    #: dérive du locus dominant, soutenue par les axes portés, en évitant ce qui résiste. Le
    #: pasteur la réécrit s'il veut : c'est son sermon.
    theme: str | None = None

    trace: tuple[TraceEntry, ...] = ()  # motif de chaque étage

    def with_(self, **kw) -> StudyState:
        return replace(self, **kw)
