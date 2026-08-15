"""Semis du corpus Urim — livres de référence + démonstration curée.

    python scripts/seed_urim_corpus.py           # semer (idempotent)
    python scripts/seed_urim_corpus.py --purge   # effacer le semis puis semer

Deux natures de données, volontairement distinctes :

* **le texte** — la LSG 1910 **entière** (31 170 versets), lue depuis `lsg_dataset_path`,
  le même fichier que le contexte `mission`. Aucun extrait tapé à la main : un corpus
  partiel ne sait pas dire « ce verset n'existe pas », il sait seulement dire « je ne
  l'ai pas » — et il l'a dit à la place de l'autre, ce qui a coûté une séance entière ;
* **la curation** (péricopes, pesées, mises en garde) — de démonstration pour l'instant,
  elle porte `reviewed_by = 'semis-demo'` de bout en bout : un semis n'est pas une
  relecture, et `reviewed_by NOT NULL` existe pour empêcher exactement cette confusion.

Les identifiants sont **déterministes** (`uuid5`) : re-semer ne casse aucune
préparation qui référencerait déjà une péricope.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, insert, select

from app.contexts.urim.engine.normalizer import normalize as normalise
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusBookModel,
    CorpusBookNameModel,
    CorpusContextNoteModel,
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusHomileticFeasibilityModel,
    CorpusIdfModel,
    CorpusLanguageModel,
    CorpusPericopeModel,
    CorpusTextualVariantModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.config import get_settings
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS
from scripts.urim_seed_curation import (
    BEARINGS,
    CAVEATS,
    CONTEXT_NOTES,
    FEASIBILITY,
    LEXIQUE_FR,
    PERICOPES,
    TEXTUAL_VARIANTS,
)


def charger_lsg() -> dict[str, str]:
    """La Bible complète, depuis `lsg_dataset_path` — jamais depuis du texte en dur.

    Le fichier est produit par `scripts/build_lsg_dataset.py` et **partagé** avec le
    contexte `mission`. S'il manque, on refuse de semer : semer un extrait donnerait un
    corpus qui a l'air de marcher et qui ment sur ce qu'il ne contient pas."""
    chemin = get_settings().lsg_dataset_path
    if not chemin or not Path(chemin).is_file():
        raise SystemExit(
            "LSG_DATASET_PATH absent ou introuvable.\n"
            "  1) python scripts/build_lsg_dataset.py\n"
            "  2) LSG_DATASET_PATH=data/ls1910.json dans .env"
        )
    return json.loads(Path(chemin).read_text(encoding="utf-8"))

#: Espace de nommage du semis — fixe, pour que `uuid5` rende toujours le même id.
NS = uuid5(NAMESPACE_URL, "https://dorea.app/urim/corpus")

#: Louis Segond 1910 — domaine public, donc jamais plafonnée (`licence_coherente`).
LSG_ID = uuid5(NS, "version:LSG")

REVIEWER = "semis-demo"
REVIEWED_AT = datetime(2026, 8, 6, tzinfo=UTC)

# ⚠️ `normalise` **est** le normaliseur du moteur (`engine.normalizer.normalize`), importé
# tel quel et non réécrit. S21 en comptait trois consommateurs — l'étage 1, la conviction,
# le détecteur d'entrée ; le semis est le quatrième, et le plus facile à oublier.
#
# La divergence qu'on évite ici n'est pas théorique : le moteur **supprime** l'apostrophe
# pour coller l'élision (« l'amour » → `lamour`), là où une normalisation naïve la
# remplacerait par une espace (`l amour`). Un pasteur tapant « lamour » n'aurait alors
# rencontré aucun verset — le corpus et le moteur auraient parlé deux langues.


def pericope_id(cle: str) -> UUID:
    return uuid5(NS, f"pericope:{cle}")


async def semer(purge: bool) -> None:
    par_osis = {osis: rang for rang, osis, *_ in BOOKS}

    async with async_session_factory() as s:
        if purge:
            # Ordre inverse des dépendances — la curation d'abord, la référence ensuite.
            for modele in (
                CorpusHomileticFeasibilityModel,
                CorpusContextNoteModel,
                CorpusDoctrinalCaveatModel,
                CorpusDoctrinalBearingModel,
                CorpusPericopeModel,
                CorpusTextualVariantModel,
                CorpusIdfModel,
                CorpusVerseModel,
                CorpusVersionModel,
                CorpusBookNameModel,
                CorpusBookModel,
                CorpusLanguageModel,
            ):
                await s.execute(delete(modele))
            await s.commit()
            print("  purge effectuee")

        deja = await s.scalar(select(CorpusBookModel.id).limit(1))
        if deja is not None:
            print("  corpus deja seme — rien a faire (utiliser --purge pour recommencer)")
            return

        # --- la reference -------------------------------------------------------
        s.add_all([
            CorpusLanguageModel(code="fr", label="Francais", direction="ltr"),
            CorpusLanguageModel(code="grc", label="Grec ancien", direction="ltr"),
            CorpusLanguageModel(code="hbo", label="Hebreu biblique", direction="rtl"),
        ])
        await s.flush()

        for rang, osis, testament, label, abrevs in BOOKS:
            s.add(CorpusBookModel(
                id=rang, osis_code=osis, testament=testament, canon_order=rang,
            ))
            s.add(CorpusBookNameModel(
                book_id=rang, language="fr", label=label,
                # Le nom complet normalise entre aussi dans les abreviations : c'est lui
                # que la saisie contient le plus souvent.
                abbreviations=sorted({normalise(label), *(normalise(a) for a in abrevs)}),
            ))
        await s.flush()
        print(f"  {len(BOOKS)} livres + noms francais")

        s.add(CorpusVersionModel(
            id=LSG_ID, code="LSG", language="fr", label="Louis Segond 1910",
            translation_kind="formelle", license_kind="domaine_public",
            provider=None, offline_allowed=True, metered=False, versification="protestante",
            # 🔴 **Éclectique, et c'est une mesure, pas une opinion.** On la disait « proche du
            # Texte Reçu » ; elle omet la clause de Romains 8:1 et le comma johanneum comme
            # Darby, et lit « celui qui » en 1 Timothée 3:16 là où les trois autres témoins
            # lisent « Dieu ». La croire alignée sur le Texte Reçu avait fait bâtir tout un
            # signal de variante sur une ligne de partage qui n'existe pas.
            text_family="eclectique",
        ))
        await s.flush()

        # --- les versets : la BIBLE ENTIÈRE ------------------------------------
        #
        # Lue depuis `lsg_dataset_path`, le **même fichier** que `mission` (M9-1). Il n'y
        # a plus d'extrait tapé à la main nulle part : un corpus partiel ne permet pas de
        # répondre « ce verset n'existe pas » — il permet seulement de dire « je ne l'ai
        # pas », ce qui n'est pas la même phrase et n'a pas la même valeur pour un pasteur.
        par_livre = {label: rang for rang, _, _, label, _ in BOOKS}
        documents: list[list[str]] = []
        lignes = []
        for etiquette, corps in charger_lsg().items():
            livre, localisateur = etiquette.rsplit(" ", 1)
            chapitre, verset = (int(x) for x in localisateur.split("."))
            norme = normalise(corps)
            lignes.append({
                "version_id": LSG_ID, "book_id": par_livre[livre], "chapter": chapitre,
                "verse": verset, "body": corps, "body_norm": norme,
            })
            documents.append(norme.split())
        # Insertion en masse : 31 000 objets ORM coûteraient une minute et beaucoup de
        # mémoire pour un résultat identique.
        await s.execute(insert(CorpusVerseModel), lignes)
        await s.flush()
        print(f"  {len(lignes)} versets (LSG 1910, domaine public, Bible entiere)")

        # --- l'idf, et le lexique de la LANGUE (S34) ---------------------------
        #
        # Deux populations dans la meme table, et c'est voulu :
        #  * les tokens du texte portent un idf reel — ce sont les ancres rares sur
        #    lesquelles `scripture_affinity` s'appuie ;
        #  * les mots du francais courant entrent a idf **exactement 0.0** — connus de la
        #    langue, sans aucun poids scripturaire. `known_words` compte les deux, ce qui
        #    est exactement la question qu'il pose : « y a-t-il du francais la-dedans ? ».
        #
        # Le lissage `(n + 1) / df` n'est pas cosmetique : sans lui, un mot present dans
        # *tous* les versets tomberait a 0.0 et deviendrait indiscernable d'un mot du
        # lexique. Avec lui, `idf > 0.0` **est** le predicat « ce mot est dans le texte » —
        # ce qui evite une colonne marqueur et garde la table telle que la migration l'a
        # definie.
        df = Counter()
        for doc in documents:
            df.update(set(doc))
        n = len(documents)
        entrees = [
            {"language": "fr", "token": token, "idf": math.log((n + 1) / freq)}
            for token, freq in df.items()
        ]
        entrees += [
            {"language": "fr", "token": mot, "idf": 0.0}
            for mot in {normalise(m) for m in LEXIQUE_FR}
            if mot and mot not in df
        ]
        await s.execute(insert(CorpusIdfModel), entrees)
        await s.flush()
        print(f"  {len(df)} tokens du texte + lexique francais courant")

        # --- les pericopes curees ----------------------------------------------
        for p in PERICOPES:
            s.add(CorpusPericopeModel(
                id=pericope_id(p["key"]), book_id=par_osis[p["osis"]],
                start_ch=p["start_ch"], start_v=p["start_v"],
                end_ch=p["end_ch"], end_v=p["end_v"],
                label=p["label"], rationale=p["rationale"], source_ref=p["source_ref"],
                reviewed_by=REVIEWER, reviewed_at=REVIEWED_AT,
            ))
        await s.flush()
        print(f"  {len(PERICOPES)} pericopes curees")

        for cle, axe, force, motif in BEARINGS:
            s.add(CorpusDoctrinalBearingModel(
                pericope_id=pericope_id(cle), axis_code=axe, strength=force,
                rationale=motif, source_ref="Semis de demonstration",
                reviewed_by=REVIEWER, reviewed_at=REVIEWED_AT,
            ))

        for cle, axe, genre, corps, traditions, source in CAVEATS:
            s.add(CorpusDoctrinalCaveatModel(
                id=uuid5(NS, f"caveat:{cle}:{axe}:{genre}"),
                pericope_id=pericope_id(cle), axis_code=axe, body=corps,
                caveat_kind=genre,
                tradition_scope=list(traditions) if traditions else None,
                source_ref=source, reviewed_by=REVIEWER, reviewed_at=REVIEWED_AT,
            ))

        for cle, genre, ordinal, corps, source in CONTEXT_NOTES:
            s.add(CorpusContextNoteModel(
                id=uuid5(NS, f"context:{cle}:{genre}:{ordinal}"),
                pericope_id=pericope_id(cle), context_kind=genre, body=corps,
                ordinal=ordinal, source_ref=source,
                reviewed_by=REVIEWER, reviewed_at=REVIEWED_AT,
            ))

        for cle, plan, matiere, faisable, refus, risque in FEASIBILITY:
            s.add(CorpusHomileticFeasibilityModel(
                pericope_id=pericope_id(cle), plan_source=plan, subject_matter=matiere,
                feasible=faisable, refusal_reason=refus, proof_text_risk=risque,
                reviewed_by=REVIEWER, reviewed_at=REVIEWED_AT,
            ))

        for v in TEXTUAL_VARIANTS:
            s.add(CorpusTextualVariantModel(
                id=uuid5(NS, f"variant:{v['osis']}:{v['chapter']}:{v['verse']}"),
                book_id=par_osis[v["osis"]], chapter=v["chapter"], verse=v["verse"],
                body=v["body"], families_with=list(v["families_with"]),
                families_without=list(v["families_without"]),
                doctrinal_weight=v["doctrinal_weight"], note=v["note"],
                source_ref=v["source_ref"], reviewed_by=REVIEWER, reviewed_at=REVIEWED_AT,
            ))

        await s.commit()
        print(f"  {len(BEARINGS)} pesees dont "
              f"{sum(1 for b in BEARINGS if b[2] == 'resiste')} 'resiste'")
        print(f"  {len(CAVEATS)} mises en garde, {len(CONTEXT_NOTES)} notes de contexte")
        print(f"  {len(FEASIBILITY)} couples dont "
              f"{sum(1 for f in FEASIBILITY if not f[3])} refus motives")
        print(f"  {len(TEXTUAL_VARIANTS)} variante textuelle")


def main() -> None:
    ap = argparse.ArgumentParser(description="Semis du corpus Urim (demonstration)")
    ap.add_argument("--purge", action="store_true", help="effacer le semis avant de recommencer")
    args = ap.parse_args()
    print("Semis du corpus Urim")
    asyncio.run(semer(args.purge))
    print("OK")


if __name__ == "__main__":
    main()
