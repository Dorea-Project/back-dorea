"""Convertit la LSG 1910 brute en `data/ls1910.json` — **le format du dépôt**.

    python scripts/build_lsg_dataset.py

Source : `api.getbible.net/v2/ls1910.json` (Louis Segond 1910, **domaine public**), déposée
en `data/ls1910_raw.json`. Sortie : `{ "Jean 3.16": "texte", … }`, exactement ce que
`lsg_dataset_path` attend et que `JsonFileScriptureSource` sait lire.

**Un seul fichier pour tout le dépôt.** `mission` (carte d'invitation, M9-1) et `urim`
(corpus de préparation) lisent la même Bible. Deux extraits tapés à la main dans deux
contextes, c'était deux Bibles qui pouvaient diverger — et elles divergeaient : `mission`
tenait 8 versets, `urim` en avait 72 autres.

Les libellés de livres sont ramenés au **vocabulaire du dépôt** (`urim_seed_books.BOOKS`),
pour qu'il n'existe qu'une seule façon de nommer un livre d'un bout à l'autre du système.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.urim_seed_books import BOOKS

BRUT = Path("data/ls1910_raw.json")
SORTIE = Path("data/ls1910.json")

#: 🔴 **L'elision cassee par une espace fine — trente versets, et deux degats distincts.**
#:
#: La source ecrit « l'<U+2009>alliance », « qu'<U+2009>ils », « J'<U+2009>augmenterai » : une
#: **espace fine** (U+2009) s'est glissee entre l'apostrophe et la suite du mot. En francais, une
#: apostrophe n'est jamais suivie d'une espace — les trente cas ont ete relus un par un, et aucun
#: n'est un guillemet fermant.
#:
#: **Ce que ca casse, et pourquoi ce n'est pas cosmetique :**
#:
#: 1. **A l'ecran.** `mission` sert ce fichier tel quel sur la carte d'invitation : un chercheur
#:    qui n'est pas de l'eglise lit « le sang de l'<U+2009>alliance ». C'est le premier texte
#:    biblique que Dorea met sous les yeux de quelqu'un du dehors.
#: 2. **A la recherche.** Le normaliseur partage **colle** l'elision au mot suivant pour que
#:    « lamour » rencontre « l'amour » (S21) ; ici il n'a rien a quoi la coller, et rend
#:    « l alliance ». Un pasteur qui tape « lalliance » ne rencontre alors **jamais**
#:    Matthieu 26:28.
#:
#: On recolle donc a la **construction du fichier**, et pas dans le normaliseur : le texte
#: affiche est faux avant d'etre mal normalise, et un normaliseur ne repare pas ce qu'il lit.
#:
#: Les apostrophes sont ecrites en echappement et reprennent **exactement** celles du
#: normaliseur partage : sur un clavier, ces glyphes sont indiscernables, et une relecture ne
#: verrait pas qu'il en manque un.
_ESPACE_APRES_ELISION = re.compile(
    "(?<=["
    "'"          # apostrophe droite — celle des claviers
    "\u2019"    # apostrophe typographique — celle des traitements de texte
    "\u02bc"    # lettre modificatrice, frequente dans les corpus importes
    "\u02bb"    # sa jumelle tournee
    "`])"        # accent grave, tape par erreur a la place de l'apostrophe
    # Une lettre derriere, et rien d'autre : c'est l'appariement apostrophe -> lettre qui
    # decide. Sans lui, « dit : Voici » serait soude en « dit :Voici ».
    r"\s+(?=[^\W\d_])"
)


def recoller_les_elisions(texte: str) -> str:
    """Rend au mot l'élision que la source lui avait détachée."""
    return _ESPACE_APRES_ELISION.sub("", texte)


#: Les deux seuls écarts de nommage entre la source et le dépôt. Explicites plutôt que
#: rattrapés par une heuristique : deux cas se lisent, une heuristique se subit.
ALIAS = {
    "Actes des Apôtres": "Actes",
    "Cantique des Cantiques": "Cantique des cantiques",
}

#: Nombre de chapitres attendu pour le canon protestant — le seul contrôle qui puisse
#: attraper une source tronquée ou augmentée sans qu'on s'en aperçoive.
CHAPITRES_ATTENDUS = 1189


def main() -> None:
    if not BRUT.exists():
        raise SystemExit(f"{BRUT} absent — telecharger d'abord la source LSG 1910.")

    connus = {label for _, _, _, label, _ in BOOKS}
    donnees = json.loads(BRUT.read_text(encoding="utf-8"))

    plat: dict[str, str] = {}
    inconnus: set[str] = set()
    n_chapitres = 0

    for livre in donnees["books"]:
        nom = ALIAS.get(livre["name"], livre["name"])
        if nom not in connus:
            inconnus.add(nom)
            continue
        for chapitre in livre["chapters"]:
            n_chapitres += 1
            for verset in chapitre["verses"]:
                # `.strip()` : la source laisse une espace finale sur presque chaque
                # verset. Elle ne se voit pas a l'ecran et fausse toute comparaison de
                # chaine — dont le controle de citation (`citation_check`, S4).
                plat[f"{nom} {chapitre['chapter']}.{verset['verse']}"] = recoller_les_elisions(
                    verset["text"].strip()
                )

    if inconnus:
        raise SystemExit(f"livres non reconnus : {sorted(inconnus)}")
    if n_chapitres != CHAPITRES_ATTENDUS:
        raise SystemExit(f"{n_chapitres} chapitres, {CHAPITRES_ATTENDUS} attendus.")

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(plat, ensure_ascii=False, indent=0), encoding="utf-8")

    print(f"  {len(plat)} versets, {n_chapitres} chapitres, {len(donnees['books'])} livres")
    print(f"  -> {SORTIE}  ({SORTIE.stat().st_size // 1024} Ko)")
    print(f"\n  temoin  Jean 11.35 : « {plat['Jean 11.35']} »")
    print(f"  temoin  2 Corinthiens 5.17 : « {plat['2 Corinthiens 5.17'][:60]}… »")


if __name__ == "__main__":
    main()
