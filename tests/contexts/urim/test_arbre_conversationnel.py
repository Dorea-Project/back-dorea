"""**Aucune branche ne se termine par un mur** — la règle du produit, tenue en CI.

`Outcome.DEGRADE` ne coupe jamais le pipeline, les adaptateurs `Null*` sont des états de
production, une panne de modèle n'est jamais une panne d'Urim. *Aucun mur un vendredi soir.*
Cette règle était tenue côté moteur et **perdue à la présentation**, où personne ne la
cherchait : le tour peut fabriquer un cul-de-sac que le moteur n'a pas voulu.

    Après ce tour, le pasteur a-t-il quelque chose à faire ?

Des options à toucher, une action ouverte, ou une barre de saisie **dont la passerelle est
nommée**. Rien des trois : c'est un mur.

## Le détecteur est celui du banc, importé — pas une seconde copie

`scripts/urim_banc_arbre.py` marche l'arbre contre le corpus réel ; ce fichier tient la même
propriété sur des vues fabriquées, sans base ni réseau. Deux implémentations du mot « mur »
auraient dérivé, et le jour où elles se contrediraient, c'est le banc qu'on croirait.

## Chaque garde est doublée d'un témoin fautif

C'est la parade du dépôt (`test_quatrieme_mur`) : **c'est le détecteur qui est testé**, pas le
vide. Les deux témoins ci-dessous sont les tours **réellement rendus avant la réparation** —
relevés en marchant, pas imaginés.
"""

from __future__ import annotations

import pytest
from scripts.urim_banc_arbre import mur

from app.contexts.urim.interface.turn import (
    ActionItem,
    ActionsBlock,
    ChipItem,
    ChipsBlock,
    TurnView,
    construire_tour,
)

from .test_turn import _Option, _Trace, _Vue

#: Les huit étages qui rendent un tour. `load_context` en fait partie depuis qu'on a marché la
#: **relecture** : rouvrir une préparation décidée rejoue le pipeline, les étages qui rendaient
#: la main ne s'appliquent plus, et c'est lui qui reste en queue de trace.
ETAGES = (
    "route_entry", "weigh_conviction", "resolve_passage", "bound_pericope",
    "serve_corpus", "load_context", "bear_axes", "shape_homiletic", "propose_theme",
)
ISSUES = ("continue", "await_decision", "refuse", "degrade")


# ===================================================== les deux témoins d'avant la réparation


def test_le_detecteur_attrape_le_choix_sur_une_liste_videe() -> None:
    """🔴 **Le mur n°1, tel qu'il était rendu.** Le pasteur avait écarté les dix loci ; le tour
    gardait `expects: choice`, la question restait posée, et le bloc de pastilles arrivait
    **vide**. Le client ouvrait un sélecteur sur rien."""
    temoin = TurnView(
        say="Votre phrase touche plusieurs endroits de la doctrine.",
        why="Une intention peut porter plusieurs doctrines.",
        ask="Sur lequel prêchez-vous ?", expects="choice",
        stage_code="weigh_conviction", blocks=[ChipsBlock(items=[])],
    )

    assert mur(temoin), "le détecteur laisse passer un choix demandé sur zéro option"


def test_le_detecteur_attrape_le_voici_au_dessus_de_rien() -> None:
    """🔴 **Le mur n°2**, et c'était le tour ordinaire : hors unité curée, la pesée dégrade,
    aucun étage aval ne s'applique, et le tour disait « Voici ce que ce texte porte » sans un
    bloc — ni question, ni option, ni action."""
    temoin = TurnView(
        say="Voici ce que ce texte porte — et ce à quoi il résiste.",
        why="Bornes hors unité curée — aucune pesée doctrinale relue.",
        ask="", expects="text", stage_code="bear_axes", blocks=[],
    )

    assert mur(temoin), "le détecteur laisse passer une barre ouverte sans passerelle"


def test_le_detecteur_laisse_passer_un_tour_qui_offre_quelque_chose() -> None:
    """La sévérité ne doit pas condamner ce qui va bien — sans quoi le banc devient du bruit."""
    honnete = TurnView(
        say="Votre phrase touche plusieurs endroits de la doctrine.",
        why="Une intention peut porter plusieurs doctrines.",
        ask="Sur lequel prêchez-vous ?", expects="choice",
        stage_code="weigh_conviction",
        blocks=[ChipsBlock(items=[ChipItem(code="axe:christologie", label="Christologie")])],
    )

    assert mur(honnete) is None


def test_une_action_ouverte_suffit_quand_il_n_y_a_rien_a_choisir() -> None:
    """Le dernier tour ne propose aucune option : c'est « Écrire mes points » qui le sauve.

    ⚠️ Un bouton **grisé** ne compte pas. Trois boutons dont deux verrouillés et un désactivé
    seraient un mur avec des couleurs."""
    tour = TurnView(
        say="Un thème, jamais un titre.", why="Thème proposé.", ask="", expects="text",
        stage_code="propose_theme",
        blocks=[ActionsBlock(items=[
            ActionItem(code="elements", label="Écrire mes points", enabled=True),
            ActionItem(code="deck", label="PowerPoint", enabled=False,
                       unavailable_reason="verrouillé"),
        ])],
    )
    grise = TurnView(
        say="Un thème, jamais un titre.", why="Thème proposé.", ask="", expects="text",
        stage_code="propose_theme",
        blocks=[ActionsBlock(items=[
            ActionItem(code="deck", label="PowerPoint", enabled=False,
                       unavailable_reason="verrouillé"),
        ])],
    )

    assert mur(tour) is None
    assert mur(grise)


# ===================================================== la propriété, sur tout l'arbre


@pytest.mark.parametrize("etage", ETAGES)
@pytest.mark.parametrize("issue", ISSUES)
def test_aucune_cellule_de_l_arbre_ne_rend_un_mur(etage: str, issue: str) -> None:
    """Les 36 cellules, y compris celles qu'aucun étage ne sait produire aujourd'hui.

    ⚠️ **Une cellule inatteignable est testée quand même**, et c'est délibéré : `bound_pericope`
    ne refuse jamais *aujourd'hui*, mais rien n'empêche un étage de demain de le faire, et le
    tour ne doit pas s'effondrer ce jour-là. Le coût est nul, la garde survit à l'auteur."""
    tour = construire_tour(_Vue(trace=[_Trace(etage)], outcome=issue, options=[]))

    assert mur(tour) is None, f"[{etage} · {issue}] {tour.say!r} / ask={tour.ask!r}"


@pytest.mark.parametrize("etage", ETAGES)
def test_aucune_cellule_ne_rend_un_mur_quand_tout_a_ete_ecarte(etage: str) -> None:
    """La liste épuisée, à **chaque** étage qui propose quelque chose.

    C'est le cas du pasteur dont le sujet n'entre dans aucun des dix loci — une intention
    mariale, une fête liturgique — et il n'a rien d'exceptionnel : il suffit d'écarter."""
    vue = _Vue(
        trace=[_Trace(etage)],
        options=[_Option("a", dismissed=True), _Option("b", dismissed=True)],
    )

    tour = construire_tour(vue)

    assert mur(tour) is None, f"[{etage}] tout écarté rend un mur"
    assert not tour.blocks, "un bloc vide est émis là où toutes les options sont écartées"


def test_la_liste_epuisee_cesse_de_demander_un_choix() -> None:
    """⚠️ `expects: choice` sur zéro pastille dit au client d'ouvrir un sélecteur vide.

    Le moteur, lui, attend toujours — et il a raison : son `AWAIT` est intact, ses options
    existent, elles sont seulement toutes reléguées. C'est la **présentation** qui doit cesser
    de réclamer un geste impossible."""
    vue = _Vue(options=[_Option("a", dismissed=True)], outcome="await_decision")

    tour = construire_tour(vue)

    assert tour.expects == "text"
    assert tour.ask.strip(), "aucune passerelle n'est tendue"


def test_la_liste_epuisee_nomme_ce_qu_urim_est_sans_rien_reprocher() -> None:
    """La règle des deux répondeurs, et elle vaut ici : **on nomme ce qu'Urim est**.

    *« Vous avez tout écarté »* juge le pasteur. *« Ces dix axes sont ce que la dogmatique de
    ce corpus sait nommer »* dit une limite du produit, et laisse la personne intacte — c'est
    la même règle que S19 sur les refus."""
    vue = _Vue(options=[_Option(f"axe:{i}", dismissed=True) for i in range(10)])

    dit = construire_tour(vue).say.lower()

    assert "corpus" in dit, "le tour ne nomme pas la limite qui est celle du produit"
    for reproche in ("vous avez", "écarté", "ecarte", "refusé", "aucun choix"):
        assert reproche not in dit, f"le tour renvoie « {reproche} » au pasteur"


def test_un_tour_sans_rien_a_montrer_situe_la_preparation() -> None:
    """L'ancre des répondeurs : *le seul service qu'un tour vide puisse rendre*.

    Un pasteur devant un écran qui ne lui offre rien a d'abord besoin de savoir où en est son
    travail — sans quoi il ne sait même pas ce qu'il perdrait en recommençant."""
    vue = _Vue(trace=[_Trace("bear_axes")], outcome="degrade", options=[])
    vue.resolved = "Luc 1:28"

    assert "Luc 1:28" in construire_tour(vue).say


def test_un_choix_demande_porte_toujours_sa_question() -> None:
    """🔴 Relevé en marchant : `bear_axes` rendait deux axes à choisir **sans poser de question**.

    Sa phrase était celle des pesées — « Voici ce que ce texte porte » —, qui n'appelle aucune
    réponse. Le pasteur voyait deux pastilles et aucune raison de les toucher."""
    for etage in ETAGES:
        tour = construire_tour(_Vue(trace=[_Trace(etage)], outcome="await_decision"))
        assert tour.expects == "choice"
        assert tour.ask.strip(), f"[{etage}] un choix demandé sans question posée"


def test_le_say_ne_promet_jamais_ce_que_l_ecran_ne_montre_pas() -> None:
    """« Voici… » au-dessus de zéro bloc est un mur qui a l'air d'une réponse.

    C'est la forme sous laquelle le mur survit à une relecture de code : la phrase est juste
    pour l'étage, et fausse pour l'écran."""
    for etage in ETAGES:
        for issue in ISSUES:
            tour = construire_tour(_Vue(trace=[_Trace(etage)], outcome=issue, options=[]))
            if not tour.blocks:
                assert not tour.say.lstrip().lower().startswith("voici"), (
                    f"[{etage} · {issue}] promet un contenu qu'il n'a pas"
                )


def test_le_filet_dore_traverse_tous_les_tours_de_l_arbre() -> None:
    """§5.2 — *pas de conclusion sans provenance*, y compris aux tours qu'on vient d'ajouter."""
    for etage in ETAGES:
        for issue in ISSUES:
            for options in ([], [_Option("a")], [_Option("a", dismissed=True)]):
                tour = construire_tour(
                    _Vue(trace=[_Trace(etage)], outcome=issue, options=options)
                )
                assert tour.say.strip() and tour.why.strip()
