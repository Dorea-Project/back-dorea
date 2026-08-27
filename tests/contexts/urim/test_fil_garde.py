"""**Le fil se garde, et ce qu'on y écrit peut viser un point.**

🔴 **Deux défauts, une table**, trouvés le 22 et le 23/08/2026 sur un téléphone.

Le premier : *« le fil de discussion disparaît lorsqu'on revient dans la discussion »*. Le
client n'y était pour rien — il affichait tout ce qu'il avait. C'est le serveur qui ne gardait
rien : la saisie d'ouverture, et c'est tout. Le reste vivait en mémoire d'écran et mourait
avec elle.

Le second est une demande : ce qui s'écrit dans le fil doit pouvoir **préparer le document**.
Or un point de plan ne pouvait naître que de l'écran « Mes points ».

## La question difficile, et la façon dont elle a été tranchée

> *« ça peut être point ou pas, parce qu'il peut mettre une pause et revenir changer »*

Si le pasteur ne sait pas encore, la machine ne peut pas savoir. **On ne devine donc jamais :
on lit une désignation, ou on ne range rien.** Une phrase sans adresse n'est pas un échec —
elle attend, et elle se rangera plus tard si le pasteur le veut.
"""

import pytest

from app.contexts.urim.engine.liaison import viser_un_point

#: Les quatre points proposés sur Romains 3:21-30, tels que le modèle les a rendus le 23/08.
POINTS = (
    ("divisions", 0, "La justice de Dieu manifestée maintenant"),
    ("divisions", 1, "La justice par la foi en Jésus-Christ pour tous"),
    ("divisions", 2, "Justifiés gratuitement par la grâce en Jésus-Christ"),
    ("divisions", 3, "Un seul Dieu pour tous, par la foi"),
)


# --- Ce qui désigne -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("saisie", "attendu"),
    [
        ("le deuxième, il faut parler de la loi", 1),
        ("point 3 : trop long", 2),
        ("le dernier me plaît", 3),
        ("le premier, je le garde", 0),
    ],
)
def test_un_rang_designe_le_point_de_ce_rang(saisie, attendu):
    """Le même vocabulaire que partout ailleurs dans ce fil — le pasteur n'apprend rien de
    neuf pour ranger une note."""
    assert viser_un_point(saisie, POINTS) == ("divisions", attendu)


def test_les_mots_du_point_le_designent_aussi():
    """**Par recouvrement, pas par égalité.** Un pasteur écrit « la justice par la foi » pour
    désigner « La justice par la foi en Jésus-Christ pour tous » ; exiger la phrase entière
    rendrait la désignation inutilisable."""
    assert viser_un_point(
        "la justice par la foi mérite deux points", POINTS
    ) == ("divisions", 1)


# --- Ce qui ne désigne pas, et c'est le sujet ------------------------------------------------


def test_une_phrase_sans_adresse_reste_une_parole_du_fil():
    """*« il faut parler de la loi ici »* — **« ici » ne dit rien à une machine.**

    C'est le cas le plus fréquent, et il ne doit pas produire de rangement. La phrase est
    gardée, sans adresse : elle attend."""
    assert viser_un_point("il faut parler de la loi ici", POINTS) is None


def test_un_libelle_trop_court_ne_designe_personne():
    """« la justice » ouvre trois des quatre points. À égalité, **on ne range rien** plutôt que
    de choisir au premier venu — la règle que la liaison applique déjà aux références."""
    assert viser_un_point("la justice", POINTS) is None


def test_un_chiffre_nu_ne_designe_pas_un_point():
    """🔴 **Le piège trouvé en éprouvant la fonction, avant qu'un pasteur ne le trouve.**

    « Romains 3 dit autre chose » rangeait la phrase sous le troisième point. Un chiffre seul
    est une désignation quand l'écran ne porte que des options numérotées ; ici le pasteur
    écrit des références, des versets, des chapitres — le chiffre appartient au texte, pas au
    plan. Le mot « point » est donc exigé devant lui."""
    assert viser_un_point("Romains 3 dit autre chose", POINTS) is None
    assert viser_un_point("point 3 dit autre chose", POINTS) == ("divisions", 2)


def test_un_rang_qui_n_existe_pas_ne_designe_rien():
    """« le sixième » quand quatre points sont affichés ne désigne pas le quatrième."""
    assert viser_un_point("le sixième est faible", POINTS) is None


def test_sans_plan_rien_ne_se_range():
    """Avant qu'un point existe, toute parole est une parole du fil."""
    assert viser_un_point("le deuxième", ()) is None


def test_une_saisie_vide_ne_range_rien():
    assert viser_un_point("   ", POINTS) is None
