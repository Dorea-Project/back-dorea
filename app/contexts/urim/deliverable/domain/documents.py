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

import re
import unicodedata
from dataclasses import dataclass

from app.contexts.urim.domain.squelette import (
    ELEMENTS,
    ELEMENTS_OBSERVES,
    POINT_CENTRAL,
)

#: Réexportés : le livrable s'en sert, il ne les possède pas. Le squelette appartient à la
#: **préparation** — `PUT /elements` l'écrit bien avant qu'un document existe.
__all__ = [
    "ELEMENTS",
    "ELEMENTS_OBSERVES",
    "POINT_CENTRAL",
    "Deck",
    "Diapositive",
    "MotOriginal",
    "Note",
    "mots_communs",
    "point_central_renseigne",
]

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


#: Les mots que toute phrase française porte — ils reviendraient dans n'importe quels versets
#: et ne diraient donc rien du mot grec qu'on cherche.
_OUTILS = frozenset(
    "le la les un une des du de d a à au aux et ou que qui quoi dont où ce cet cette ces "
    "il elle ils elles je tu nous vous on se sa son ses leur leurs mon ma mes ton ta tes "
    "est sont était fut sera être avoir a ont avait eu en y ne pas plus ni mais donc or car "
    "pour par avec sans sur sous dans vers chez comme si tout tous toute toutes".split()
)


def mots_communs(versets: tuple[str, ...], combien: int = 4) -> tuple[str, ...]:
    """Les mots que **tous** ces versets partagent — un fait, pas une traduction.

    ⚠️ **La nuance décide de ce qu'on a le droit d'afficher.** Dire *« πρῶτος signifie
    premièrement »* serait une glose, et il n'y en a pas dans ce dépôt. Dire *« ces trois
    versets ont en commun : premièrement, abord »* est une **observation vérifiable sur le
    texte français**, que le pasteur peut confirmer d'un coup d'œil.

    C'est ce qui répond, sans rien inventer, à la question *« quel mot est-ce qu'il
    remplace ? »* : le mot français qui revient partout où le mot grec paraît est presque
    toujours sa traduction — et quand il ne l'est pas, le pasteur le voit, parce que les
    versets sont là.

    Les mots-outils sont retirés : *le*, *de*, *et* reviennent dans n'importe quel verset et
    ne désigneraient rien.

    ⚠️ **La majorité, pas l'unanimité** — et c'est le premier essai réel qui l'a montré. Sur
    `πρῶτος` : *« va d'**abord** te réconcilier »*, *« cherchez **premièrement** le royaume »*,
    *« ôte **premièrement** la poutre »*. Une traduction rend un même mot grec par plusieurs
    mots français ; exiger qu'ils soient tous identiques ne rendrait presque jamais rien."""
    if len(versets) < 2:
        return ()
    compte: dict[str, int] = {}
    for verset in versets:
        for mot in {
            mot for mot in _decouper(verset) if len(mot) > 2 and mot not in _OUTILS
        }:
            compte[mot] = compte.get(mot, 0) + 1
    seuil = max(2, (len(versets) + 1) // 2)
    retenus = sorted(
        (mot for mot, n in compte.items() if n >= seuil),
        key=lambda mot: (-compte[mot], mot),
    )
    return tuple(retenus[:combien])


def _decouper(texte: str) -> list[str]:
    plie = unicodedata.normalize("NFD", texte.casefold())
    sans_accent = "".join(c for c in plie if unicodedata.category(c) != "Mn")
    return [mot for mot in re.split(r"[^0-9a-z]+", sans_accent) if mot]


@dataclass(frozen=True, slots=True)
class MotOriginal:
    """Un mot du texte d'origine, tel que la note le montre.

    **Quatre choses, et aucune n'est une traduction** : où il est employé, comment il se dit,
    ce que sa forme fait, et où il revient. C'est le maximum qu'on puisse offrir tant que
    `urim_corpus_lemma.gloss` est vide — et c'est déjà ce qui manquait le plus."""

    reference: str
    forme: str
    #: `prôtos` — **mécanique, donc permis** : translittérer n'est pas traduire.
    phonetique: str
    lemme: str
    nature: str
    morphologie: str
    #: `(référence, verset français)` — la concordance, avec le texte et non la seule adresse.
    ailleurs: tuple[tuple[str, str], ...] = ()
    #: Ce que ces versets ont en commun — l'indice de ce que le mot rend, **jamais présenté
    #: comme sa définition**.
    communs: tuple[str, ...] = ()


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
    #: Le plan du pasteur : `(code, texte, appuis)`, dans son ordre.
    #:
    #: **`appuis` est ce qui développe le point sans l'écrire.** Un titre seul ne sert à rien —
    #: c'est sous lui que le travail se fait. Mais développer *à sa place* serait la machine à
    #: sermons. La seule matière qu'on puisse y mettre sans rien inventer est **le texte qu'il
    #: a lui-même convoqué dans ce point** : les références écrites dans sa ligne sont
    #: résolues, et le verset s'imprime dessous.
    #:
    #: ⚠️ **Une référence qui n'existe pas s'imprime avec le motif du corpus**, jamais en
    #: silence : les notes du Pasteur X portaient `Hb 2v29` et `Ph 28v9`, et c'est exactement
    #: là qu'Urim doit parler.
    plan: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...]
    #: Le texte servi par le corpus — jamais saisi, donc rien à falsifier.
    versets: tuple[tuple[str, str], ...]
    #: **Dans quelle version il a préparé.** Sur Romains 8:1, l'Ostervald porte une clause
    #: que la LSG omet : sans la clause « aucune condamnation » est inconditionnel, avec
    #: elle c'est une condition morale. Une note qui ne dit pas d'où vient son texte laisse
    #: son lecteur croire qu'il n'y en avait qu'un.
    version: str
    #: `(axe, force, motif)` — les dix, `absent` compris.
    pesees: tuple[tuple[str, str, str], ...]
    #: **L'axe que le pasteur a retenu** — sa décision, pas le calcul du corpus.
    #:
    #: Les deux ne coïncident pas toujours, et c'est l'information la plus utile de la
    #: section : *« Christologie — votre choix »* à côté de *« Pneumatologie — ce que le corpus
    #: trouve dominant »*. Les fondre en une seule liste ferait disparaître le désaccord, or
    #: c'est précisément là que le pasteur a quelque chose à décider. Le reste du dépôt tient
    #: déjà la distinction — l'archive range sous **l'axe retenu**, jamais sous le dominant
    #: calculé, et l'étage du thème dérive du retenu.
    axe_retenu: str | None
    #: Ce que le texte **ne dit pas**.
    mises_en_garde: tuple[str, ...]
    #: `(plan x matiere, faisable, motif de refus, risque de proof-texting)`.
    faisabilites: tuple[tuple[str, bool, str, str], ...]
    #: Les textes qui **résistent**, venus d'ailleurs — au même rang que ceux qui portent.
    resistances: tuple[tuple[str, str], ...]
    #: `(référence, texte, verdict)` — la chaîne d'appuis, **saisies illisibles comprises**.
    appuis: tuple[tuple[str, str, str], ...]
    #: Les mots de l'original — voir `MotOriginal`.
    original: tuple[MotOriginal, ...]
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
