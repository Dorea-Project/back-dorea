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

    say    déterministe, par étage — ce qu'Urim vient de faire
    why    LE MOTIF DU MOTEUR, tel quel — jamais réécrit
    ask    déterministe, et seulement quand le moteur attend une décision

C'est le même partage que les deux répondeurs `hors_champ` et `indechiffrable` : la voix du
produit est écrite en français, une fois, et relue ; ce qui vient du raisonnement traverse
intact.

⚠️ **`why` n'est jamais nul, et c'est une règle du produit.** *« Chaque réponse porte son filet
doré. C'est ce qui sépare un atelier d'un oracle. »* Un tour sans motif serait une conclusion
sans provenance — la seule chose qu'Urim s'interdit.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

#: ⚠️ **Ce qu'Urim vient de faire, par étage — et rien de plus.**
#:
#: Ces phrases sont déterministes pour la même raison que celles des répondeurs : le modèle n'a
#: aucun canal de sortie en prose, et lui en ouvrir un pour annoncer ce que le moteur a fait
#: serait payer un appel pour une phrase qu'on peut écrire une fois.
#:
#: `ask` ne sert que lorsque le moteur **attend** une décision. Un étage qui continue ne pose
#: aucune question, et une question sans attente ferait croire au pasteur qu'il doit répondre.
_PHRASES: dict[str, tuple[str, str]] = {
    "route_entry": (
        "Je lis votre saisie avant tout le reste.",
        "Est-ce bien de cela que vous voulez parler ?",
    ),
    "weigh_conviction": (
        "Votre phrase touche plusieurs endroits de la doctrine.",
        "Sur lequel prêchez-vous ?",
    ),
    "resolve_passage": (
        "Plusieurs textes traitent ce sujet — aucun ne s'impose seul.",
        "Lequel ouvrons-nous ?",
    ),
    "bound_pericope": (
        "Vos bornes ne coïncident pas avec l'unité relue.",
        "Lesquelles gardons-nous ?",
    ),
    "bear_axes": (
        "Voici ce que ce texte porte — et ce à quoi il résiste.",
        "",
    ),
    "shape_homiletic": (
        "Voici les plans que ce texte peut tenir, et ceux qu'il refuse.",
        "Lequel voulez-vous suivre ?",
    ),
    "propose_theme": (
        "Un thème, jamais un titre — le titre, c'est votre voix.",
        "",
    ),
    "serve_corpus": (
        "Le texte est servi, avec ce que la curation en dit.",
        "",
    ),
}

_SAY_PAR_DEFAUT = "Voici où nous en sommes."


class ChipItem(BaseModel):
    code: str
    label: str
    hint: str = ""
    origin: str = "moteur"
    selected: bool = False


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


class BearingsBlock(BaseModel):
    kind: Literal["bearings"] = "bearings"
    items: list[BearingItem]
    caveats: list[str] = []


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


#: Le livrable reste fermé tant qu'une citation projetée n'est pas contrôlée (trou 3). Le motif
#: voyage avec le bouton : c'est la seule façon honnête de le montrer.
_LIVRABLE_FERME = (
    "Le livrable n'est pas ouvert : une citation projetée doit d'abord être contrôlée."
)

#: Les étages dont les options sont des textes à ouvrir, non des pastilles à toucher.
_ETAGES_D_UNITES = frozenset({"resolve_passage"})


def _pastilles(options: list) -> list[ChipItem]:
    return [
        ChipItem(
            code=o.code, label=o.label, hint=o.rationale[:80],
            origin=o.origin, selected=False,
        )
        for o in options
        if not o.dismissed
    ]


def _blocs(vue, etage: str) -> list[Block]:
    """Les blocs que cet étage a de quoi remplir — jamais un bloc vide.

    L'ordre est celui de l'écran, de haut en bas, et il est fixé ici : le client rend ce qu'on
    lui donne dans l'ordre où on le lui donne."""
    blocs: list[Block] = []

    if etage in _ETAGES_D_UNITES and vue.options:
        blocs.append(UnitsBlock(groups=[UnitGroup(
            role="proposed",
            heading="Traitent votre sujet",
            items=[
                UnitItem(code=o.code, label=o.label, reference=o.code, rationale=o.rationale)
                for o in vue.options if not o.dismissed
            ],
        )]))
    elif etage == "bound_pericope" and vue.options:
        blocs.append(BoundsBlock(
            items=_pastilles(vue.options),
            consequence=(
                "Si vous gardez vos bornes, je ne pourrai plus vous alerter sur un risque "
                "de proof-texting."
            ),
        ))
    elif vue.options:
        blocs.append(ChipsBlock(items=_pastilles(vue.options)))

    if vue.bearings:
        blocs.append(BearingsBlock(
            items=[
                BearingItem(
                    axis_code=b.axis_code, label=b.label,
                    strength=b.strength, rationale=b.rationale,
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
                code="deck", label="PowerPoint", enabled=False,
                unavailable_reason=_LIVRABLE_FERME,
            ),
            ActionItem(
                code="sheet", label="Fiche de chaire", enabled=False,
                unavailable_reason=_LIVRABLE_FERME,
            ),
        ]))

    return blocs


def construire_tour(vue) -> TurnView:
    """La présentation conversationnelle de ce que la vue porte déjà.

    ⚠️ **`expects` vient de l'issue, jamais de l'étage.** Un même étage attend une décision ou
    n'attend rien selon ce que le corpus lui a donné — coder l'attente dans la table des
    phrases ferait poser une question là où le moteur n'attend personne, et le pasteur
    répondrait à un tour qui a déjà continué."""
    etage = vue.trace[-1].stage_code if vue.trace else "route_entry"
    say, ask = _PHRASES.get(etage, (_SAY_PAR_DEFAUT, ""))

    attend = vue.outcome == "await_decision"
    return TurnView(
        say=say,
        # Le motif du moteur, tel quel. C'est le filet doré, et il ne se réécrit pas.
        why=vue.rationale,
        ask=ask if attend else "",
        expects="choice" if attend else "text",
        stage_code=etage,
        signature=vue.curation_reviewed_by,
        blocks=_blocs(vue, etage),
    )
