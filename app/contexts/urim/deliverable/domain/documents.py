"""Les deux documents — et **la frontière qui les sépare, portée par les types**.

Le `.pptx` est ce que l'assemblée voit ; le `.docx` est la note du prédicateur. Le second n'est
pas le premier détaillé : ils ne s'adressent pas à la même personne, et une seule question les
sépare — *à qui cette phrase est-elle utile ?*

> Une mise en garde s'adresse au **prédicateur**. Une assemblée à qui l'on projette « ce texte
> ne dit pas ceci » reçoit un cours d'exégèse à la place d'une prédication, et un doute qu'elle
> n'a pas les moyens d'instruire.

## Pourquoi c'est un TYPE et non un filtre

Un filtre s'oublie. Il suffit qu'une refonte ajoute un champ pour qu'une mise en garde arrive à
l'écran sans que personne l'ait décidé.

**`Deck` n'a nulle part où mettre un caveat.** Une implémentation pressée *ne peut pas* en
projeter un — c'est la même parade que `TopicCount` côté veille, dont le type n'a aucun champ
d'identité pour que la fuite soit inconstructible plutôt qu'interdite.

## Le seuil — **corrigé le 2026-08-13 par trois prédications réelles**

Le seuil est *« le point central seul suffit »*, et il ne bouge pas. Ce qui a bougé, c'est
**l'élément qui le porte**.

La première rédaction s'adossait à la `proposition` de Braga — le sermon en une phrase. Trois
prédications réelles (`docs/temoins/`) ont montré que **pas une seule n'en contient**. Aucune ne
formule de proposition ; toutes ont un **thème** et des **divisions numérotées**. Le verrou aurait
donc refusé son document à exactement les trois pasteurs pour qui il est écrit — le même défaut
que la chaîne de textes, qui « n'avait aucune surface où s'exercer » parce que personne ne
soumettait ses appuis.

**Le thème ne peut pas non plus tenir ce rôle**, et c'est décisif : `propose_theme` le remplit
d'office (gabarit fermé, `axis + plan x matière`). Un verrou que le moteur satisfait lui-même
n'est pas un verrou.

> **Le seuil est donc une division** — un point du plan, écrit par lui.

Les trois témoins en portent respectivement trois, trois et quatre ; c'est la colonne vertébrale
observable d'une prédication. Et le moteur n'en écrit jamais aucune : *un plan qui arrive complet
n'est pas un plan que quelqu'un a préparé*.

⚠️ **On ne juge jamais son contenu.** Non vide après normalisation, un point. Aucune longueur
minimale, aucun décompte de divisions, aucun modèle consulté : une machine qui apprécierait la
valeur du plan d'un prédicateur serait la machine à sermons sous un autre nom, et cette fois avec
une note.

## Les codes, et pourquoi la liste reste ouverte en base

Les trois témoins portent des sections que Braga ne nomme pas — **objectif**, **définitions**,
**contexte du livre**, **NB**, **témoignage personnel** — et les nomment chacun à leur façon. La
colonne `preparation_element.element_code` reste donc **libre** : fermer la liste refuserait à un
pasteur la section qu'il tient depuis vingt ans. Seul le **code de la division** est connu du
livrable, parce que c'est lui que le verrou interroge.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Les dix éléments du squelette (Braga) — l'ordre que la spec fixe, et que l'écran propose.
ELEMENTS = (
    "titre",
    "introduction",
    "proposition",
    "phrase_interrogative",
    "phrase_de_transition",
    "divisions",
    "subdivisions",
    "illustrations",
    "application",
    "conclusion",
)

#: Ce que les prédications réelles portent **en plus**, et que Braga ne nomme pas
#: (`docs/temoins/`). Elles ne ferment rien : la colonne reste libre. Elles existent pour que
#: l'écran les **propose**, plutôt que de laisser un pasteur inventer un code par section.
ELEMENTS_OBSERVES = (
    "objectif",       # « Objectif : favorisant un retour aux fondamentaux » (Saint-Esprit)
    "contexte",       # datation, auteur, visée du livre — systématique en introduction
    "definitions",    # « Définition : A- un signe dans la Bible · B- la prière » (Signes)
    "nb",             # l'application immédiate, posée avant le plan (Signes)
    "temoignage",     # « Mon Témoignage » (Signes)
)

#: **Le seuil du livrable** — un point du plan, écrit par lui. Voir l'en-tête : ce n'est pas la
#: `proposition` (aucun témoin n'en contient) ni le `theme` (le moteur le remplit d'office).
POINT_CENTRAL = "divisions"


@dataclass(frozen=True, slots=True)
class Diapositive:
    """Ce que l'assemblée voit. **Trois champs, et pas un de plus.**

    `titre` est de lui. `texte_projete` est de lui aussi — il coupe, il abrège — mais il est
    **jugé** contre le corpus avant qu'un octet de fichier existe. `reference` est contrôlée."""

    titre: str
    reference: str
    texte_projete: str


@dataclass(frozen=True, slots=True)
class Deck:
    """Le `.pptx`.

    ⚠️ **Aucun champ pour une pesée, un motif, une mise en garde ou un risque de proof-texting.**
    C'est délibéré et c'est testé : la frontière du document tient dans la forme du type, pas
    dans la vigilance de celui qui l'assemble."""

    titre: str
    diapositives: tuple[Diapositive, ...]


@dataclass(frozen=True, slots=True)
class Note:
    """Le `.docx` — la note du prédicateur, où **tout** ce que le moteur a rassemblé a sa place.

    `signature` porte qui a relu la curation (`ia-mistral` ou un nom) et `corpus_snapshot`
    contre quel état le raisonnement a été mené : un document daté d'une curation qui a changé
    depuis n'est pas faux, il est **antidaté**, et rien à l'écran ne le dirait.

    ⚠️ **Mention de destination en pied de CHAQUE page** — pas une page de garde, qui ne
    survit ni à une capture d'écran, ni à un partage partiel, ni à une impression recto."""

    titre: str
    reference: str
    #: L'unité littéraire retenue et **le motif de son découpage**.
    unite: str
    motif_unite: str
    #: Le plan du pasteur : `(code Braga, texte)`, dans son ordre.
    plan: tuple[tuple[str, str], ...]
    #: Le texte servi par le corpus — jamais saisi, donc rien à falsifier.
    versets: tuple[tuple[str, str], ...]
    #: `(axe, force, motif)` — les dix, `absent` compris.
    pesees: tuple[tuple[str, str, str], ...]
    #: Ce que le texte **ne dit pas**.
    mises_en_garde: tuple[str, ...]
    #: `(plan x matiere, faisable, motif de refus, risque de proof-texting)`.
    faisabilites: tuple[tuple[str, bool, str, str], ...]
    #: Les textes qui **résistent**, venus d'ailleurs — au même rang que ceux qui portent.
    resistances: tuple[tuple[str, str], ...]
    #: `(référence, texte, verdict)` — la chaîne d'appuis, **saisies illisibles comprises**.
    appuis: tuple[tuple[str, str, str], ...]
    #: Les mots de l'original : `(référence, forme, lemme, nature, morphologie, ailleurs)`.
    #:
    #: ⚠️ **Il n'y a pas de traduction, et ce n'est pas un oubli.** MorphGNT n'en porte aucune,
    #: et les lexiques libres sont en anglais ; une glose produite par un modèle aurait l'air
    #: d'une source, et personne ne relit une définition grecque avant de la redire en chaire.
    #:
    #: Ce qui la remplace : **la référence** (on sait donc *où* le mot est employé) et
    #: **`ailleurs`**, les autres endroits où le même lemme paraît. C'est la concordance, et
    #: c'est la seule façon de dire ce qu'un mot porte sans rien inventer — la culture
    #: matérielle s'y enseigne par la récurrence.
    original: tuple[tuple[str, str, str, str, str, tuple[str, ...]], ...]
    #: Ce qui a été **écarté**, avec son motif : la moitié du dialogue qu'on oublie d'imprimer.
    ecartees: tuple[tuple[str, str], ...]
    signature: str | None
    corpus_snapshot: str | None


def point_central_renseigne(plan: dict[str, str | None]) -> bool:
    """Y a-t-il quelque chose de lui ? — **la question, et toute la question**.

    Ce n'est pas « a-t-il modifié ? ». Pour le vérifier il faudrait d'abord lui avoir donné un
    brouillon à modifier — donc **écrire le sermon à sa place pour constater qu'il l'a
    corrigé**, ce que ce produit refuse de faire. Et une espace en fin de ligne suffirait à
    passer n'importe quelle comparaison.

    ⚠️ **Le plan arrive en plusieurs lignes de même code** (`divisions` x ordinal 1, 2, 3) : le
    dictionnaire attendu ici est donc *déjà replié*, une entrée par code. Replier en gardant la
    première non vide suffit — on cherche l'existence, jamais le nombre."""
    return bool((plan.get(POINT_CENTRAL) or "").strip())
