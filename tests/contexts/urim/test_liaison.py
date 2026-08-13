"""La liaison — ce qu'elle lie, et surtout **ce qu'elle refuse de lier**.

Le second groupe compte davantage. Une intention mal aiguillée donne une réponse hors sujet ;
une désignation manquée fait agir sur le mauvais objet. La liaison doit donc rendre la main
plutôt que de deviner, et ces tests fixent la frontière.
"""

from __future__ import annotations

import pytest

from app.contexts.urim.engine.liaison import Geste, lier
from app.contexts.urim.engine.state import Reference

#: L'écran d'un tour : quatre passages proposés, dans l'ordre.
OPTIONS = (
    Reference(book="Romains", chapter=12, verse_start=9, verse_end=16),
    Reference(book="1 Jean", chapter=4, verse_start=7, verse_end=12),
    Reference(book="Luc", chapter=15, verse_start=11, verse_end=24),
    Reference(book="Hébreux", chapter=13, verse_start=1, verse_end=6),
)

AXES = (
    ("soteriologie", "Le salut offert"),
    ("ecclesiologie", "La vie de l'assemblée"),
)


# -- ce qu'elle lie ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("saisie", "attendu"),
    [
        ("le deuxième", 1),
        ("le 2", 1),
        ("prends le troisième", 2),
        ("le dernier", 3),
        ("le premier", 0),
    ],
)
def test_elle_lie_un_rang(saisie: str, attendu: int) -> None:
    assert lier(saisie, OPTIONS, AXES).option == attendu


@pytest.mark.parametrize(
    ("saisie", "attendu"),
    [
        ("Romains 12", 0),
        ("romains 12:9-16", 0),
        ("1 Jean 4", 1),
        ("luc 15", 2),
    ],
)
def test_elle_lie_une_reference_affichee(saisie: str, attendu: int) -> None:
    """⚠️ La référence prime sur le rang, et l'ordre n'est pas arbitraire.

    « Romains 12 » contient le nombre 12 ; lu comme un rang, il ne désignerait rien, et lu
    comme un chiffre isolé il pourrait désigner n'importe quoi. La référence est exacte."""
    assert lier(saisie, OPTIONS, AXES).option == attendu


def test_elle_reconnait_le_retrait() -> None:
    lu = lier("non, pas le deuxième", OPTIONS, AXES)
    assert lu.option == 1
    assert lu.geste is Geste.ECARTER


def test_elle_reconnait_l_acquiescement() -> None:
    assert lier("d'accord", OPTIONS, AXES).geste is Geste.ACQUIESCER
    assert lier("OK", OPTIONS, AXES).geste is Geste.ACQUIESCER


def test_l_acquiescement_doit_occuper_toute_la_saisie() -> None:
    """« oui mais pas celui-là » n'est pas un acquiescement — c'est un refus."""
    lu = lier("oui mais pas le premier", OPTIONS, AXES)
    assert lu.geste is Geste.ECARTER
    assert lu.option == 0


@pytest.mark.parametrize(
    ("saisie", "attendu"),
    [
        ("v. 9 à 13", (9, 13)),
        ("versets 9-13", (9, 13)),
        ("du 9 au 13", (9, 13)),
        ("9 a 13", (9, 13)),
    ],
)
def test_elle_lie_des_bornes(saisie: str, attendu: tuple[int, int]) -> None:
    lu = lier(saisie, OPTIONS, AXES)
    assert lu.bornes == attendu
    assert lu.geste is Geste.BORNER


def test_elle_lie_un_locus_par_son_titre() -> None:
    assert lier("la vie de l'assemblée", OPTIONS, AXES).axe == "ecclesiologie"


# -- ce qu'elle refuse de lier -------------------------------------------------------


@pytest.mark.parametrize(
    "saisie",
    [
        "celui-là",
        "ce texte",
        "celui du milieu",
        "l'autre",
    ],
)
def test_elle_rend_la_main_sur_un_demonstratif_seul(saisie: str) -> None:
    """🔴 **Le cas qui justifie tout l'étage.**

    Deux options peuvent convenir, et se tromper d'objet coûte plus cher qu'un appel de
    modèle. Elle rend une liaison vide, l'aiguilleur prend le tour."""
    assert not lier(saisie, OPTIONS, AXES)


@pytest.mark.parametrize(
    "saisie",
    [
        "je veux prêcher sur le pardon",
        "l'amour fraternel n'existe plus dans l'eglise",
        "Dieu est l'auteur et le consommateur de notre foi",
        "que veut dire upodema",
    ],
)
def test_elle_rend_la_main_sur_une_phrase_neuve(saisie: str) -> None:
    """Les saisies réelles du Pasteur X. Aucune ne désigne l'écran — ce sont des sujets."""
    assert not lier(saisie, OPTIONS, AXES)


def test_un_rang_hors_de_l_ecran_ne_compte_pas() -> None:
    """« le septième » quand quatre options sont affichées ne désigne rien."""
    assert lier("le sixième", OPTIONS, AXES).option is None


def test_une_reference_absente_de_l_ecran_n_est_pas_de_son_ressort() -> None:
    """C'est une saisie neuve : le détecteur d'entrée la traitera à l'étage suivant."""
    assert lier("Aggée 1:5", OPTIONS, AXES).option is None


def test_une_reference_ne_se_reconnait_pas_en_morceaux() -> None:
    """⚠️ « romains 12 » ne doit pas se lire dans « romains 8 et hébreux 12 »."""
    assert lier("romains 8 et hébreux 12", OPTIONS, AXES).option is None


def test_des_bornes_a_l_envers_ne_sont_pas_des_bornes() -> None:
    assert lier("du 13 au 9", OPTIONS, AXES).bornes is None


def test_une_saisie_vide_ne_designe_rien() -> None:
    assert not lier("   ", OPTIONS, AXES)
    assert not lier("!!!", OPTIONS, AXES)
