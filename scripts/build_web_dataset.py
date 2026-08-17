"""Convertit la World English Bible brute en `data/web.json` — **le format du dépôt**.

    # 1. déposer la source (domaine public) :
    #    https://api.getbible.net/v2/web.json  →  data/web_raw.json
    # 2. python scripts/build_web_dataset.py

Sortie : `{ "John 3.16": "text", … }`, exactement ce que `web_dataset_path` attend et que
`JsonFileScriptureSource` sait lire — le même format que `data/ls1910.json`, à la langue près.

**Jumeau de `build_lsg_dataset.py`, avec une différence qui compte.** Côté français, les libellés
sont ramenés au vocabulaire d'`urim_seed_books` parce que `mission` et `urim` partagent le
fichier. Ici il n'y a rien à partager : Urim reste francophone (verrou D du chantier bilingue),
donc cette Bible n'a qu'un lecteur, `mission`. Les noms de livres sont **ceux de la source**, et
c'est délibéré : ce sont eux que le prompt du résolveur demande à l'IA de produire, et eux qui
servent de clé de recherche. Les changer ici casserait la carte sans rien dire.

**`data/web.json` se versionne**, comme `data/ls1910.json` et pour la même raison qu'on avait
fini par versionner celui-là : un fichier que le déploiement doit penser à construire est un
fichier qu'un déploiement oubliera, et l'oubli est **silencieux** — Mission retombe sur l'extrait
dev de huit versets et sert des cartes sans rien dire. Seule la source brute reste hors dépôt
(`data/*_raw.json` est déjà ignoré) : la garder stockerait deux fois la même Bible.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BRUT = Path("data/web_raw.json")
SORTIE = Path("data/web.json")

#: Les 66 livres du canon protestant, **tels que la World English Bible les nomme**. La liste
#: n'est pas décorative : elle fait échouer la construction si la source change de vocabulaire,
#: plutôt que de laisser passer un « Song of Songs » qui ne rencontrerait jamais le
#: « Song of Solomon » que le prompt fait produire à l'IA.
LIVRES: tuple[str, ...] = (
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy",
    "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
    "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
    "Jude", "Revelation",
)

#: Les écarts de nommage connus entre la source et le vocabulaire ci-dessus. Explicites plutôt
#: que rattrapés par une heuristique : deux cas se lisent, une heuristique se subit.
ALIAS = {
    "Song of Songs": "Song of Solomon",
    "Revelation of John": "Revelation",
    "Psalm": "Psalms",
}

#: Nombre de chapitres attendu pour le canon protestant — le seul contrôle qui puisse attraper
#: une source tronquée ou augmentée sans qu'on s'en aperçoive. Même garde que côté français.
CHAPITRES_ATTENDUS = 1189


def main() -> None:
    if not BRUT.exists():
        raise SystemExit(
            f"{BRUT} absent — deposer d'abord https://api.getbible.net/v2/web.json"
        )

    connus = set(LIVRES)
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
                # `.strip()` pour la même raison que côté français : la source laisse une espace
                # finale qui ne se voit pas a l'ecran et fausse toute comparaison de chaine.
                plat[f"{nom} {chapitre['chapter']}.{verset['verse']}"] = verset["text"].strip()

    if inconnus:
        raise SystemExit(f"livres non reconnus : {sorted(inconnus)}")
    if n_chapitres != CHAPITRES_ATTENDUS:
        raise SystemExit(f"{n_chapitres} chapitres, {CHAPITRES_ATTENDUS} attendus.")

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(plat, ensure_ascii=False, indent=0), encoding="utf-8")

    print(f"  {len(plat)} versets, {n_chapitres} chapitres, {len(donnees['books'])} livres")
    print(f"  -> {SORTIE}  ({SORTIE.stat().st_size // 1024} Ko)")
    print(f"\n  temoin  John 11.35 : « {plat['John 11.35']} »")
    print(f"  temoin  2 Corinthians 5.17 : « {plat['2 Corinthians 5.17'][:60]}… »")


if __name__ == "__main__":
    main()
