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


# -- ce que le banc du tour a trouvé -------------------------------------------------


TITRES = (
    ("texte:unite", "La charité sans hypocrisie"),
    ("axe:ecclesiologie", "La vie de l'assemblée"),
)


def test_un_intitule_qui_contient_un_mot_de_retrait_ne_s_ecarte_pas_lui_meme() -> None:
    """🔴 **Le pire défaut possible : le bon objet, le mauvais geste.**

    « La charité sans hypocrisie » est l'intitulé d'unité de la maquette, et « sans » est un
    marqueur de retrait. Désigner l'unité l'écartait — le pasteur choisissait son texte et le
    voyait disparaître. Le geste se cherche donc **hors de ce qui a été désigné** : les mots
    d'un intitulé appartiennent à l'intitulé."""
    lu = lier("La charité sans hypocrisie", OPTIONS, TITRES)

    assert lu.axe == "texte:unite"
    assert lu.geste is None


def test_un_retrait_hors_de_l_intitule_reste_un_retrait() -> None:
    """L'autre bout : « pas » est du pasteur, il est hors de l'empan de l'intitulé."""
    lu = lier("pas la charité sans hypocrisie", OPTIONS, TITRES)

    assert lu.axe == "texte:unite"
    assert lu.geste is Geste.ECARTER


@pytest.mark.parametrize(
    "saisie",
    [
        "je veux faire un culte sur l'adultère dans",
        "Propose-moi un theme.",
        "y a un risque de proof texting sur ce que je fais ?",
        "attends deux minutes je arrive euh le fils la le retour bon",
    ],
)
def test_un_cardinal_ecrit_n_est_pas_un_rang(saisie: str) -> None:
    """🔴 **Quatre saisies sur vingt et une décidaient une option sans que personne ne le veuille.**

    « un » est un article avant d'être un rang. L'ordinal n'est jamais ambigu ; le cardinal
    l'est presque toujours — et un rang inventé fait agir sur le mauvais objet, là où un rang
    manqué ne coûte qu'un appel de modèle."""
    assert lier(saisie, OPTIONS, AXES).option is None


def test_les_ordinaux_et_les_chiffres_restent_lus() -> None:
    """La contrepartie : ce qui n'est pas ambigu ne se perd pas."""
    assert lier("le deuxième", OPTIONS, AXES).option == 1
    assert lier("le 2", OPTIONS, AXES).option == 1
    assert lier("le second", OPTIONS, AXES).option == 1


# -- la notation du pasteur ----------------------------------------------------------
#
# `Hb 2v29`, `Jn14v28`, `Eph 1v20-22`, `jn 2:3` — ses quatre saisies attestées, et pas une
# seule de la forme `Livre chapitre:verset`. La notation est absorbée en amont par le lecteur
# du corpus ; ce qui arrive ici, ce sont des `Reference`. On ne compare donc plus des chaînes,
# on compare des passages.


UNITES = (
    Reference(book="Jean", chapter=14, verse_start=15, verse_end=31),
    Reference(book="Jean", chapter=2, verse_start=1, verse_end=11),
    Reference(book="Éphésiens", chapter=1, verse_start=15, verse_end=23),
    Reference(book="Hébreux", chapter=2, verse_start=1, verse_end=18),
)

#: Ce que `lire` rend sur `Jn14v28` : **quatre** candidats, parce qu'il refuse de trancher
#: l'homonymie (S24). C'est l'écran qui va le faire.
JN14V28 = tuple(
    Reference(book=nom, chapter=14, verse_start=28)
    for nom in ("Jean", "1 Jean", "2 Jean", "3 Jean")
)


def test_la_notation_du_pasteur_designe_l_option_affichee() -> None:
    """🔴 **Une référence à l'écran partait quand même au modèle.**

    Le lecteur qui comprend `Jn14v28` existe depuis la chaîne de textes d'appui ; il ne parlait
    à personne dans le tour."""
    assert lier("Jn14v28", UNITES, AXES, JN14V28).option == 0


def test_l_ecran_tranche_l_homonymie_sans_que_personne_ne_devine() -> None:
    """⚠️ `Jn` désigne quatre livres, et `lire` les rend tous les quatre. Confrontés à l'écran,
    trois ne visent rien — il reste Jean, et aucune règle n'a eu à préférer un livre."""
    lues = tuple(
        Reference(book=nom, chapter=2, verse_start=3)
        for nom in ("Jean", "1 Jean", "2 Jean", "3 Jean")
    )
    assert lier("jn 2:3", UNITES, AXES, lues).option == 1


def test_les_versets_choisissent_entre_les_unites_d_un_meme_chapitre() -> None:
    """C'est ce que l'appariement par jetons ne sait pas faire : « Ga 5 » désigne les trois
    unités de Galates 5, et il prendrait la première."""
    galates = (
        Reference(book="Galates", chapter=5, verse_start=1, verse_end=12),
        Reference(book="Galates", chapter=5, verse_start=13, verse_end=15),
        Reference(book="Galates", chapter=5, verse_start=16, verse_end=26),
    )
    lues = (Reference(book="Galates", chapter=5, verse_start=13),)

    assert lier("Ga 5v13", galates, AXES, lues).option == 1


def test_la_notation_se_combine_avec_le_retrait() -> None:
    """« non, pas Jn14v28 » : le lecteur ne voit que la référence, le geste reste au pasteur."""
    lu = lier("non, pas Jn14v28", UNITES, AXES, JN14V28)

    assert lu.option == 0
    assert lu.geste is Geste.ECARTER


def test_un_nom_de_livre_nu_ne_designe_rien() -> None:
    """🔴 **La garde qui rend cet appariement sûr.**

    `lire` rend volontiers un livre entier — c'est juste à la porte, où le pasteur a *déclaré*
    saisir une référence. Ici rien n'est déclaré : « Marc a quitté l'église » choisirait un
    texte que personne n'a nommé. Le chapitre est exigé, comme pour les jetons."""
    assert lier("Jean", UNITES, AXES, (Reference(book="Jean"),)).option is None


def test_deux_options_visees_rendent_la_main() -> None:
    """La règle de tout l'étage : deux options peuvent convenir, et se tromper d'objet coûte
    plus cher qu'un appel de modèle."""
    deux = (
        Reference(book="Jean", chapter=14, verse_start=1, verse_end=14),
        Reference(book="Jean", chapter=14, verse_start=15, verse_end=31),
    )
    assert lier("Jn 14", deux, AXES, (Reference(book="Jean", chapter=14),)).option is None


def test_un_verset_hors_des_bornes_affichees_ne_designe_rien() -> None:
    """⚠️ `Hb 2v29` est **la référence inexistante** des notes du Pasteur X — Hébreux 2 compte
    18 versets. On ne corrige pas : deviner qu'il voulait 2:9 serait décider à sa place sur la
    foi d'une touche voisine. La saisie repart donc à l'aiguilleur."""
    lues = (Reference(book="Hébreux", chapter=2, verse_start=29),)
    assert lier("Hb 2v29", UNITES, AXES, lues).option is None


def test_deux_axes_nommes_rendent_la_main() -> None:
    """Le défaut trouvé en séance, le 19/08.

    Un pasteur écrit « Christologie et Anthropologie » devant les pastilles d'axes. La
    liaison posait christologie — et l'ordre inverse donnait le même résultat, puisque
    c'est l'écran qui tranchait, jamais ses mots. Le second axe tombait en silence et la
    décision partait en base."""
    for saisie in ("Le salut offert et La vie de l'assemblée",
                   "La vie de l'assemblée et Le salut offert"):
        assert lier(saisie, OPTIONS, AXES).axe is None, saisie


def test_un_seul_axe_nomme_se_lie_toujours() -> None:
    """La garde ne doit pas emporter le cas normal."""
    assert lier("Le salut offert", OPTIONS, AXES).axe == "soteriologie"


def test_deux_passages_nommes_par_leurs_jetons_rendent_la_main() -> None:
    """Même règle que pour la notation lue : plusieurs visés, on rend la main."""
    assert lier("Romains 12 et Luc 15", OPTIONS, AXES).option is None


def test_un_seul_passage_nomme_par_ses_jetons_se_lie() -> None:
    assert lier("Romains 12", OPTIONS, AXES).option == 0


def test_le_plus_precis_gagne_sur_son_prefixe() -> None:
    """« Hébreux 13:1 » est un préfixe de « Hébreux 13:1-2 ».

    Les deux se reconnaissent dans la saisie ; les compter à égalité ferait rendre la main
    sur une phrase qui ne porte aucune ambiguïté — le pasteur a écrit ses deux bornes."""
    deux = (
        Reference(book="Hébreux", chapter=13, verse_start=1, verse_end=2),
        Reference(book="Hébreux", chapter=13, verse_start=1),
    )
    assert lier("Hébreux 13:1-2", deux, AXES).option == 0
    assert lier("Hébreux 13:1", deux, AXES).option == 1


def test_sans_bornes_ecrites_deux_unites_du_meme_chapitre_rendent_la_main() -> None:
    """Le livre et le chapitre seuls ne départagent pas deux unités du même chapitre."""
    deux = (
        Reference(book="Hébreux", chapter=13, verse_start=1, verse_end=2),
        Reference(book="Hébreux", chapter=13, verse_start=3, verse_end=6),
    )
    assert lier("Hébreux 13", deux, AXES).option is None
