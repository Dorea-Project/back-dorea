"""L'hébreu de l'Ancien Testament — **lemmes et morphologie**, depuis Open Scriptures.

    python scripts/urim_seed_hebrew.py             # les 39 livres
    python scripts/urim_seed_hebrew.py --livre Gen

Deux sources, toutes deux libres, et il en faut **deux** :

* `openscriptures/morphhb` (WLC) donne le texte pointé, la morphologie OSHM et un **numéro**
  de Strong par mot ;
* `openscriptures/HebrewLexicon` donne le mot hébreu derrière ce numéro.

Sans la seconde, `urim_corpus_lemma.lemma` porterait « 7225 » — et le pasteur qui clique sur
`בְּרֵאשִׁית` verrait un nombre. Un lemme qui ne se lit pas ne sert à rien.

## Un jeton par mot écrit, pas par morphème

L'hébreu colle : `וְהָאָרֶץ` est une conjonction, un article et un nom en un seul mot. Le
projet les sépare par `/` dans le lemme comme dans la morphologie, mais **le texte, lui, ne les
sépare pas** — et c'est le texte que le pasteur lit. On garde donc un jeton par `<w>`, sa
surface débarrassée des barres, et la morphologie entière : c'est le décodeur qui déplie
« conjonction · article défini · nom commun ».

Le lemme retenu est celui du **dernier** morphème, qui porte le mot. `c/d/776` → 776, la terre.
Les préfixes sont dans la morphologie, où ils se lisent.

## Ce que ce semis ne pose pas, et pourquoi

**La glose.** Le lexique la donne en anglais. Même règle que pour le grec : `gloss` reste
`NULL` plutôt que de servir au pasteur une définition qu'il croirait française. Un manque
visible vaut mieux qu'une source qui n'en est pas une.

**La translittération.** Le lexique la porte (« rechit »), et elle serait plus utile en hébreu
qu'en grec — les lettres ne se devinent pas. Mais `urim_corpus_lemma` n'a pas de colonne pour
elle, et l'ajouter est une migration : c'est un chantier, pas un effet de bord de celui-ci.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, insert, select

from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusLemmaModel,
    CorpusTokenModel,
    CorpusVerseModel,
)
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS

WLC = "https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc"
LEXIQUE = (
    "https://raw.githubusercontent.com/openscriptures/HebrewLexicon/master/HebrewStrong.xml"
)
CACHE = Path("data/morphhb")

#: L'espace de noms OSIS, porté par chaque balise du fichier.
OSIS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"

#: Les 39 livres, par leur code OSIS — **explicites**, comme partout ailleurs dans ce dépôt.
#: Le rang est celui du canon du dépôt (`BOOKS`), et il ne se déduit d'aucun numéro du fichier.
LIVRES: tuple[tuple[str, int], ...] = tuple(
    (osis, rang) for rang, osis, testament, *_ in BOOKS if testament == "AT"
)


def _telecharger(url: str, nom: str) -> bytes:
    """Le fichier brut, mis en cache — relancer le semis ne retélécharge pas 40 Mo."""
    CACHE.mkdir(parents=True, exist_ok=True)
    local = CACHE / nom
    if not local.exists():
        with urllib.request.urlopen(url, timeout=120) as reponse:
            local.write_bytes(reponse.read())
    return local.read_bytes()


def _lexique() -> dict[str, str]:
    """`H7225` → `רֵאשִׁית`. Le numéro seul ne se lit pas."""
    racine = ElementTree.fromstring(_telecharger(LEXIQUE, "HebrewStrong.xml"))
    mots: dict[str, str] = {}
    for entree in racine.iter():
        if not entree.tag.endswith("entry"):
            continue
        code = entree.get("id")
        mot = next(
            (
                enfant.text
                for enfant in entree
                if enfant.tag.endswith("w") and enfant.get("src") is None and enfant.text
            ),
            None,
        )
        if code and mot:
            mots[code] = mot.strip()
    return mots


def _code_strong(lemme: str | None) -> str | None:
    """`c/d/776` → `H776`, `1254 a` → `H1254`.

    Le **dernier** segment porte le mot ; ce qui précède est un préfixe collé, et la
    morphologie le dit déjà. Le suffixe littéral (« 1254 a ») distingue des homonymes que le
    lexique range sous un seul numéro."""
    if not lemme:
        return None
    chiffres = re.search(r"(\d+)", lemme.split("/")[-1])
    return f"H{chiffres.group(1)}" if chiffres else None


def _versets(octets: bytes, rang: int) -> list[tuple[int, int, list[tuple[str, str, str]]]]:
    """Le fichier d'un livre → `[(chapitre, verset, [(surface, code Strong, morphologie)])]`."""
    racine = ElementTree.fromstring(octets)
    lus: list[tuple[int, int, list[tuple[str, str, str]]]] = []
    for verset in racine.iter(f"{OSIS}verse"):
        localisateur = (verset.get("osisID") or "").split(".")
        if len(localisateur) != 3:
            continue
        try:
            chapitre, numero = int(localisateur[1]), int(localisateur[2])
        except ValueError:
            continue
        mots = [
            # ⚠️ Les barres disparaissent de la **surface** : elles marquent les morphèmes que
            # le projet a séparés, pas le texte que le pasteur lit dans sa Bible.
            ((mot.text or "").replace("/", "").strip(), _code_strong(mot.get("lemma")) or "",
             mot.get("morph") or "")
            for mot in verset.iter(f"{OSIS}w")
            if (mot.text or "").strip()
        ]
        if mots:
            lus.append((chapitre, numero, mots))
    return lus


async def semer(livre_voulu: str | None, purge: bool) -> None:
    strongs = _lexique()
    print(f"  lexique : {len(strongs)} entrees hebraiques")

    async with async_session_factory() as s:
        if purge:
            await s.execute(
                delete(CorpusTokenModel).where(
                    CorpusTokenModel.lemma_id.in_(
                        select(CorpusLemmaModel.id).where(CorpusLemmaModel.language == "hbo")
                    )
                )
            )
            await s.execute(delete(CorpusLemmaModel).where(CorpusLemmaModel.language == "hbo"))
            await s.commit()
            print("  purge effectuee")

        versets: dict[tuple[int, int, int], int] = {
            (b, c, v): i
            for i, b, c, v in await s.execute(
                select(
                    CorpusVerseModel.id, CorpusVerseModel.book_id,
                    CorpusVerseModel.chapter, CorpusVerseModel.verse,
                )
            )
        }
        connus: dict[str, int] = {
            code: identifiant
            for identifiant, code in await s.execute(
                select(CorpusLemmaModel.id, CorpusLemmaModel.strong_code).where(
                    CorpusLemmaModel.language == "hbo"
                )
            )
        }
        # Le **nombre**, pas l'existence — un livre à moitié semé ne doit pas se déclarer fait.
        faits = {
            rang: nombre
            for rang, nombre in await s.execute(
                select(CorpusVerseModel.book_id, func.count())
                .join(CorpusTokenModel, CorpusTokenModel.verse_id == CorpusVerseModel.id)
                .group_by(CorpusVerseModel.book_id)
            )
        }

        orphelins = 0
        for osis, rang in LIVRES:
            if livre_voulu and osis != livre_voulu:
                continue
            lus = _versets(_telecharger(f"{WLC}/{osis}.xml", f"{osis}.xml"), rang)
            attendu = sum(len(mots) for _, _, mots in lus)
            if faits.get(rang, 0) == attendu:
                print(f"  {osis:6} deja seme ({attendu} mots)")
                continue
            if faits.get(rang, 0):
                print(f"  {osis:6} INCOMPLET : {faits[rang]}/{attendu} — purge du livre")
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

            nouveaux = sorted(
                {code for _, _, mots in lus for _, code, _ in mots if code and code in strongs}
                - set(connus)
            )
            if nouveaux:
                rendus = await s.execute(
                    insert(CorpusLemmaModel).returning(
                        CorpusLemmaModel.id, CorpusLemmaModel.strong_code
                    ),
                    [
                        {
                            "language": "hbo", "lemma": strongs[code],
                            "strong_code": code, "gloss": None,
                        }
                        for code in nouveaux
                    ],
                )
                connus.update({code: identifiant for identifiant, code in rendus})

            jetons: list[dict] = []
            for chapitre, numero, mots in lus:
                cle = versets.get((rang, chapitre, numero))
                if cle is None:
                    orphelins += len(mots)
                    continue
                for position, (surface, code, morph) in enumerate(mots, start=1):
                    jetons.append({
                        "verse_id": cle, "position": position, "surface": surface[:80],
                        "lemma_id": connus.get(code), "morph_code": (morph or "")[:40],
                    })
            if jetons:
                await s.execute(insert(CorpusTokenModel), jetons)
                await s.commit()
            print(f"  {osis:6} {len(jetons):>6} mots")

        total = await s.scalar(
            select(func.count()).select_from(CorpusLemmaModel).where(
                CorpusLemmaModel.language == "hbo"
            )
        )
        print(f"\n  {total} lemmes hebreux")
        if orphelins:
            print(f"  {orphelins} mots sans verset correspondant (versification divergente)")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--livre", help="code OSIS, ex. Gen, Ps, Isa")
    analyseur.add_argument("--purge", action="store_true")
    arguments = analyseur.parse_args()
    asyncio.run(semer(arguments.livre, arguments.purge))


if __name__ == "__main__":
    main()
