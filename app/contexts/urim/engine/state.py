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
class AxisGloss:
    """Un locus **dit dans la langue de celui qui écrit**.

    Le pasteur qui tape « Dieu veut délivrer les malades de mon église, on prie et rien ne
    change » ne pense pas *théologie propre* — il pense *la prière sans réponse*. Lui rendre le
    nom grec, c'est lui demander de traduire sa propre plainte en vocabulaire d'école avant
    qu'Urim ne l'aide.

    ⚠️ **Le titre habille, il ne remplace pas.** `code` reste le locus : la décision qu'il
    prend, les pesées qui suivront et le thème proposé travaillent tous sur lui. Si la glose
    est mauvaise, le pasteur choisit quand même le bon axe — c'est la même propriété de sûreté
    que partout ailleurs, *un modèle qui ne peut qu'ajouter une phrase ne peut pas nuire*."""

    code: str
    title: str
    gloss: str


@dataclass(frozen=True, slots=True)
class PassageSuggestion:
    """Un passage proposé **par le sens**, quand la lettre n'a rien trouvé.

    ⚠️ **Ce n'est pas ce que `resolve()` a l'interdiction de faire, et la différence est
    entière.** Un modèle qui rend UN verset pour un sujet, que le moteur pose ensuite comme
    résolu, ferme la question avant qu'elle ne s'ouvre — c'est le proof-texting même, et
    `_SYSTEME_REFERENCE` le refuse explicitement.

    Ici il en rend **plusieurs**, ils arrivent comme des *options*, et le pasteur tranche. Une
    fois son choix fait, le pipeline entier reprend : bornage, pesées, mises en garde, et les
    textes qui **résistent**. La proposition n'abrège rien, elle donne un point de départ là où
    il n'y avait qu'un refus.

    `rationale` dit pourquoi ce passage traite le sujet — sans quoi le pasteur choisirait une
    référence sur son seul nom, ce qui est précisément la façon dont on cite mal."""

    reference: Reference
    rationale: str


@dataclass(frozen=True, slots=True)
class TraceEntry:
    """Le motif d'un étage — jamais vide (cf. `StageResult`)."""

    stage_code: str
    rationale: str


@dataclass(frozen=True, slots=True)
class StudyState:
    session_id: UUID
    #: **Aucun étage ne la lit** — elle voyage pour la trace, pas pour la décision. C'est ce
    #: qui a rendu l'antichambre gratuite : le moteur était déjà indifférent à l'église, et
    #: `None` ne change donc rien à ce qu'il calcule.
    church_id: UUID | None
    author_id: UUID
    corpus_snapshot: str  # version du corpus — clé du déterminisme

    #: **`None` par défaut, et c'est le cas normal** — le pasteur n'indique aucun mode.
    #:
    #: Il n'y a plus d'onglet : un champ, et le moteur reconnaît. `entry_mode` ne porte donc
    #: plus « ce que le client a coché » mais **« ce que le pasteur a tranché »** — et il ne
    #: peut être posé que par une correction explicite (« ce n'est pas ça »). La différence
    #: n'est pas cosmétique : tant qu'un défaut le remplissait d'office, l'étage 0 posait une
    #: question de désaccord à quelqu'un qui n'avait rien dit, et la reposait indéfiniment
    #: puisque la trace n'est pas persistée et qu'il se ré-exécute à chaque rejeu.
    #:
    #: ⚠️ Trois étages le lisent — `route_entry`, `resolve_passage.applies`,
    #: `weigh_conviction.applies`. Un `None` qui survivrait à l'étage 0 arrêterait le pipeline
    #: en silence : c'est l'invariant que `route_entry` doit toujours poser un mode.
    entry_mode: EntryMode | None
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

    #: Loci que le modèle **suggère** pour une intention — il annote, il n'écarte jamais.
    #:
    #: ⚠️ **Pourquoi ce champ existe alors qu'un port le prévoyait déjà.** `ConvictionReader`
    #: est synchrone, parce que le moteur l'est ; Mistral est asynchrone. `get_study_service`
    #: câblait donc `resolver=` et laissait `conviction=` sur `NullConvictionReader` — le
    #: modèle était branché sur le chemin référence et sur rien du côté intention. Une saisie
    #: comme « Salut » sortait avec dix loci portant tous la même phrase creuse.
    #:
    #: Le contournement est celui de `risk_flags` : l'appel se fait à la bordure, et l'état
    #: rejoué porte le résultat. Le moteur reste pur et rejouable, et le port synchrone garde
    #: son sens — il sert le cas hors ligne, où rien n'a pu être demandé à personne.
    #:
    #: La propriété de sûreté de S37 tient parce que l'étage **réunit** les deux sources et
    #: n'en retire jamais : dix loci entrent, dix loci sortent, certains mieux motivés.
    #:
    #: Chaque entrée porte en plus un **titre et une glose dans la langue du pasteur** :
    #: « théologie propre » devient « La prière sans réponse — ce que devient la foi quand rien
    #: ne vient ». Le nom grec ne disparaît pas, il passe à l'écran du texte, où c'est la
    #: discipline qui parle ; l'écran de l'intention parle, lui, la langue de celui qui écrit.
    #: Le `code` reste le locus, donc rien en aval ne s'aperçoit du changement.
    suggested_axes: tuple[AxisGloss, ...] = ()

    #: Passages proposés **par le sens**, quand la lettre n'a rien trouvé — voir
    #: `PassageSuggestion`. Ils ne résolvent rien : ils remplissent une liste d'options là où
    #: le moteur rendait un refus.
    suggested_passages: tuple[PassageSuggestion, ...] = ()

    #: ⚠️ **Ce que le modèle a cru lire — une proposition, jamais une résolution.**
    #:
    #: 🔴 La bordure posait cette trouvaille directement dans `resolved`. Le pasteur qui tapait
    #: `Hébreux 2:29` — une note réelle, dans un chapitre qui compte 18 versets — recevait
    #: **Hébreux 2:9** et l'écran du bornage. Le moteur, lui, savait dire *« Hébreux 2 compte 18
    #: versets, il n'y a pas de verset 29 »* : la seule chose utile, effacée par une correction
    #: silencieuse. Et `Zorobabel 3:5` rendait un refus **avec** `resolved = Esdras 3:5` — un
    #: enregistrement qui pointait vers un texte que personne n'avait nommé.
    #:
    #: Le fait reste donc le motif, et la trouvaille devient une **option**. C'est le patron du
    #: chemin citation — *le refus devient une proposition* — et la règle de l'étage 0 : *le
    #: calcul propose, la personne dispose*.
    #:
    #: ⚠️ Elle ne remplace pas `resolved` sur les chemins où le moteur n'a **rien à dire** : une
    #: citation de mémoire, une paraphrase, un personnage nommé autrement que dans la traduction
    #: continuent de se résoudre. On ne propose que là où l'on avait un fait à taire.
    suggested_reference: Reference | None = None

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
