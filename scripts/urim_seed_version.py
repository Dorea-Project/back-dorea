"""Semer une traduction française du domaine public — **pour que deux textes puissent se heurter**.

    python scripts/urim_seed_version.py --version darby
    python scripts/urim_seed_version.py --version martin
    python scripts/urim_seed_version.py --version darby --purge

Source : `api.getbible.net/v2` — la même API qui a fourni la Segond 1910.

## Pourquoi plusieurs versions, et pourquoi ce n'est pas un réglage

Un menu « choisissez votre traduction » demanderait au pasteur de configurer. Urim ne fait cela
nulle part : il **signale**. Là où deux traducteurs sérieux rendent le même verset autrement,
il y a quelque chose à dire — et c'est le produit qui doit le dire, au moment où ça compte.

Les trois témoins ne sont donc pas trois préférences, ce sont trois angles :

    Segond 1910   équilibrée, la norme des assemblées   · proche du Texte Reçu
    Darby         formelle, serre l'original            · TEXTE CRITIQUE
    Martin 1744   ancienne, tradition genevoise         · TEXTE REÇU

Darby contre les deux autres fait remonter les divergences Texte Reçu / texte critique **toutes
seules**, sans apparat, sans modèle, sans rien inventer. C'est la seule approche honnête des
variantes dont ce produit dispose : on n'affirme pas qu'un manuscrit porte ceci — on montre que
deux traducteurs ont lu autrement, et le pasteur vérifie des deux yeux.

## Ce que ce semis vérifie, et qui est le vrai travail

**La versification.** Les traductions ne numérotent pas pareil. Un écart silencieux ferait
afficher le mauvais verset sous la bonne référence — pire que de ne rien afficher. Le script
compare livre par livre contre la Segond et imprime chaque divergence.

Il ne les corrige pas : `urim_corpus_versification_map` existe pour les déclarer, et remplir une
table de correspondances est une décision, pas un effet de bord d'un téléchargement.

⚠️ **Aucun appel de modèle.** Le texte biblique ne vient jamais d'une machine — il vient des
traducteurs. C'est la garantie que le produit tient partout ailleurs : le modèle nomme des
références, la Bible donne le texte.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, insert, select

from app.contexts.urim.engine.normalizer import normalize as normalise
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.database import async_session_factory
from scripts.build_lsg_dataset import ALIAS, CHAPITRES_ATTENDUS
from scripts.urim_seed_books import BOOKS

#: Le même espace de nommage que `seed_urim_corpus.py` — sans quoi deux semis produiraient
#: deux identifiants pour la même chose.
NS = uuid5(NAMESPACE_URL, "https://dorea.app/urim/corpus")


@dataclass(frozen=True)
class Version:
    """⚠️ **Liste fermée, comme les loci et les traditions.**

    Semer « n'importe quelle version que la source propose » ferait entrer dans le corpus des
    traductions dont personne n'a vérifié la licence ni la philosophie. Chacune est ici nommée,
    avec ce qui justifie sa présence."""

    source: str          # le code chez getbible
    code: str            # le code du dépôt
    label: str
    genre: str           # 'formelle' | 'dynamique'
    pourquoi: str

    @property
    def id(self) -> UUID:
        return uuid5(NS, f"version:{self.code}")


#: `licence_coherente` impose, pour le domaine public : hors ligne autorisé, jamais plafonné.
#: Ce qui ne coûte rien à servir ne se compte pas — et le repli ne peut pas céder.
CATALOGUE = {
    "darby": Version(
        "darby", "DARBY", "Darby (français)", "formelle",
        "serre l'original sur un texte critique — le contraste utile a la Segond",
    ),
    "martin": Version(
        "martin", "MARTIN", "Martin (1744)", "formelle",
        "temoin du Texte Recu : sa divergence d'avec Darby EST le signal de variante",
    ),
}


def _telecharger(source: str) -> dict:
    """~10 Mo par version, mis en cache : resemer ne retélécharge pas."""
    cache = Path(f"data/{source}_raw.json")
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        requete = urllib.request.Request(
            f"https://api.getbible.net/v2/{source}.json",
            headers={"User-Agent": "Mozilla/5.0 (Dorea corpus seed)"},
        )
        with urllib.request.urlopen(requete, timeout=300) as reponse:
            cache.write_bytes(reponse.read())
    return json.loads(cache.read_text(encoding="utf-8"))


async def semer(version: Version, purge: bool) -> None:
    donnees = _telecharger(version.source)
    connus = {label for _, _, _, label, _ in BOOKS}
    rangs = {label: rang for rang, _osis, _t, label, _a in BOOKS}
    par_rang = {rang: label for rang, _osis, _t, label, _a in BOOKS}

    lignes: list[dict] = []
    inconnus: set[str] = set()
    chapitres = 0
    compte: dict[str, int] = {}

    async with async_session_factory() as s:
        if purge:
            await s.execute(
                delete(CorpusVerseModel).where(CorpusVerseModel.version_id == version.id)
            )
            await s.execute(
                delete(CorpusVersionModel).where(CorpusVersionModel.id == version.id)
            )
            await s.commit()
            print(f"  {version.code} effacee\n")

        if await s.get(CorpusVersionModel, version.id):
            print(f"  {version.code} deja semee — --purge pour resemer.")
            return

        for livre in donnees["books"]:
            nom = ALIAS.get(livre["name"], livre["name"])
            if nom not in connus:
                inconnus.add(nom)
                continue
            for chapitre in livre["chapters"]:
                chapitres += 1
                for verset in chapitre["verses"]:
                    corps = verset["text"].strip()
                    lignes.append({
                        "version_id": version.id, "book_id": rangs[nom],
                        "chapter": int(chapitre["chapter"]), "verse": int(verset["verse"]),
                        "body": corps, "body_norm": normalise(corps),
                    })
                    compte[nom] = compte.get(nom, 0) + 1

        if inconnus:
            raise SystemExit(f"  livres non reconnus : {sorted(inconnus)}")
        if chapitres != CHAPITRES_ATTENDUS:
            raise SystemExit(f"  {chapitres} chapitres, {CHAPITRES_ATTENDUS} attendus.")

        s.add(CorpusVersionModel(
            id=version.id, code=version.code, language="fr", label=version.label,
            translation_kind=version.genre, license_kind="domaine_public", provider=None,
            offline_allowed=True, metered=False, versification="standard",
        ))
        # ⚠️ La version doit exister **avant** les versets : l'insertion en masse est un ordre
        # SQL direct, elle ne déclenche pas l'écriture de l'objet ORM encore en attente, et la
        # clé étrangère tombe sur 31 000 lignes à la fois.
        await s.flush()
        await s.execute(insert(CorpusVerseModel), lignes)
        await s.commit()
        print(f"  {len(lignes)} versets, {chapitres} chapitres — {version.code} semee\n")

        segond = {
            par_rang[rang]: n for rang, n in await s.execute(
                select(CorpusVerseModel.book_id, func.count())
                .join(
                    CorpusVersionModel,
                    CorpusVersionModel.id == CorpusVerseModel.version_id,
                )
                .where(CorpusVersionModel.code == "LSG")
                .group_by(CorpusVerseModel.book_id)
            )
        }

    ecarts = [
        (nom, segond.get(nom, 0), compte[nom])
        for nom in compte
        if segond.get(nom, 0) != compte[nom]
    ]
    if not ecarts:
        print("  versification identique a la Segond sur les 66 livres.")
        return

    print(f"  {len(ecarts)} livres numerotent differemment de la Segond :\n")
    for nom, n_lsg, n_autre in sorted(ecarts, key=lambda e: abs(e[1] - e[2]), reverse=True):
        print(f"    {nom:<24} Segond {n_lsg:>5}   {version.code:<7}{n_autre:>5}"
              f"   ecart {n_autre - n_lsg:+}")
    print(
        "\n  ⚠️ Ces ecarts ne sont PAS corriges ici. `urim_corpus_versification_map` existe\n"
        "     pour les declarer, et une table de correspondances est une decision."
    )


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--version", required=True, choices=sorted(CATALOGUE))
    analyseur.add_argument("--purge", action="store_true", help="effacer et resemer")
    arguments = analyseur.parse_args()
    asyncio.run(semer(CATALOGUE[arguments.version], arguments.purge))


if __name__ == "__main__":
    main()
