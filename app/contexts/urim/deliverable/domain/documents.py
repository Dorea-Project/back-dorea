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

## Le squelette Braga, et le seul élément qui ouvre le livrable

Les dix éléments sont **tous facultatifs** : le moteur n'en remplit aucun, parce qu'*un plan qui
arrive complet n'est pas un plan que quelqu'un a préparé*. Un seul est exigé pour produire un
document, et c'est **la proposition** — le sermon en une phrase.

Ce n'est pas un seuil d'avancement, c'est une question binaire : *y a-t-il un homme derrière ce
document ?* Le titre est une étiquette, les divisions se déduisent d'un plan, les illustrations
viennent d'ailleurs ; la proposition est l'endroit où le pasteur dit ce qu'il va dire — et chez
Braga, c'est elle qui gouverne les divisions.

⚠️ **On ne juge jamais son contenu.** Non vide après normalisation, un point. Aucune longueur
minimale, aucun modèle consulté : une machine qui apprécierait la valeur du point central d'un
prédicateur serait la machine à sermons sous un autre nom, et cette fois avec une note.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Les dix éléments du squelette (Braga), dans leur ordre canonique. La liste est **fermée**
#: ici alors que `preparation_element.element_code` est encore un texte libre en base : le
#: livrable s'adosse à `proposition`, et une liste ouverte rendrait le verrou contournable par
#: une majuscule — pire, refuserait son document à un pasteur qui avait bien écrit son point
#: central. Fermer la colonne elle-même touche `PUT /elements`, déjà en service : à faire après
#: vérification du client, pas au détour de ce module.
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

#: Celui sans lequel il n'y a pas de document. Voir l'en-tête.
POINT_CENTRAL = "proposition"


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
    #: Les mots de l'original avec leur morphologie décodée.
    original: tuple[tuple[str, str, str], ...]
    #: Ce qui a été **écarté**, avec son motif : la moitié du dialogue qu'on oublie d'imprimer.
    ecartees: tuple[tuple[str, str], ...]
    signature: str | None
    corpus_snapshot: str | None


def point_central_renseigne(plan: dict[str, str | None]) -> bool:
    """Y a-t-il quelque chose de lui ? — **la question, et toute la question**.

    Ce n'est pas « a-t-il modifié ? ». Pour le vérifier il faudrait d'abord lui avoir donné un
    brouillon à modifier — donc **écrire le sermon à sa place pour constater qu'il l'a
    corrigé**, ce que ce produit refuse de faire. Et une espace en fin de ligne suffirait à
    passer n'importe quelle comparaison."""
    return bool((plan.get(POINT_CENTRAL) or "").strip())
