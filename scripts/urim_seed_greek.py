"""Le grec du Nouveau Testament — **lemmes et morphologie**, depuis MorphGNT/SBLGNT.

    python scripts/urim_seed_greek.py            # les 27 livres
    python scripts/urim_seed_greek.py --livre Lk

Source : `github.com/morphgnt/sblgnt`, le SBL Greek New Testament annoté (CC BY 4.0, la
mention de licence est portée en base sur chaque lemme). Même geste que `build_lsg_dataset` :
on télécharge, on vérifie, on écrit — **jamais de texte tapé de mémoire**.

## Pourquoi ces deux tables étaient vides

`urim_corpus_lemma` et `urim_corpus_token` existent au schéma depuis le premier jour et
n'avaient jamais reçu une ligne. Tant qu'elles l'étaient, « en savoir plus sur un mot » ne
pouvait rien vouloir dire : le pasteur qui clique sur `Ἀγαπήσεις` dans Luc 10:27 attend de
savoir que c'est un **futur de l'indicatif** — donc « tu aimeras », promesse ou constat, et
non l'impératif qu'on prêche d'ordinaire.

Un modèle aurait pu gloser cela de mémoire. C'est exactement ce qu'il ne faut pas : personne
ne relit une analyse grammaticale, on la croit, et l'erreur ressort en chaire.

## Ce que ce semis ne pose pas

**La glose.** MorphGNT ne porte aucune traduction, et les lexiques libres sont en anglais.
`lemma.gloss` reste donc `NULL` : le pasteur verra `ἀγαπάω` et sa forme, pas « aimer ». Mieux
vaut ce manque, visible, qu'une glose inventée qui aurait l'air d'une source.

**L'hébreu.** Autre source (Open Scriptures `morphhb`), autre format (XML par livre), autre
jeu de codes. Il vient ensuite, et l'AT reste sans original d'ici là.

## L'accrochage aux versets

Les jetons pendent à `urim_corpus_verse.id`, c'est-à-dire à la ligne **française** — il n'y a
qu'une version dans ce corpus. Ce n'est pas un détournement : c'est la lecture voulue par
`lemma.language`, *les mots de l'original derrière ce verset-ci*. Un verset introuvable est
compté et sauté ; la versification SBLGNT et celle de la Segond divergent sur quelques
endroits, et inventer un rattachement serait pire que le trou.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, insert, select

from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusLemmaModel,
    CorpusTokenModel,
    CorpusVerseModel,
)
from app.core.database import async_session_factory

BASE = "https://raw.githubusercontent.com/morphgnt/sblgnt/master"

#: Les 27 livres — **explicites**, comme `BOOKS`. Le nom de fichier et le code interne ne
#: suivent pas la même numérotation (Luc est `63-Lk-morphgnt.txt` et s'écrit `03` dans le
#: fichier), et une heuristique sur deux numérotations divergentes est une panne qui attend.
#:
#: `(code interne, nom de fichier, rang dans le canon du dépôt)`
LIVRES: tuple[tuple[str, str, int], ...] = (
    ("01", "61-Mt", 40), ("02", "62-Mk", 41), ("03", "63-Lk", 42), ("04", "64-Jn", 43),
    ("05", "65-Ac", 44), ("06", "66-Ro", 45), ("07", "67-1Co", 46), ("08", "68-2Co", 47),
    ("09", "69-Ga", 48), ("10", "70-Eph", 49), ("11", "71-Php", 50), ("12", "72-Col", 51),
    ("13", "73-1Th", 52), ("14", "74-2Th", 53), ("15", "75-1Ti", 54), ("16", "76-2Ti", 55),
    ("17", "77-Tit", 56), ("18", "78-Phm", 57), ("19", "79-Heb", 58), ("20", "80-Jas", 59),
    ("21", "81-1Pe", 60), ("22", "82-2Pe", 61), ("23", "83-1Jn", 62), ("24", "84-2Jn", 63),
    ("25", "85-3Jn", 64), ("26", "86-Jud", 65), ("27", "87-Re", 66),
)

CACHE = Path("data/morphgnt")
SOURCE = "MorphGNT/SBLGNT (CC BY 4.0)"


def _telecharger(fichier: str) -> list[str]:
    """Le fichier brut, mis en cache — relancer le semis ne retélécharge pas 27 fois."""
    CACHE.mkdir(parents=True, exist_ok=True)
    local = CACHE / f"{fichier}-morphgnt.txt"
    if not local.exists():
        with urllib.request.urlopen(f"{BASE}/{fichier}-morphgnt.txt", timeout=60) as reponse:
            local.write_bytes(reponse.read())
    return local.read_text(encoding="utf-8").splitlines()


def _analyser(ligne: str) -> tuple[int, int, str, str, str, str] | None:
    """Une ligne MorphGNT → `(chapitre, verset, nature, morphologie, surface, lemme)`.

    Format : `BBCCVV nature morphologie texte mot normalisé lemme`. Le champ « texte » porte
    la ponctuation collée (`εἶπεν·`) ; c'est lui qu'on garde comme surface, parce que c'est ce
    que le pasteur voit dans son édition."""
    champs = ligne.split()
    if len(champs) < 7 or len(champs[0]) != 6:
        return None
    localisateur = champs[0]
    try:
        chapitre, verset = int(localisateur[2:4]), int(localisateur[4:6])
    except ValueError:
        return None
    return chapitre, verset, champs[1], champs[2], champs[3], champs[6]


async def semer(livre_voulu: str | None, purge: bool) -> None:
    async with async_session_factory() as s:
        if purge:
            await s.execute(delete(CorpusTokenModel))
            await s.execute(delete(CorpusLemmaModel))
            await s.commit()
            print("  purge effectuee")

        # `(book_id, chapitre, verset) -> verse_id`. Une seule version au corpus, donc une
        # seule ligne par référence — la clé unique `verse_unique_ref` le garantit.
        versets: dict[tuple[int, int, int], int] = {
            (b, c, v): i
            for i, b, c, v in await s.execute(
                select(
                    CorpusVerseModel.id, CorpusVerseModel.book_id,
                    CorpusVerseModel.chapter, CorpusVerseModel.verse,
                )
            )
        }

        # Les lemmes sont **dédupliqués sur toute la langue**, pas par livre : `ἀγαπάω` est le
        # même mot dans Luc et dans Jean, et le pasteur qui clique dessus doit tomber sur une
        # seule entrée.
        connus: dict[str, int] = {
            forme: identifiant
            for identifiant, forme in await s.execute(
                select(CorpusLemmaModel.id, CorpusLemmaModel.lemma).where(
                    CorpusLemmaModel.language == "grc"
                )
            )
        }

        # Les livres **déjà semés** — un essai sur Luc avait fait échouer le passage complet
        # sur la clé primaire `(verse_id, position)`. Un semis qui n'est pas reprenable oblige
        # à tout purger pour rattraper un livre, ce qui est le meilleur moyen de ne pas le
        # rattraper.
        #
        # ⚠️ On compare le **nombre**, pas l'existence. Le passage qui a échoué avait commis
        # un lot avant de tomber : Matthieu et Marc avaient des jetons sans être finis, et un
        # garde qui teste « ce livre a-t-il des jetons ? » les aurait déclarés faits pour
        # toujours. Un semis à moitié est plus dangereux qu'un semis absent, parce qu'il ne
        # se signale pas.
        faits = {
            rang: nombre
            for rang, nombre in await s.execute(
                select(CorpusVerseModel.book_id, func.count())
                .join(CorpusTokenModel, CorpusTokenModel.verse_id == CorpusVerseModel.id)
                .group_by(CorpusVerseModel.book_id)
            )
        }

        jetons: list[dict] = []
        orphelins = 0

        for code, fichier, rang in LIVRES:
            if livre_voulu and not fichier.endswith(livre_voulu):
                continue
            brut = _telecharger(fichier)
            attendu = sum(1 for ligne in brut if ligne.startswith(code))
            if faits.get(rang, 0) == attendu:
                print(f"  {fichier:8} deja seme ({attendu} mots)")
                continue
            if faits.get(rang, 0):
                print(f"  {fichier:8} INCOMPLET : {faits[rang]}/{attendu} — purge du livre")
                await s.execute(
                    delete(CorpusTokenModel).where(
                        CorpusTokenModel.verse_id.in_(
                            select(CorpusVerseModel.id).where(
                                CorpusVerseModel.book_id == rang
                            )
                        )
                    )
                )
                await s.commit()
            lignes = [
                lu for ligne in brut
                if ligne.startswith(code) and (lu := _analyser(ligne)) is not None
            ]
            nouveaux = sorted({lemme for *_, lemme in lignes} - set(connus))
            if nouveaux:
                rendus = await s.execute(
                    insert(CorpusLemmaModel).returning(
                        CorpusLemmaModel.id, CorpusLemmaModel.lemma
                    ),
                    [
                        # `gloss` reste NULL — voir l'en-tête. Un manque visible vaut mieux
                        # qu'une traduction inventée qui aurait l'air d'une source.
                        {"language": "grc", "lemma": forme, "strong_code": None, "gloss": None}
                        for forme in nouveaux
                    ],
                )
                connus.update({forme: identifiant for identifiant, forme in rendus})

            position: dict[tuple[int, int], int] = {}
            for chapitre, verset, nature, morphologie, surface, lemme in lignes:
                cle = versets.get((rang, chapitre, verset))
                if cle is None:
                    # Versification divergente : compté, jamais rattaché au petit bonheur.
                    orphelins += 1
                    continue
                position[(chapitre, verset)] = position.get((chapitre, verset), 0) + 1
                jetons.append({
                    "verse_id": cle,
                    "position": position[(chapitre, verset)],
                    "surface": surface[:80],
                    "lemma_id": connus[lemme],
                    # Nature et morphologie voyagent **ensemble** : `V-` sans `2FAI-S--` ne
                    # dit pas le mode, et `2FAI-S--` sans `V-` ne dit pas que c'est un verbe.
                    "morph_code": f"{nature}|{morphologie}"[:40],
                })
            print(f"  {fichier:8} {len(lignes):>6} mots")

            if len(jetons) >= 20000:
                await s.execute(insert(CorpusTokenModel), jetons)
                await s.commit()
                jetons = []

        if jetons:
            await s.execute(insert(CorpusTokenModel), jetons)
        await s.commit()

        total = await s.scalar(select(CorpusTokenModel.verse_id).limit(1))
        print(f"\n  {len(connus)} lemmes grecs")
        if orphelins:
            print(f"  {orphelins} mots sans verset correspondant (versification divergente)")
        if total is None:
            print("  ⚠ aucun jeton ecrit")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--livre", help="suffixe du fichier, ex. Lk, Ro, 1Co")
    analyseur.add_argument("--purge", action="store_true")
    arguments = analyseur.parse_args()
    asyncio.run(semer(arguments.livre, arguments.purge))


if __name__ == "__main__":
    main()
