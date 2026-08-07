"""La bordure — tout ce que le moteur ne sait pas faire lui-même.

`UrimEngine.run` est **pure** : aucune écriture, aucun réseau, aucune horloge. Tout passe
par ici, y compris `clock` — le déterminisme l'exige.

⚠️ **`EcclesialContextPort` — AFFICHAGE SEUL.** Il est déclaré dans `EngineDeps` pour être
transmis à la couche de présentation, **jamais consommé par un étage**. Un texte se choisit
sur le texte, pas sur les tourments de l'assemblée : le jour où un étage lit ce port, Dorea
propose un thème à partir de la veille — exactement ce que le produit refuse. Un test le
vérifie par inspection du bytecode (`test_aucun_etage_ne_lit_le_contexte_ecclesial`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Protocol
from uuid import UUID

from app.contexts.urim.calendar.domain.ports import EcclesialContextPort
from app.contexts.urim.engine.state import Bounds, Reference


class Clock(Protocol):
    def __call__(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class ReferenceCheck:
    """Ce que le corpus répond quand on lui soumet une référence — et **pourquoi**, s'il dit non.

    Le motif n'est pas une commodité de journalisation : c'est lui qui s'affiche au pasteur quand
    un candidat est écarté. « 1 Corinthiens 5 compte 13 versets » lui apprend quelque chose ;
    « référence invalide » le laisse chercher."""

    exists: bool
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class CitationCandidate:
    """Un passage que le corpus reconnaît derrière une citation approximative.

    `score` sert **uniquement** à comparer des candidats entre eux — jamais à décider seul. Un
    score médiocre partout n'est pas un échec : c'est le diagnostic de la conflation de mémoire."""

    reference: Reference
    score: float
    rationale: str


@dataclass(frozen=True, slots=True)
class PericopeView:
    """Une **unité littéraire curée**, telle que l'étage du bornage la lit.

    `rationale` n'est pas une note interne : c'est `pericope.rationale NOT NULL`, la phrase que
    le pasteur lit pour comprendre *pourquoi* ces bornes-là. Une péricope sans motif ne devrait
    pas exister — la base l'interdit, et cet étage s'appuie dessus pour motiver chaque option."""

    id: UUID
    bounds: Bounds
    label: str
    rationale: str


@dataclass(frozen=True, slots=True)
class ReferenceSpan:
    """Un nom de livre reconnu, et **où il commence et finit** dans la saisie.

    `stop` suit la convention Python : premier index **après** le dernier token du nom. Un nom
    peut couvrir plusieurs mots — « 1 Rois », « Cantique des cantiques »."""

    book: str
    start: int
    stop: int


class CorpusReader(Protocol):
    """Lecture seule du corpus **immuable** — versions, texte, original, concordance.

    Les trois lectures ajoutées pour le détecteur d'entrée (S33) sont volontairement **maigres** :
    elles rendent un nom de livre ou une proportion, jamais un candidat ni un score composite. Le
    corpus répond à des questions de fait ; c'est l'étage qui décide. Toutes trois sont
    déterministes à `snapshot()` constant — l'invariant du moteur en dépend."""

    def snapshot(self) -> str: ...

    def find_reference_span(self, tokens: Sequence[str]) -> ReferenceSpan | None:
        """Le nom de livre reconnu **et l'empan contigu qu'il occupe**, ou `None`.

        Lu dans `book_name.abbreviations` — **la table, jamais une regex**. L'empan est rendu
        parce que le code seul ne suffit pas (S35) : `Job`, `Nombres`, `Juges`, `Actes`, `Rois`
        sont des mots français courants. « mon job me prend tout mon temps » contient un nom de
        livre et n'est pas une référence ; c'est la **contiguïté** avec des chiffres, ou le fait
        de couvrir toute la saisie, qui fait la différence. L'étage tranche ; le port se contente
        de dire où le nom commence et où il finit."""
        ...

    def scripture_affinity(self, tokens: Sequence[str]) -> float:
        """Entre 0 et 1 — à quel point cette suite de mots ressemble au texte biblique.

        Trigrammes et ancres rares (`idf`) sur `verse.body_norm`. C'est un **indice de surface**,
        pas une résolution : identifier le passage reste le travail de l'étage 1."""
        ...

    def parse_reference_candidates(self, tokens: Sequence[str]) -> Sequence[Reference]:
        """Les références que cette suite de mots peut désigner — **plusieurs, souvent**.

        « Jean 3:16 » désigne l'évangile ; mais « Jean » seul peut aussi ouvrir sur 1, 2 et
        3 Jean, et « Roi » sur les deux livres des Rois (S24). Le port rend tous les candidats
        plausibles ; c'est l'étage qui écarte et, s'il en reste plusieurs, qui rend la main."""
        ...

    def check_reference(self, reference: Reference) -> ReferenceCheck:
        """Cette référence existe-t-elle — et sinon, **pourquoi** (S19).

        Livre inconnu, chapitre hors du livre, verset hors du chapitre : trois faits, pas trois
        ambiguïtés. Le moteur n'interrompt jamais pour un fait ; il écarte le candidat avec son
        motif et continue. *Écarter en silence laisserait le pasteur chercher son verset
        disparu.*"""
        ...

    def resolve_citation(self, tokens: Sequence[str]) -> Sequence[CitationCandidate]:
        """Les passages que le corpus reconnaît derrière une citation approximative.

        Trigrammes et ancres rares. Rendus **triés du meilleur au moins bon** — l'étage compare
        les deux premiers pour savoir s'il tient un vainqueur ou une mémoire fusionnée."""
        ...

    def pericopes_for(self, reference: Reference) -> Sequence[PericopeView]:
        """Les unités littéraires curées que ce passage **rencontre**, dans l'ordre du canon.

        Rendues toutes, y compris quand la demande n'en touche qu'une partie : c'est la relation
        entre la demande et ces unités qui décide s'il y a quelque chose à arbitrer, et cette
        décision appartient à l'étage. Une liste vide n'est pas une erreur — c'est un passage
        hors du corpus curé, et le moteur continue quand même."""
        ...

    def context_for(self, pericope_id: UUID) -> Sequence[ContextNote]:
        """Le contexte historique et littéraire de cette unité — **sourcé, ou rien**."""
        ...

    def known_words(self, tokens: Sequence[str]) -> int:
        """Combien de ces mots **la langue** connaît — un décompte, pas une proportion (S34).

        ⚠️ **Le lexique de la langue, pas celui du corpus biblique.** `idf` ne convient pas : il
        est bâti sur l'Écriture, et le vocabulaire d'une conviction sur l'église d'aujourd'hui est
        précisément celui qui n'y figure pas — *voiture*, *réseaux*, *chômage*, *quartier*. Une
        simulation l'a montré : deux mots retirés du lexique biblique suffisaient à faire déclarer
        une phrase française parfaitement lisible incompréhensible.

        Un **décompte** et non un ratio, pour la même raison : un token pourri sur neuf ne doit
        rien peser. La question n'est pas *« quelle proportion est du français ? »* mais
        *« y a-t-il quelque chose de reconnaissable là-dedans ? »*."""
        ...


@dataclass(frozen=True, slots=True)
class AxisBearing:
    """Ce qu'une péricope **porte** d'un axe doctrinal — curé, sourcé, relu.

    `strength` a quatre valeurs, et la quatrième est celle qui distingue Urim d'un moteur de
    proof-texting :

    | valeur | ce que le texte fait de cet axe |
    | :-- | :-- |
    | `dominant` | il en est le sujet |
    | `porte` | il le soutient |
    | **`resiste`** | il le **complique ou le contredit** |
    | `absent` | il n'en dit rien |

    `absent` et `resiste` sont **opposés**, pas voisins : ne rien dire n'est pas résister. C'est
    précisément la valeur qui manquait au schéma d'origine, et sans elle le mode conviction était
    inconstructible."""

    axis_code: str
    label: str
    strength: str
    rationale: str


@dataclass(frozen=True, slots=True)
class DoctrinalAxis:
    """Un des dix loci de la théologie systématique, tel que la table de référence le nomme.

    `ordinal` porte l'ordre canonique (Dieu → … → les choses dernières), qui est aussi celui
    d'un plan de catéchèse. L'écran peut trier par force **ou** par ordre sans coder l'un ou
    l'autre en dur."""

    code: str
    label: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class BearingSite:
    """Une unité qui **porte** un axe — ou qui lui **résiste**. Le chemin inverse de `bearings`.

    ⚠️ Les résistantes voyagent avec les portantes, **au même rang** (§7). C'est la seule
    protection du mode conviction : elle ne dépend pas de la justesse de l'axe choisi. Un
    pasteur qui retient *guérison* verra quand même 2 Co 12:7-10 — et c'est précisément ce
    qui empêche Urim d'être un moteur de proof-texting."""

    pericope_id: UUID
    label: str
    bounds: Bounds
    strength: str
    rationale: str


class DoctrineReader(Protocol):
    """Axes portés par un passage, mises en garde **curées** (jamais générées)."""

    def axes(self) -> Sequence[DoctrinalAxis]:
        """Les dix loci, dans l'ordre canonique.

        C'est l'**écran de base** du mode conviction, pas un écran de secours (S12) : le
        pasteur peut toujours désigner son axe lui-même, et l'étape modèle ne fait que
        pré-remplir un choix qu'il pouvait déjà faire. C'est ce qui rend Urim livrable sans
        aucun modèle branché."""
        ...

    def sites_for_axis(self, axis_code: str) -> Sequence[BearingSite]:
        """Les unités curées qui **disent quelque chose** de cet axe — portantes et résistantes.

        Jamais celles qui n'en disent rien : `absent` est une information sur le texte, pas un
        candidat à prêcher. Une liste vide n'est pas une erreur — c'est le plafond dur du
        corpus curé, et il se dit franchement (S3)."""
        ...

    def bearings(self, pericope_id: UUID) -> Sequence[AxisBearing]:
        """Les pesées doctrinales de cette unité — toutes, y compris celles qui résistent.

        Rendues telles qu'elles ont été relues (`reviewed_by NOT NULL`). L'étage n'en pondère
        aucune : il les range, il ne les juge pas."""
        ...

    def caveats(self, pericope_id: UUID) -> Sequence[str]:
        """**Ce que le texte ne dit pas.** Exégétique, ou confessionnel.

        D-F : un caveat confessionnel s'affiche **toujours**, y compris quand la tradition de
        l'église est inconnue — la formulation le rend possible (« ici les traditions divergent »,
        jamais « votre tradition dit X »). Une unité sans caveat n'affiche rien : le vide est un
        état normal, jamais une improvisation."""
        ...

    def dominant_axis(self, pericope_id: UUID) -> str | None:
        """L'axe `dominant` de cette péricope, s'il a été curé.

        ⚠️ **Lu par l'étage 2, et ce n'est pas une entorse à l'ordre du pipeline** (S18). C'est un
        **port de lecture** sur le corpus curé — pas la sortie de l'étage 5. *L'ordre contraint le
        flux d'état, pas l'accès aux ports.* L'étage 5 reste seul à **interpréter** les axes et à
        porter les mises en garde ; l'étage 2 ne fait que s'en servir pour ordonner des options.

        `None` hors péricopes curées : les options sortent alors **sans ordre, jamais en erreur**
        — c'est la dégradation silencieuse voulue par S18."""
        ...


@dataclass(frozen=True, slots=True)
class Feasibility:
    """Un couple **plan x matière** sur une péricope, et ce qu'il vaut.

    La faisabilité n'est pas une propriété du texte : c'est celle d'un **triplet**. Le même
    passage est faisable en expositif et refusé en biographique — `Romains 8:9-17` ne porte aucun
    personnage, donc `x biographique` ne produit pas un plan, il produit un **refus motivé**.

    La contrainte `refus_motive` en base interdit `feasible = false` sans `refusal_reason` : un
    refus muet est un refus qu'on ne peut pas contester. Et depuis S39, la table porte aussi
    `reviewed_by NOT NULL` — **c'est la seule table curée dont le contenu oppose un refus à
    quelqu'un**, donc la dernière où une décision devrait rester anonyme."""

    plan_source: str
    subject_matter: str
    feasible: bool
    refusal_reason: str
    proof_text_risk: str


@dataclass(frozen=True, slots=True)
class ContextNote:
    """Un élément de contexte — **sourcé, ou absent**. Il n'y a pas de troisième possibilité.

    `kind` sépare les deux natures que la spec nomme, parce qu'elles ne se lisent pas au même
    moment : l'**historique** situe (« la lettre est écrite avant le voyage »), le **littéraire**
    explique la construction. Un passage sans note n'affiche **rien** — le vide est un état
    normal, jamais une improvisation.

    Table `urim_corpus_context_note`, définie le 2026-08-06 (S40) : elle manquait, et l'étage 4
    travaillait contre un port dont rien ne fixait la forme."""

    kind: str
    body: str
    source_ref: str


class HomileticsReader(Protocol):
    """Faisabilité d'un couple (source de plan croisée avec matière) — un refus est motivé."""

    def couples_for(self, pericope_id: UUID) -> Sequence[Feasibility]:
        """Les couples relus sur cette unité — **les faisables et les refusés**.

        Les refusés voyagent avec : *une combinaison impossible est signalée, jamais fabriquée*.
        Les cacher laisserait le pasteur croire qu'on n'y a pas pensé."""
        ...

    def recently_preached_axes(self, author_id: UUID) -> Sequence[str]:
        """Les axes que cet auteur a prêchés récemment — lus dans **son** archive.

        E1 : l'étage du thème croise l'axe retenu et **l'historique**, jamais le calendrier
        ecclésial. `preached` est une donnée d'Urim, clée sur l'auteur — elle ne franchit aucun
        mur. Le calendrier, lui, s'affiche à côté, et le pasteur en tient compte lui-même."""
        ...


class VersionResolver(Protocol):
    """Arbitre domaine public / sous licence, et le plafond qui déclenche le repli."""

    def ceiling_reached(self) -> bool: ...

    def is_metered(self, version_id: UUID) -> bool:
        """Cette version compte-t-elle dans le plafond ?

        La contrainte `licence_coherente` garantit qu'une version du domaine public répond
        toujours **non** — c'est elle qui rend le repli increvable."""
        ...

    def public_domain_fallback(self) -> UUID:
        """La version sur laquelle on retombe — **jamais plafonnée, par construction**.

        `licence_coherente` interdit qu'une version du domaine public soit `metered`. Le filet ne
        peut donc pas céder : il n'existe aucun état de la base où le repli serait lui-même
        bloqué. C'est une règle produit écrite dans un `CHECK`, pas une intention de code."""
        ...


class ConvictionReader(Protocol):
    """Ce qu'un modèle peut apporter au mode conviction — et **rien de plus** (S12, S37).

    Deux lectures, aucune décision. Le port existe pour que le modèle **accélère** un choix
    que le pasteur pouvait déjà faire seul, jamais pour le faire à sa place.

    ⚠️ **Propriété de sûreté** — c'est elle qui autorise ce port à exister :

        faux positif  → des textes résistants en plus, inoffensif
        faux négatif  → le comportement d'aujourd'hui
        modèle absent → idem, rien ne casse

    Elle ne tient que parce que ces deux méthodes ne peuvent **qu'ajouter de la protection**.
    Le jour où l'une d'elles écarte un texte ou choisit à la place du pasteur, la propriété
    tombe et le port devient dangereux."""

    def risk_flags(self, text: str) -> Sequence[str]:
        """Ce qui **relève le risque** dans cette formulation — jamais ce qui choisit le texte.

        Une intention déclarée (« je veux motiver », S26) et la charge d'une conviction (S20,
        S37) font la même chose : elles n'ajoutent aucun axe, elles élargissent l'ensemble des
        textes **résistants** et relèvent `proof_text_risk`.

        ⚠️ **Ne se lève que faute de référence.** Une saisie qui nomme son passage n'a pas de
        charge à peser : le pasteur a déjà dit sur quoi il prêche. Le drapeau nomme
        **l'effet**, jamais l'état de celui qui écrit — « formulation à forte charge,
        davantage de textes qui résistent sont affichés » se conteste ; « vous êtes dans la
        plainte » est un diagnostic, et S10 l'interdit."""
        ...

    def candidate_axes(self, text: str) -> Sequence[str]:
        """Les axes que cette intention **peut** toucher — plusieurs, jamais un « meilleur ».

        Une conviction est souvent une plainte, pas un thème : « trop de malades malgré les
        prières » touche la guérison *et* la prière sans réponse. Les rendre tous, au même
        rang, est la seule façon de ne pas interpréter le for intérieur du pasteur (S10).

        Vide = on ne sait pas, et l'étage retombe sur les dix loci — ce qui est l'écran normal."""
        ...


class NullConvictionReader:
    """Aucun modèle branché. **C'est un état de production, pas un mode dégradé** (S12).

    Architecture v2 §10 veut Urim utilisable hors ligne sur le domaine public : terrain
    tablette, connexion irrégulière. Le mode conviction reste alors entier — le pasteur
    désigne son axe parmi les dix loci, et rien dans le pipeline ne s'en aperçoit."""

    def risk_flags(self, text: str) -> Sequence[str]:
        return ()

    def candidate_axes(self, text: str) -> Sequence[str]:
        return ()


@dataclass(frozen=True, slots=True)
class EngineDeps:
    corpus: CorpusReader
    doctrine: DoctrineReader
    homiletics: HomileticsReader
    context: EcclesialContextPort  # ⚠ AFFICHAGE SEUL — jamais lu par un étage
    versions: VersionResolver
    clock: Clock

    #: Model-optional par construction : le défaut ne lit aucun modèle et ne casse rien.
    conviction: ConvictionReader = field(default_factory=NullConvictionReader)

    #: Le nom d'attribut interdit aux étages — source de vérité du test d'architecture.
    #:
    #: ⚠ **`ClassVar`, et il a fallu le premier étage réel pour s'en apercevoir.** Déclaré comme
    #: champ dans un dataclass `slots=True`, il était deux fois faux : il devenait un paramètre du
    #: constructeur, et l'accès de classe rendait un `member_descriptor` au lieu du tuple. Le test
    #: qui le lit ne plantait pas parce que `PIPELINE` était vide — il était **vrai par vacuité**,
    #: exactement comme son en-tête le disait. Le jour où un étage est entré dans le pipeline, le
    #: garde le plus important du dépôt s'est révélé cassé.
    FORBIDDEN_FOR_STAGES: ClassVar[tuple[str, ...]] = ("context",)


@dataclass(frozen=True, slots=True)
class Decision:
    """La réponse du pasteur après un `AWAIT` — elle entre dans l'état, le pipeline repart."""

    stage_code: str
    option_code: str
    decided_by: UUID
    changes: tuple[tuple[str, object], ...] = ()

    def apply_to(self, state):
        return state.with_(**dict(self.changes)) if self.changes else state
