"""Les deux répondeurs qui ne préparent rien — et ce banc vérifie **la voix**, pas une valeur.

Un test qui compare une phrase entière se casse au premier mot changé et n'apprend rien. Ce
qu'il faut tenir, ce sont les invariants de ton : ne jamais faire porter l'échec à celui qui
parle, toujours nommer ce qu'Urim fait, et rappeler où en est la préparation.
"""

from __future__ import annotations

import pytest

from app.contexts.urim.engine.repondeurs import (
    _REPONDEURS,
    repondre_acquiescement,
    repondre_changer_de_sujet,
    repondre_demander_production,
    repondre_hors_champ,
    repondre_indechiffrable,
    repondre_interroger_texte,
    repondre_interroger_travail,
    repondre_panne,
    repondre_preciser,
    repondre_reference_introuvable,
    repondre_sans_lecture,
)

ANCRE = "Romains 12:9-16"

#: **Tous** les répondeurs, y compris les trois qui ne viennent d'aucune intention. Les
#: invariants de ton valent pour la voix entière du produit, pas pour deux fonctions.
TOUS = (
    *_REPONDEURS.values(),
    repondre_acquiescement,
    repondre_sans_lecture,
    repondre_panne,
    repondre_reference_introuvable,
)

#: ⚠️ Les tournures qui font porter l'échec à celui qui parle. Aucune ne doit apparaître.
#:
#: « Je n'ai pas compris » est fausse en plus d'être blessante : une parole captée par un micro
#: resté ouvert a été parfaitement comprise — elle ne nous était pas destinée.
_REPROCHES = (
    "je n'ai pas compris",
    "je ne comprends pas",
    "votre demande",
    "hors sujet",
    "vous n'avez pas",
    "incorrect",
    "invalide",
    "erreur",
)

#: Ce qu'Urim est. L'une de ces marques doit toujours être là : une réponse qui ne dit pas ce
#: qu'on fait laisse la personne sans direction.
_CE_QU_ON_EST = ("prédication", "préparation", "texte", "Écriture", "atelier")


def _sans_reproche(reponse: str) -> None:
    bas = reponse.lower()
    for reproche in _REPROCHES:
        assert reproche not in bas, f"la réponse reproche : « {reproche} »"


def _nomme_ce_qu_on_est(reponse: str) -> None:
    assert any(marque in reponse for marque in _CE_QU_ON_EST)


# -- hors_champ ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "saisie",
    [
        "comment annoncer un deces a l'assemblee",
        "que faire d'un membre qui ne vient plus",
        "je me sens decourage en ce moment",
        "mon eglise se vide et je ne sais plus quoi faire",
    ],
)
def test_le_conseil_pastoral_recoit_une_passerelle(saisie: str) -> None:
    """🔴 **Le pasteur qui demande comment annoncer un décès n'a rien fait de mal.**

    Sans la seconde phrase — *si un passage vous vient, donnez-le-moi* — le tour serait une
    porte fermée. C'est le défaut le plus facile à commettre ici."""
    reponse = repondre_hors_champ(saisie, ANCRE)
    _sans_reproche(reponse)
    _nomme_ce_qu_on_est(reponse)
    assert "donnez-le-moi" in reponse


@pytest.mark.parametrize(
    "saisie",
    ["prie pour moi", "tu penses quoi de moi", "est-ce que tu crois en Dieu", "tu es qui"],
)
def test_l_adresse_personnelle_recoit_une_limite(saisie: str) -> None:
    reponse = repondre_hors_champ(saisie, ANCRE)
    _sans_reproche(reponse)
    assert "ne suis pas quelqu'un" in reponse


def test_une_demande_ordinaire_au_vouvoiement_reste_pastorale() -> None:
    """⚠️ Le pronom seul ne fait pas l'adresse personnelle.

    « vous pouvez m'ouvrir Romains 12 » s'adresse aussi à Urim. Basculer sur la limite nette
    parce qu'un « vous » traîne serait rabrouer une demande ordinaire."""
    reponse = repondre_hors_champ("vous pouvez m'aider sur ce membre difficile", ANCRE)
    assert "ne suis pas quelqu'un" not in reponse


# -- indechiffrable ------------------------------------------------------------------


@pytest.mark.parametrize(
    "saisie",
    [
        "Ma voiture 406, a besoin de reparation , jefgf Paradis",
        "et donc je disais a mon frere que",
        "bon alors",
    ],
)
def test_le_micro_ouvert_ne_recoit_aucun_reproche(saisie: str) -> None:
    """Une parole captée par un micro resté ouvert a été comprise — elle ne nous visait pas."""
    reponse = repondre_indechiffrable(saisie, ANCRE)
    _sans_reproche(reponse)


# -- l'ancre, qui est le seul service d'un tour perdu ---------------------------------


@pytest.mark.parametrize("repondeur", TOUS)
def test_la_preparation_est_toujours_situee(repondeur) -> None:
    """Un tour perdu doit au moins rappeler où l'on en est."""
    assert ANCRE in repondeur("bon alors", ANCRE)


@pytest.mark.parametrize("repondeur", TOUS)
def test_sans_ancre_la_reponse_reste_lisible(repondeur) -> None:
    """À l'ouverture il n'y a rien à situer — la phrase ne doit pas s'en trouver bancale."""
    reponse = repondeur("bon alors", None)
    assert "Nous en sommes" not in reponse
    assert "  " not in reponse
    assert reponse.strip() == reponse


# -- la voix, sur les dix répondeurs ---------------------------------------------------


@pytest.mark.parametrize("repondeur", TOUS)
@pytest.mark.parametrize("ancre", [ANCRE, None])
def test_aucun_repondeur_ne_fait_porter_l_echec_a_celui_qui_parle(repondeur, ancre) -> None:
    """La règle de la porte, tenue sur la voix entière : **on nomme ce qu'Urim est**.

    Elle vaut jusque sur la panne, et c'est là qu'elle se renverse : une coupure est de notre
    côté, donc on la nomme — mais on ne dit jamais qu'on n'a pas compris."""
    reponse = repondeur("bon alors", ancre)
    _sans_reproche(reponse)
    _nomme_ce_qu_on_est(reponse)


# -- les trois intentions qui n'ont rien à dire sans texte -----------------------------


@pytest.mark.parametrize(
    "repondeur",
    [repondre_interroger_texte, repondre_interroger_travail, repondre_demander_production],
)
def test_sans_texte_ouvert_le_repondeur_dit_la_verite(repondeur) -> None:
    """⚠️ Documenté dans `_SYSTEME_AIGUILLAGE` : *« Quel plan je peux tenir ? » posé avant
    qu'un texte soit résolu part quand même en `interroger_travail`, et le répondeur dit la
    vérité — il faut d'abord un texte.*

    L'aiguilleur est aveugle à l'état, exprès : il reste une fonction pure, et ne reçoit
    aucune confidence sur une assemblée qu'il n'a pas besoin de connaître."""
    reponse = repondeur("quel plan je peux tenir", None)
    assert "Aucun texte n'est encore ouvert" in reponse


def test_le_livrable_verrouille_dit_pourquoi_il_l_est() -> None:
    """⚠️ Un bouton grisé muet est un mensonge poli — et une demande de PowerPoint mérite la
    même honnêteté que le bouton."""
    reponse = repondre_demander_production("mets moi ça en powerpoint", ANCRE)
    assert "citation projetée" in reponse


def test_changer_de_sujet_propose_et_ne_ferme_rien() -> None:
    """🔴 **Une intention ne déclenche jamais un acte irréversible.** Un faux positif qui
    fermerait la préparation détruirait le travail d'un samedi soir."""
    reponse = repondre_changer_de_sujet("en fait je vais prêcher sur autre chose", ANCRE)
    assert "ouvrez-en une neuve" in reponse
    assert "attendra entière" in reponse


def test_le_motif_du_corpus_traverse_intact() -> None:
    """⚠️ **Le même partage que le filet doré du tour.**

    « Hébreux 2 compte 18 versets » lui apprend quelque chose ; « référence invalide » le
    laisse chercher. C'est S19 — un refus nomme ce qui manque au **corpus**, jamais ce qui
    manque au pasteur — et le reformuler ferait perdre exactement l'information utile."""
    motif = "Hébreux 2 compte 18 versets — il n'y a pas de verset 29."

    reponse = repondre_reference_introuvable(motif, ANCRE)

    assert reponse.startswith(motif)
    assert "autre référence" in reponse
    assert ANCRE in reponse, "la préparation ne bouge pas, et on le situe"


def test_preciser_ne_promet_que_ce_qui_existe() -> None:
    """Écarter ne supprime pas : l'option reste dans la liste, reléguée. Promettre autre
    chose — « reformulez et je reprends » — promettrait une route qui abandonne la
    préparation au lieu de la corriger."""
    reponse = repondre_preciser("ce n'est pas ça", ANCRE)
    assert "reste dans la liste" in reponse
