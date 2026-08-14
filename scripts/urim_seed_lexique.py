"""Semer le lexique — **l'acquisition, sans un seul appel de modèle**.

Remplit `urim_corpus_lemma.gloss_source` (l'entrée anglaise, mot pour mot),
`gloss_source_ref` et `strong_code` depuis **TBESG** (STEPBible, CC BY 4.0).

La traduction française est un **second geste**, dans un autre script : ce qui est acquis et ce
qui est produit ne se mélangent pas, et l'un peut être rejoué sans refaire l'autre.

## Ce que ce script répare au passage

Les 5 461 lemmes grecs du corpus **n'avaient aucun code Strong** — MorphGNT n'en fournit pas.
Le pont vers n'importe quel lexique n'existait donc qu'à moitié (côté hébreu). TBESG portant
à la fois le lemme et le Strong, la jointure par lemme le reconstruit.

## Ce qu'il ne fait pas

**Il n'invente aucune correspondance.** Un lemme sans entrée reste sans glose : les noms propres
dont l'orthographe diffère entre éditions (`Καφαρναούμ`, `Μαθθαῖος`) ne sont pas rapprochés de
force — et ce sont justement les mots dont personne n'attend une définition.

Attribution requise par la licence : **STEP Bible** — https://www.STEPBible.org

Usage :
    python scripts/urim_seed_lexique.py data/stepbible/TBESG.txt [--ecrire]

Sans `--ecrire`, il **compte et n'écrit rien**.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import Settings  # noqa: E402

SOURCE = "TBESG (STEPBible, CC BY 4.0)"


def plier(mot: str) -> str:
    """Casse et accents repliés — la seule façon de rapprocher deux éditions du grec."""
    decompose = unicodedata.normalize("NFD", (mot or "").strip().casefold())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def lire(fichier: pathlib.Path) -> dict[str, tuple[str, str]]:
    """`lemme plié → (code Strong, glose brève)`.

    Le fichier porte plusieurs formes par entrée (`α, Ἀλφα`) : chacune ouvre une clé. **La
    première gagne** — les entrées sont ordonnées par numéro Strong, donc la plus ancienne
    acception l'emporte sur ses homonymes tardifs.

    ⚠️ **On retient la colonne 6 (glose brève), pas la 7 (entrée complète).** La seconde porte
    du HTML, des références croisées et des abréviations de lexicographe — intraduisible en une
    ligne, et illisible pour qui n'est pas bibliste."""
    entrees: dict[str, tuple[str, str]] = {}
    for ligne in fichier.read_text(encoding="utf-8-sig").splitlines():
        colonnes = ligne.split("\t")
        if len(colonnes) < 7 or not colonnes[0].startswith("G"):
            continue
        strong, formes, glose = colonnes[0], colonnes[3], colonnes[6].strip()
        if not glose:
            continue
        for forme in formes.split(","):
            cle = plier(forme)
            if cle and cle not in entrees:
                entrees[cle] = (strong, glose)
    return entrees


async def principal(fichier: pathlib.Path, ecrire: bool) -> None:
    entrees = lire(fichier)
    reglages = Settings()
    moteur = create_async_engine(str(reglages.database_url))

    async with moteur.begin() as cx:
        nos = (await cx.execute(text(
            "SELECT id, lemma FROM urim_corpus_lemma WHERE language = 'grc'"
        ))).all()

        apparies = 0
        for identifiant, lemme in nos:
            trouve = entrees.get(plier(lemme))
            if trouve is None:
                continue
            apparies += 1
            if not ecrire:
                continue
            strong, glose = trouve
            await cx.execute(
                text(
                    "UPDATE urim_corpus_lemma SET gloss_source = :g,"
                    " gloss_source_ref = :ref, strong_code = COALESCE(strong_code, :s)"
                    " WHERE id = :id"
                ),
                {"g": glose, "ref": SOURCE, "s": strong, "id": identifiant},
            )
    await moteur.dispose()

    print(f"entrées lues      : {len(entrees)}")
    print(f"lemmes grecs      : {len(nos)}")
    print(f"appariés          : {apparies} ({100 * apparies / max(len(nos), 1):.1f} %)")
    print("écrit             :", "oui" if ecrire else "NON (essai à blanc)")


if __name__ == "__main__":
    chemin = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/stepbible/TBESG.txt")
    asyncio.run(principal(chemin, "--ecrire" in sys.argv))
