"""Le tour — **le serveur rend le tour, le client rend des blocs**.

`docs/Urim_Conversation.md` pose le contrat ; ce module l'implémente, sans rien y ajouter.

    Le client n'écrit jamais une phrase de sa propre autorité.

C'est la décision fondatrice, et elle a une conséquence directe : tout ce que le pasteur lit
vient d'ici, donc tout se relit en un seul endroit. Une phrase fabriquée côté Flutter
échapperait à la relecture, aux tests, et à la règle du filet doré.

## Ce que ce module n'est pas

**Il ne calcule rien.** Le tour est une *présentation* de ce que `StudyView` porte déjà — pas
un nouvel étage, pas une nouvelle donnée, pas un appel de modèle. Si une information n'est pas
dans la vue, elle n'est pas dans le tour ; c'est ce qui garantit que les deux ne peuvent pas se
contredire.

## Les trois phrases, et pourquoi elles ne viennent pas du même endroit

Le contrat veut `say`, `why` et `ask` là où le moteur ne produit qu'un `rationale`. On ne
découpe pas cette phrase — un découpage se casserait au premier motif reformulé.

    say    déterministe, choisi sur L'ÉCRAN — ce qu'Urim vient de faire
    why    LE MOTIF DU MOTEUR, tel quel — jamais réécrit
    ask    déterministe, et seulement quand le pasteur a quelque chose à faire

C'est le même partage que les deux répondeurs `hors_champ` et `indechiffrable` : la voix du
produit est écrite en français, une fois, et relue ; ce qui vient du raisonnement traverse
intact.

⚠️ **`why` n'est jamais nul, et c'est une règle du produit.** *« Chaque réponse porte son filet
doré. C'est ce qui sépare un atelier d'un oracle. »* Un tour sans motif serait une conclusion
sans provenance — la seule chose qu'Urim s'interdit.

## La règle que ce module tient, et qui n'était écrite nulle part

> **Aucun tour ne se termine par un mur.** Après chaque tour, le pasteur a quelque chose à
> faire : des options à toucher, une barre de saisie ouverte, ou une passerelle nommée.

C'est la même règle que `Outcome.DEGRADE` côté moteur — *aucun mur un vendredi soir* — et elle
se perdait ici, à la présentation, là où personne ne la cherchait. Deux murs se fabriquaient
dans ce fichier : un choix demandé sur une liste entièrement écartée, et un « voici » posé
au-dessus de zéro bloc. `scripts/urim_banc_arbre.py` marche l'arbre et les nomme.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.contexts.urim.domain.squelette import POINT_CENTRAL
from app.contexts.urim.engine.liaison import ORDRE_DES_FORCES
from app.contexts.urim.engine.repondeurs import situer

#: **L'écran où rien n'est à regarder**, et celui où tout ce qui était offert a été écarté.
#: Deux formes qui ne sont pas des types de bloc — ce sont les deux façons qu'a un tour de
#: n'avoir rien à montrer, et ce sont les deux endroits où l'on fabriquait un mur.
FORME_RIEN = "rien"
FORME_EPUISE = "epuise"

#: L'écran d'une **correction** — « vouliez-vous dire Hébreux 2:9 ? ». Ce sont des pastilles
#: comme les autres, et pourtant ce n'est pas le même écran : les phrases de l'étage parlent de
#: textes qui traitent un sujet, celle-ci parle de ce que le pasteur a **tapé**.
FORME_CORRECTION = "correction"

#: ⚠️ **La phrase suit l'écran, pas le nom de l'étage.**
#:
#: 🔴 Une table indexée sur le seul nom de l'étage disait faux dès qu'un étage servait plus
#: d'un écran — et ils le font tous. Trois prises, marchées contre le corpus réel :
#:
#:     weigh_conviction   « Sur lequel prêchez-vous ? » posé devant quatre péricopes
#:     bear_axes          « Voici ce que ce texte porte » posé devant un écran VIDE
#:     bear_axes          deux axes à choisir, et aucune question posée
#:
#: Le deuxième est le tour **ordinaire**, pas un cas limite : sur 99,77 % de l'Écriture rien
#: n'est encore curé, la pesée dégrade, et le pipeline s'arrête là. Le `say` promettait alors
#: un contenu que les blocs n'avaient pas — la forme exacte d'un mur.
#:
#: L'écran, lui, ne peut pas mentir : c'est ce que le pasteur a réellement sous les yeux.
#: Les phrases restent déterministes pour la raison des répondeurs — le modèle n'a aucun canal
#: de sortie en prose, et lui en ouvrir un pour annoncer ce que le moteur vient de faire serait
#: payer un appel pour une phrase qu'on écrit une fois.
_PAR_ECRAN: dict[str, tuple[str, str]] = {
    "units": (
        "Voici les textes relus qui disent quelque chose de cet axe.",
        "Lequel ouvrons-nous ?",
    ),
    "bounds": (
        "Vos bornes ne coïncident pas avec l'unité relue.",
        "Lesquelles gardons-nous ?",
    ),
    # ⚠️ Ces trois écrans-là n'arrivent **qu'avec les mains vides** : dès que l'étage offre un
    # choix, c'est lui qui parle. Leur question n'est donc pas décorative — c'est la seule
    # chose qui reste à faire au pasteur, et sans elle le tour est un cul-de-sac poli.
    # ⚠️ La question nomme le geste que le bloc rend possible depuis §7 : l'axe retenu n'est pas
    # une fatalité du texte, c'est un angle, et le pasteur peut en prendre un autre parmi ceux
    # que le texte porte. Le dire ici est tout ce qui manquait — le geste, lui, existait.
    "bearings": (
        "Voici ce que ce texte porte — et ce à quoi il résiste.",
        "Prêchez-le sur un autre de ses axes si le vôtre est ailleurs, ou ouvrez un autre "
        "passage.",
    ),
    "feasibility": (
        "Voici les plans que ce texte peut tenir, et ceux qu'il refuse.",
        "Travaillez le texte tel quel — le plan reste le vôtre.",
    ),
    "theme": (
        "Un thème, jamais un titre — le titre, c'est votre voix.",
        "Réécrivez-le, c'est votre sermon — ou écrivez vos points.",
    ),
    "chips": ("Voici ce que je peux vous proposer ici.", "Lequel retenez-vous ?"),
    # Le motif porte déjà le fait — *« Hébreux 2 compte 18 versets »* — et la question du
    # moteur. La phrase dit ce qu'Urim a fait, sans la répéter.
    FORME_CORRECTION: (
        "J'ai cherché la référence la plus proche de ce que vous avez écrit.",
        "Est-ce celle-là ?",
    ),
    FORME_RIEN: (
        "Je n'ai rien de plus à vous montrer sur ce point.",
        "Donnez-moi un passage, ou reprenez votre sujet en clair — les deux entrent par le "
        "même champ.",
    ),
    FORME_EPUISE: (
        "Je n'ai plus de proposition neuve ici — celles que je savais offrir sont reléguées "
        "plus bas.",
        "Reprenez l'une d'elles, ou donnez-moi une référence : j'ouvre le passage et je "
        "repars de là.",
    ),
}

#: Ce que l'étage sait dire de mieux que l'écran seul — **et rien d'autre**.
#:
#: Des pastilles ne disent pas d'elles-mêmes de quoi elles sont faites : dix loci, deux
#: lectures d'entrée, six passages à égalité et deux axes dominants ont la même forme. Là
#: seulement, l'étage tranche. Partout ailleurs l'écran suffit, et une entrée de plus serait
#: une phrase de plus à relire pour rien.
#: La passerelle du vestibule quand le modèle n'a pas posé de question lui-même.
#:
#: ⚠️ **Elle n'est pas décorative.** Le banc de l'arbre appelle un `expects: text` sans `ask`
#: *« barre ouverte, mais aucune passerelle nommée »* — un mur, et le seul qui survive à une
#: relecture de code parce que la structure a l'air correcte.
_RELANCE_DU_VESTIBULE = (
    "Écrivez-le comme il vous vient : un sujet, un passage, ou ce qui vous occupe."
)

_PAR_ETAGE: dict[tuple[str, str], tuple[str, str]] = {
    ("route_entry", "chips"): (
        "Je lis votre saisie avant tout le reste.",
        "Est-ce bien de cela que vous voulez parler ?",
    ),
    ("route_entry", FORME_RIEN): (
        "Je ne sais pas quoi ouvrir avec cette saisie.",
        "Réécrivez-la comme elle vous vient : un sujet, une référence ou une phrase du "
        "texte — les trois entrent par le même champ.",
    ),
    ("weigh_conviction", "chips"): (
        "Votre phrase touche plusieurs endroits de la doctrine.",
        "Sur lequel prêchez-vous ?",
    ),
    # ⚠️ **Le tour du pasteur dont le sujet n'a pas de locus.** Les dix loci sont la
    # dogmatique de CE corpus, pas la mesure de ce qui se prêche : une intention mariale,
    # une fête liturgique, une question de discipline n'y tiennent dans aucun. Quand ils
    # sont tous écartés, le produit doit nommer **sa** limite — jamais reprocher au pasteur
    # d'avoir tout repoussé, et surtout jamais arbitrer sa tradition.
    #
    # La passerelle est vérifiée avant d'être promise : « Luc 1:28 » donné à la main ouvre
    # l'unité entière de l'Annonciation, ses dix pesées et ses deux mises en garde.
    ("weigh_conviction", FORME_EPUISE): (
        "Ces dix axes sont ce que la dogmatique de ce corpus sait nommer — un sujet peut "
        "n'entrer dans aucun.",
        "Donnez-moi un texte, même un seul verset : je l'ouvre entier, avec ce qui en a "
        "été relu.",
    ),
    ("weigh_conviction", FORME_RIEN): (
        "Sur cet angle, la curation n'a encore relu aucun texte.",
        "Donnez-moi une référence si vous savez déjà où aller, ou reprenez un autre angle.",
    ),
    ("resolve_passage", "chips"): (
        "Plusieurs textes portent cette formulation — aucun ne s'impose seul.",
        "Lequel visiez-vous ?",
    ),
    ("resolve_passage", FORME_RIEN): (
        "Je n'ai pas su ouvrir le passage que vous nommez.",
        "Vérifiez le nom du livre, ou dites-moi votre sujet en clair.",
    ),
    ("bear_axes", "chips"): (
        "Plusieurs axes disent quelque chose de ce texte, au même rang.",
        "Lequel prêchez-vous ?",
    ),
    # 🔴 **Le mur le plus fréquent du produit**, et il ne se voyait qu'en marchant : le
    # `say` annonçait « voici ce que ce texte porte » au-dessus de zéro bloc.
    ("bear_axes", FORME_RIEN): (
        "Le texte est là, entier — ce qui manque ici, c'est la relecture, pas l'Écriture.",
        "Travaillez-le tel quel, ou donnez-moi un autre passage : je dirai ce qui en a "
        "été relu.",
    ),
    ("shape_homiletic", "chips"): (
        "Voici les plans que ce texte peut tenir, et ceux qu'il refuse.",
        "Lequel voulez-vous suivre ?",
    ),
    # Le refus de l'étage 6 : tous les couples relus sont écartés. Ils restent affichés avec
    # leur motif — *les cacher laisserait croire qu'on n'y a pas pensé* —, et le tour dit ce
    # qui reste possible plutôt que de s'arrêter sur le refus.
    ("shape_homiletic", "feasibility"): (
        "Aucun de ces plans ne tient sur cette unité — ils restent affichés avec leur motif.",
        "Travaillez le texte tel quel : le plan reste le vôtre.",
    ),
    ("shape_homiletic", FORME_RIEN): (
        "Aucune mise en forme n'a encore été relue sur cette unité.",
        "Travaillez le texte tel quel — le plan reste le vôtre.",
    ),
}

#: Le dernier recours : un `kind` de bloc ajouté demain, qu'aucune table ne connaît encore.
#: Il dégrade en une phrase vraie plutôt qu'en une phrase vide (§5.5).
_FAUTE_DE_MIEUX = ("Voici où nous en sommes.", "")


class ChipItem(BaseModel):
    code: str
    label: str
    #: La référence du passage, quand la pastille en désigne un — « Colossiens 3:18-25 ».
    #: Vide pour un locus ou un couple plan x matière, qui n'en désignent aucun.
    reference: str = ""
    hint: str = ""
    origin: str = "moteur"
    selected: bool = False

    #: ⚠️ **Qui a écrit ce libellé**, quand ce n'est pas le corpus — `ia-mistral`, le mot du
    #: bandeau. `origin` dit d'où vient la **proposition**, celle-ci dit qui l'a **habillée** :
    #: les dix loci viennent tous de la dogmatique, et trois d'entre eux portent la phrase du
    #: pasteur écrite par un modèle. Les confondre reviendrait à dire que l'axe est généré.
    signature: str | None = None


class ChipsBlock(BaseModel):
    """Un choix qui se touche.

    *Les pastilles sont des raccourcis, jamais des barreaux.* Le pasteur peut taper le libellé
    à la main : `expects` vaut `choice`, ce qui **autorise** le texte libre sans l'exclure."""

    kind: Literal["chips"] = "chips"
    items: list[ChipItem]


class UnitItem(BaseModel):
    code: str
    label: str
    reference: str = ""
    rationale: str = ""


class UnitGroup(BaseModel):
    role: str
    heading: str
    items: list[UnitItem]


class UnitsBlock(BaseModel):
    """Les unités, groupées par ce qu'elles font du sujet.

    ⚠️ **Un seul groupe tant que le trou 1 n'est pas bouché.** La maquette sépare *« en fait
    son sujet »* de *« le soutient » ; `OptionView` ne porte rien qui distingue les deux, et le
    client le devinerait en lisant le motif — ce qui marche jusqu'au jour où non. Émettre un
    groupe unique et honnête vaut mieux qu'un groupement inventé."""

    kind: Literal["units"] = "units"
    groups: list[UnitGroup]


class BoundsBlock(BaseModel):
    """L'unité contre les bornes du pasteur.

    Un `kind` distinct de `chips` parce que la **conséquence** n'est pas optionnelle à
    l'affichage : *si vous gardez vos bornes, je ne pourrai plus vous alerter sur un risque de
    proof-texting.*"""

    kind: Literal["bounds"] = "bounds"
    items: list[ChipItem]
    consequence: str = ""


class BearingItem(BaseModel):
    axis_code: str
    label: str
    strength: str
    rationale: str

    #: L'axe sur lequel la préparation travaille — **celui dont tout l'aval dépend** : le thème
    #: s'en dérive, et les textes qui résistent sont cherchés pour lui.
    selected: bool = False

    #: ⚠️ **Cet axe peut être pris à la place de celui-là**, et c'est le trou que §7 a nommé.
    #:
    #: 🔴 Un texte à **un seul** axe dominant voyait son axe posé d'office : `bear_axes`
    #: continue sans rendre la main, et aucun écran ne disait que le choix existait. Le pasteur
    #: orthodoxe qui ouvre 2 Pierre 1:4 *pour* la déification repartait avec une préparation
    #: christologique — l'unité porte pourtant l'anthropologie. 42,2 % des unités curées sont
    #: dans ce cas, et 98,9 % d'entre elles portent au moins un autre axe.
    #:
    #: Le geste existait déjà de bout en bout : `POST /decisions` sur `bear_axes` repose l'axe
    #: et le pipeline repart derrière. **Rien ne le disait.** Une porte ouverte que personne ne
    #: voit est pire qu'une porte fermée : elle a l'air d'une fonctionnalité manquante.
    #:
    #: `absent` n'est jamais sélectionnable — *un axe absent n'affiche rien, et aucun plan ne se
    #: construit dessus* —, et `resiste` non plus : on ne prêche pas un texte sur ce qu'il
    #: contredit.
    selectable: bool = False


class BearingsBlock(BaseModel):
    """Ce que le texte porte — **et, depuis §7, ce qu'on peut prendre à la place**.

    ⚠️ `decide_stage` dit **où** poster : le tour porte le code de l'étage courant, qui n'est
    pas celui-ci. Sans lui, un client qui rendrait ces pesées cliquables les enverrait à
    l'étage qui vient de parler, et le service refuserait — la moitié du 422 au clic, dans
    l'autre sens."""

    kind: Literal["bearings"] = "bearings"
    items: list[BearingItem]
    caveats: list[str] = []
    decide_stage: str = "bear_axes"


class FeasibilityItem(BaseModel):
    plan_source: str
    subject_matter: str
    feasible: bool
    risk: str = ""
    rationale: str = ""


class FeasibilityBlock(BaseModel):
    """Les couples plan x matière.

    **Les refusés voyagent avec les faisables** — les cacher laisserait croire qu'on n'y a
    pas pensé, et c'est la même règle que les options écartées."""

    kind: Literal["feasibility"] = "feasibility"
    items: list[FeasibilityItem]


class ThemeBlock(BaseModel):
    kind: Literal["theme"] = "theme"
    body: str


class ActionItem(BaseModel):
    code: str
    label: str
    enabled: bool
    unavailable_reason: str = ""


class ActionsBlock(BaseModel):
    """Les sorties.

    ⚠️ `enabled: false` **porte toujours son motif**. Un bouton grisé muet est un mensonge
    poli — même règle que les versions indisponibles : *elle informe, elle ne rançonne pas.*"""

    kind: Literal["actions"] = "actions"
    items: list[ActionItem]


Block = (
    ChipsBlock | UnitsBlock | BoundsBlock | BearingsBlock
    | FeasibilityBlock | ThemeBlock | ActionsBlock
)


class TurnView(BaseModel):
    say: str
    why: str
    ask: str = ""
    expects: Literal["choice", "text", "nothing"]
    stage_code: str
    signature: str | None = None
    blocks: list[Block] = []

    #: ⚠️ **Le bloc dont ce tour parle** — et la seule chose qui permette au client
    #: de ne pas tout redéplier.
    #:
    #: Cette valeur était déjà calculée : `_forme` la produit pour choisir la
    #: phrase, puis la jetait. Le client recevait donc des blocs sans savoir
    #: lequel est le sujet et lesquels sont du **décor ambiant** — les pesées et
    #: les couples accompagnent tous les tours qui suivent l'étage qui les a
    #: produits, et se réaffichaient à l'identique à chaque fois.
    #:
    #: 🔴 Mesuré sur un téléphone : un tour de `shape_homiletic` fait **onze
    #: écrans**, dont neuf de matière déjà lue. Le pasteur traverse son propre
    #: passé pour atteindre son geste. Il n'a pas le temps — c'est la raison
    #: d'être du compagnon.
    #:
    #: Porte un `kind` de bloc, ou `rien` / `epuise` / `correction` quand ce qui
    #: parle n'est pas un bloc. Le client déplie celui-là et replie le reste,
    #: **sans rien cacher** : les refusés voyagent toujours avec les faisables,
    #: repliés sous leur nombre.
    speaks: str = ""


#: 🔴 **Les deux livrables étaient annoncés fermés alors qu'ils fonctionnent.** Ce motif
#: datait du trou 3 — avant que le module du livrable existe. Depuis, `POST
#: /studies/{id}/deliverable` soumet, contrôle et rend un fichier ; l'écran, lui, continuait
#: d'annoncer une porte close. Un bouton fermé doit porter son motif, mais un motif périmé
#: est pire qu'un bouton muet : il décrit un produit qui n'existe plus.
#:
#: Ce qui reste vrai, et le seul refus légitime : **le deck sans plan**. Le service le dit
#: lui-même, dans ces termes.
_DECK_SANS_PLAN = (
    "Il n'y a pas encore de plan à projeter. Les diapositives mettent en page ce que vous "
    "avez écrit ; le moteur ne l'écrit pas à votre place."
)

#: ⚠️ **Les groupes suivent la donnée, pas le nom de l'étage.**
#:
#: Une option qui porte une force est une unité pesée, d'où qu'elle vienne ; une option sans
#: force est une pastille. Lier le type de bloc à un nom d'étage aurait fallu le corriger à
#: chaque étage nouveau, et se serait trompé le jour où deux étages proposent des unités.
#:
#: `resiste` a son groupe, et ce n'est pas un détail : c'est la seule mécanique
#: anti-proof-texting du produit, et elle s'affiche **au même rang** que ce qui porte.
#: ⚠️ **L'ordre vient de `liaison`, il ne se redéclare pas ici.**
#:
#: 🔴 Cette table le portait en dur, et `liaison.ORDRE_DES_FORCES` le portait aussi — deux
#: définitions de la même chose. Or le **compteur de rangs** en dépend : « le deuxième » se
#: compte sur ce que le pasteur VOIT, c'est-à-dire sur ces groupes. Les deux listes divergeant
#: d'un cran, « le deuxième » aurait désigné la troisième option — agir sur le mauvais objet,
#: exactement ce que la liaison existe pour empêcher.
_GROUPES = tuple(
    zip(ORDRE_DES_FORCES, ("En fait son sujet", "Le soutient", "Lui résiste"), strict=True)
)


#: Le budget d'une aide de pastille. Au-delà, le motif complet se lit dans le bloc des
#: pesées, où il n'est pas coupé.
_AIDE_MAX = 80


def _ecourter(texte: str, budget: int = _AIDE_MAX) -> str:
    """Le motif ramené à son budget, **sur un mot entier**.

    🔴 C'était `texte[:80]`, et la coupe tombait où elle tombait : le pasteur lisait
    « plus d'alerte de risque de proof-te » — un mot tranché au milieu, à l'endroit précis
    où on l'avertit d'un risque. Une aide qui s'interrompt ainsi n'aide pas, elle inquiète.

    Le point de suspension dit que la suite existe ; elle se lit entière dans les pesées.
    """
    if len(texte) <= budget:
        return texte

    coupe = texte[:budget].rstrip()
    espace = coupe.rfind(" ")
    # Un mot plus long que le budget entier : rien à sauver, on coupe net.
    return f"{coupe[:espace].rstrip() if espace > 0 else coupe}…"


def _a_un_point(vue) -> bool:
    """Le plan porte-t-il un point écrit par lui ? — le seuil du deck.

    Même question que `point_central_renseigne`, posée sur la vue plutôt que sur le plan
    replié : l'écran doit pouvoir fermer le bouton **avant** que le service refuse, sans quoi
    le pasteur touche une sortie pour apprendre qu'elle n'existe pas."""
    return any(
        e.element_code == POINT_CENTRAL and (e.body or "").strip()
        for e in vue.elements
    )


def _pastilles(options: list) -> list[ChipItem]:
    return [
        ChipItem(
            code=o.code, label=o.label, reference=o.reference,
            hint=_ecourter(o.rationale),
            origin=o.origin, selected=False, signature=o.signature,
        )
        for o in options
        if not o.dismissed
    ]


def _blocs(vue, etage: str, vivantes: list) -> list[Block]:
    """Les blocs que cet étage a de quoi remplir — jamais un bloc vide.

    L'ordre est celui de l'écran, de haut en bas, et il est fixé ici : le client rend ce qu'on
    lui donne dans l'ordre où on le lui donne.

    ⚠️ **Les trois branches d'options testent les vivantes, jamais `vue.options`.** 🔴 Elles
    testaient la liste entière : le pasteur qui avait écarté les dix loci recevait donc un
    bloc `chips` **vide**, sous une question qui restait posée — un choix demandé sur zéro
    proposition. C'était le mur, et il tenait à un mot."""
    blocs: list[Block] = []

    pesees = [o for o in vivantes if o.strength]

    if pesees:
        groupes = [
            UnitGroup(
                role=role,
                heading=titre,
                items=[
                    UnitItem(
                        code=o.code, label=o.label,
                        # 🔴 Ce champ portait `o.code` — « texte:9269b12d-… ». Le client ne
                        # l'affichait pas, et il avait raison : ce n'est pas une référence.
                        reference=o.reference, rationale=o.rationale,
                    )
                    for o in pesees if o.strength == role
                ],
            )
            for role, titre in _GROUPES
        ]
        blocs.append(UnitsBlock(groups=[g for g in groupes if g.items]))
        # Les options non pesées de la même liste — « allez droit à un texte » — restent des
        # pastilles : elles n'ont rien de relu, et les mêler aux unités le laisserait croire.
        if autres := [o for o in vivantes if not o.strength]:
            blocs.append(ChipsBlock(items=_pastilles(autres)))
    elif etage == "bound_pericope" and vivantes:
        blocs.append(BoundsBlock(
            items=_pastilles(vivantes),
            consequence=(
                "Si vous gardez vos bornes, je ne pourrai plus vous alerter sur un risque "
                "de proof-texting."
            ),
        ))
    elif vivantes:
        blocs.append(ChipsBlock(items=_pastilles(vivantes)))

    if vue.bearings:
        # ⚠️ **La glosse ne se répète pas de tour en tour.**
        #
        # 🔴 Vu sur téléphone le 22/08 : dix pesées, chacune portant trois lignes de motif,
        # recollées à **chaque** tour suivant le choix. Le pasteur retrouvait le même paragraphe
        # sur la mise en forme, sur le thème, sur ses points — un texte qu'il avait déjà lu et
        # déjà tranché, réaffiché comme s'il était neuf.
        #
        # Au tour du choix, la glosse est la question : c'est elle qui permet de décider, et
        # elle reste entière. Après, la décision est prise — le décor ambiant garde les
        # libellés, qui suffisent à retrouver et à reprendre un autre axe, et lâche les
        # paragraphes.
        pese = etage == "bear_axes"
        blocs.append(BearingsBlock(
            items=[
                BearingItem(
                    axis_code=b.axis_code, label=b.label,
                    strength=b.strength, rationale=b.rationale if pese else "",
                    selected=b.axis_code == vue.axis_code,
                    # On ne propose pas de reprendre l'axe déjà retenu : ce serait offrir un
                    # geste qui ne fait rien.
                    selectable=(
                        b.strength in _AXES_PRECHABLES and b.axis_code != vue.axis_code
                    ),
                )
                for b in vue.bearings
            ],
            caveats=list(vue.caveats),
        ))

    if vue.couples:
        blocs.append(FeasibilityBlock(items=[
            FeasibilityItem(
                plan_source=c.plan_source, subject_matter=c.subject_matter,
                feasible=c.feasible, risk=c.proof_text_risk,
                rationale=c.refusal_reason,
            )
            for c in vue.couples
        ]))

    if vue.theme:
        blocs.append(ThemeBlock(body=vue.theme))
        blocs.append(ActionsBlock(items=[
            ActionItem(code="elements", label="Écrire mes points", enabled=True),
            ActionItem(
                code="deck", label="PowerPoint", enabled=_a_un_point(vue),
                unavailable_reason="" if _a_un_point(vue) else _DECK_SANS_PLAN,
            ),
            # La note n'exige aucun plan, et c'est délibéré : sans plan elle
            # devient un document de travail — le pasteur l'emporte à son
            # bureau et écrit dessus. La section de son plan y dit « à écrire »
            # au lieu de proposer.
            ActionItem(code="sheet", label="Fiche de chaire", enabled=True),
        ]))

    return blocs


#: Une sortie, pas un écran : `actions` accompagne le thème, il ne le remplace pas.
_DECOR = frozenset({"actions"})

#: Les forces sur lesquelles un sermon se construit. `absent` en est exclu — *un axe absent
#: n'affiche rien, et aucun plan ne se construit dessus* — et `resiste` aussi : c'est un
#: garde-fou, pas un angle. C'est le même partage que `bear_axes`, qui offre les dominants,
#: sinon les portants, et jamais les résistants.
_AXES_PRECHABLES = frozenset({"dominant", "porte"})


def _forme(vue, blocs: list[Block], vivantes: list) -> str:
    """**Ce que le pasteur a sous les yeux**, dit en un mot.

    L'ordre des questions est la règle. *Ai-je proposé quelque chose qui a tout été écarté ?*
    d'abord — sinon la question « lequel ? » resterait posée sur une liste vidée. *Y a-t-il
    quoi que ce soit à regarder ?* ensuite.

    ⚠️ **Le bloc qui parle n'est pas toujours le premier.** Quand l'étage offre un choix, c'est
    lui : `_blocs` place toujours les options en tête. Quand il n'offre rien, la tête est du
    **décor ambiant** — les pesées de l'unité accompagnent tous les tours qui suivent —, et
    c'est le bloc le plus avancé qui dit ce qui vient d'arriver. 🔴 Sans cette distinction, le
    dernier tour de la maquette annonçait « voici ce que ce texte porte » au-dessus du thème
    qu'il venait de proposer."""
    if vue.options and not vivantes:
        return FORME_EPUISE
    # ⚠️ Une correction ne se distingue pas par son **bloc** — c'est une pastille — mais par ce
    # dont elle parle. Sans cette branche, l'écran de la faute de frappe héritait de la phrase
    # des textes à égalité : « plusieurs textes portent cette formulation » au-dessus d'une
    # seule proposition, qui ne porte aucune formulation. Le mur n°2, en plus petit.
    if vivantes and all(o.origin == FORME_CORRECTION for o in vivantes):
        return FORME_CORRECTION
    parlants = [b for b in blocs if b.kind not in _DECOR]
    if not parlants:
        return FORME_RIEN
    return parlants[0].kind if vivantes else parlants[-1].kind


def construire_tour(
    vue, say: str | None = None, relance: str | None = None
) -> TurnView:
    """La présentation conversationnelle de ce que la vue porte déjà.

    ⚠️ **`expects` vient de l'issue ET de ce qui reste à choisir.** Un même étage attend une
    décision ou n'attend rien selon ce que le corpus lui a donné — et il n'attend plus rien
    quand tout ce qu'il proposait a été écarté. 🔴 `expects: choice` sur zéro pastille disait
    au client d'ouvrir un sélecteur vide : le moteur attendait encore, l'écran n'offrait plus
    rien, et le pasteur n'avait aucun geste possible.

    ⚠️ **`ask` accompagne ce qu'on peut faire, pas l'issue.** Une question posée au-dessus d'une
    liste de pastilles alors que le moteur a déjà continué ferait répondre le pasteur à un tour
    passé — d'où la garde d'origine. Mais un tour qui n'offre **rien à toucher** doit poser la
    sienne : la saisie est alors le seul geste possible, et un tour qui ne la nomme pas est un
    cul-de-sac poli.
    """
    etage = vue.trace[-1].stage_code if vue.trace else "route_entry"
    vivantes = [o for o in vue.options if not o.dismissed]
    blocs = _blocs(vue, etage, vivantes)
    forme = _forme(vue, blocs, vivantes)

    dit, ask = _PAR_ETAGE.get(
        (etage, forme), _PAR_ECRAN.get(forme, _FAUTE_DE_MIEUX)
    )
    # ⚠️ **La seule chose qu'on souffle au tour : la phrase d'un répondeur.**
    #
    # Quand le tour a été *aiguillé* plutôt que décidé, c'est le répondeur qui a la réponse —
    # « je ne sais pas conseiller sur les personnes », « aucun texte n'est encore ouvert ». Elle
    # prend la place de `say`, et **rien d'autre** : `why` reste le motif du moteur, les blocs
    # restent ce que la vue porte. Les deux ne peuvent donc pas se contredire.
    #
    # Le répondeur situe déjà la préparation lui-même — il ne faut pas la situer deux fois.
    #
    # 🔴 **La garde était écrite, et la ligne suivante l'écrasait.** `sans_rien` était remis à
    # sa valeur de forme juste après avoir été mis à faux, si bien que la phrase du répondeur
    # — qui situe déjà — se voyait ajouter une seconde fois « Nous en sommes à Romains 8:32 ».
    # Vu sur un téléphone le 22/08, dans la même phrase, deux fois de suite. Le commentaire
    # disait la règle ; le code disait l'inverse, deux lignes plus bas.
    if say:
        dit, sans_rien = say, False
    else:
        sans_rien = forme in (FORME_RIEN, FORME_EPUISE)
    attend = vue.outcome == "await_decision" and bool(vivantes)

    # ⚠️ **Le vestibule parle d'une seule voix, et c'est la sienne.**
    #
    # 🔴 Vu sur un téléphone le 22/08 : chaque tour empilait trois énoncés qui disaient la même
    # chose — la phrase générique du tour vide (« je n'ai rien de plus à vous montrer »), sa
    # passerelle (« donnez-moi un passage… »), et le motif du moteur en dessous. Trois sources,
    # une seule idée, à chaque tour. Le pasteur n'y lisait aucune cohérence, et il avait raison.
    #
    # Ici le motif **est** la parole de l'agent : elle accueille, elle relance, elle dit déjà ce
    # qu'on attend. La commenter par une phrase d'écran serait la doubler d'une voix qui en sait
    # moins qu'elle.
    motif = vue.rationale
    if etage == "vestibule":
        dit, motif, sans_rien = vue.rationale, "", False
        # La relance vient du même souffle que la parole. À défaut — le modèle n'a pas posé de
        # question, ou il n'y en avait pas — on nomme quand même la passerelle : c'est ce que
        # le banc exige, et il a raison de l'exiger.
        ask = relance or _RELANCE_DU_VESTIBULE

    return TurnView(
        # Où en est la préparation, aux deux seuls tours qui n'offrent rien — c'est le seul
        # service qu'un tour vide puisse rendre, et c'est l'incise des répondeurs.
        say=dit + (situer(vue.resolved) if sans_rien else ""),
        speaks=forme,
        # Le motif du moteur, tel quel. C'est le filet doré, et il ne se réécrit pas.
        why=motif,
        ask=ask if attend or not vivantes else "",
        expects="choice" if attend else "text",
        stage_code=etage,
        signature=vue.curation_reviewed_by,
        blocks=blocs,
    )
