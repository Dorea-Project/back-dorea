"""La Bible que tout le dépôt partage — **un seul fichier, et il est versionné**.

`data/ls1910.json` est lu par `mission` (la carte d'invitation, M9-1) et par le semis d'`urim`.
Il a existé un temps où chacun tenait son propre extrait tapé à la main : deux Bibles qui
pouvaient diverger, et qui divergeaient. La leçon a été payée une fois ; ce fichier existe pour
qu'elle ne se repaie pas.

Elle s'est pourtant repayée autrement. Trente versets portaient une **espace fine** (U+2009)
glissée entre l'apostrophe et la suite du mot — « l'<U+2009>alliance », « qu'<U+2009>ils ». La
base de développement avait été recousue à la main ; le fichier livré, non. Le dépôt servait
donc deux textes différents selon qu'on passait par `mission` ou par `urim`, et personne ne
pouvait le voir : une espace fine est invisible à l'œil.

D'où ces tests, qui gardent l'invariant **sur le fichier livré** et non sur une copie fabriquée
pour l'occasion — c'était le seul endroit où le défaut pouvait se cacher.
"""

import json
import re
from pathlib import Path

import pytest
from scripts.build_lsg_dataset import SORTIE, recoller_les_elisions

#: Les apostrophes du normaliseur partagé, écrites en échappement : sur un clavier ces glyphes
#: sont indiscernables, et une relecture ne verrait pas qu'il en manque une.
APOSTROPHES = "'" \
    "\u2019" \
    "\u02bc" \
    "\u02bb`"

#: Une apostrophe suivie de n'importe quelle espace — fine, insécable ou ordinaire. En français
#: une apostrophe n'est **jamais** suivie d'une espace.
_APOSTROPHE_PUIS_ESPACE = re.compile("[" + APOSTROPHES + r"]\s")


@pytest.fixture(scope="module")
def bible() -> dict[str, str]:
    if not SORTIE.exists():
        pytest.skip(f"{SORTIE} absent — python scripts/build_lsg_dataset.py")
    return json.loads(SORTIE.read_text(encoding="utf-8"))


def test_aucune_elision_n_est_detachee_de_son_mot(bible):
    """🔴 **Le défaut fait deux dégâts, et le second est le pire.**

    *À l'écran* : `mission` sert ce fichier tel quel sur la carte d'invitation, donc un chercheur
    qui n'est pas de l'église lit « le sang de l'<U+2009>alliance ». C'est le premier texte
    biblique que Dorea met sous les yeux de quelqu'un du dehors.

    *À la recherche* : le normaliseur partagé **colle** l'élision au mot suivant, précisément
    pour qu'un pasteur qui tape « lamour » rencontre « l'amour » (S21). Ici il n'a rien à quoi la
    coller et rend « l alliance » — si bien que « lalliance » ne rencontre **jamais** Matthieu
    26:28. La panne est du mauvais côté : elle ne dit rien, elle fait seulement disparaître un
    verset."""
    casses = {ref: t for ref, t in bible.items() if _APOSTROPHE_PUIS_ESPACE.search(t)}
    assert casses == {}, f"{len(casses)} versets : {list(casses)[:5]}"


def test_aucun_verset_ne_traine_d_espace_au_bord(bible):
    """La source laisse une espace finale sur presque chaque verset.

    Elle ne se voit pas à l'écran et fausse toute comparaison de chaîne — dont le contrôle de
    citation, qui exige que le projeté soit une **sous-chaîne contiguë** du corpus (S4)."""
    assert [ref for ref, t in bible.items() if t != t.strip()] == []


def test_le_recollage_recolle_l_elision_et_rien_d_autre():
    """Le couple : ce que la règle doit reprendre, et ce à quoi elle ne doit pas toucher.

    Une règle qui recollerait toute espace serait aussi fausse que pas de règle du tout — elle
    souderait « dit : Voici » en « dit :Voici », et mangerait l'espace fine avant un
    point-virgule, qui est de la typographie française correcte. C'est l'appariement
    **apostrophe → lettre** qui décide, et lui seul."""
    fine = "\u2009"
    assert recoller_les_elisions(f"le sang de l\u2019{fine}alliance") == (
        "le sang de l\u2019alliance"
    )
    assert recoller_les_elisions(f"qu\u2019{fine}ils") == "qu\u2019ils"
    assert recoller_les_elisions(f"d\u2019{fine}un an") == "d\u2019un an"
    assert recoller_les_elisions("n' echappera") == "n'echappera"

    # Les espaces francaises AVANT une ponctuation double sont ecrites en echappement, et
    # elles sont le vrai enjeu du couple : elles ressemblent au defaut sans en etre un.
    for intact in ("l\u2019alliance", "il dit\u00a0: Voici", "des villes\u202f; et voici"):
        assert recoller_les_elisions(intact) == intact


def test_un_chiffre_derriere_n_est_pas_une_elision():
    """L'apostrophe ne se recolle qu'à une **lettre**.

    Le corpus ne présente pas le cas aujourd'hui, et c'est justement pourquoi la règle doit le
    dire elle-même : une source future écrira « l' an 40 », et souder une élision à un nombre
    fabriquerait un mot qui n'existe dans aucune langue."""
    assert recoller_les_elisions("l\u2019 40 jours") == "l\u2019 40 jours"


def test_le_fichier_partage_est_bien_celui_du_depot():
    """Un seul fichier pour `mission` et pour `urim` — c'est tout l'intérêt.

    Le jour où quelqu'un en ajoutera un second « juste pour son contexte », les deux Bibles
    recommenceront à diverger sans que rien ne le signale."""
    assert SORTIE == Path("data/ls1910.json")
