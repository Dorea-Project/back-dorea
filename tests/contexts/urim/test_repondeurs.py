"""Les deux répondeurs qui ne préparent rien — et ce banc vérifie **la voix**, pas une valeur.

Un test qui compare une phrase entière se casse au premier mot changé et n'apprend rien. Ce
qu'il faut tenir, ce sont les invariants de ton : ne jamais faire porter l'échec à celui qui
parle, toujours nommer ce qu'Urim fait, et rappeler où en est la préparation.
"""

from __future__ import annotations

import pytest

from app.contexts.urim.engine.repondeurs import (
    repondre_hors_champ,
    repondre_indechiffrable,
)

ANCRE = "Romains 12:9-16"

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


@pytest.mark.parametrize(
    "repondeur", [repondre_hors_champ, repondre_indechiffrable]
)
def test_la_preparation_est_toujours_situee(repondeur) -> None:
    """Un tour perdu doit au moins rappeler où l'on en est."""
    assert ANCRE in repondeur("bon alors", ANCRE)


@pytest.mark.parametrize(
    "repondeur", [repondre_hors_champ, repondre_indechiffrable]
)
def test_sans_ancre_la_reponse_reste_lisible(repondeur) -> None:
    """À l'ouverture il n'y a rien à situer — la phrase ne doit pas s'en trouver bancale."""
    reponse = repondeur("bon alors", None)
    assert "Nous en sommes" not in reponse
    assert "  " not in reponse
    assert reponse.strip() == reponse
