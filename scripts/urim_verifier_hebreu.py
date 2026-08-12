"""Le décodeur OSHM contre de **vrais** codes — il a été écrit sans en avoir jamais vu un.

Le semis peut réussir et le produit rester muet : si `morphology_hebrew` ne reconnaît pas les
codes que le WLC écrit vraiment, le pasteur clique sur un mot et reçoit une chaîne brute. Ce
script lit ce qui est en base et compte ce que le décodeur sait en dire.

    python scripts/urim_verifier_hebreu.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select

from app.contexts.urim.infrastructure.corpus.morphology_hebrew import (
    decrire as decode_hebrew_morph,
)
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusLemmaModel,
    CorpusTokenModel,
    CorpusVerseModel,
)
from app.core.database import async_session_factory


async def main() -> None:
    async with async_session_factory() as s:
        lignes = (await s.execute(
            select(
                CorpusVerseModel.book_id, CorpusVerseModel.chapter, CorpusVerseModel.verse,
                CorpusTokenModel.position, CorpusTokenModel.surface,
                CorpusTokenModel.morph_code, CorpusLemmaModel.lemma,
            )
            .join(CorpusVerseModel, CorpusVerseModel.id == CorpusTokenModel.verse_id)
            .outerjoin(CorpusLemmaModel, CorpusLemmaModel.id == CorpusTokenModel.lemma_id)
            .where(CorpusLemmaModel.language == "hbo")
            # ⚠️ **Tout le corpus, pas les premiers mots.** Un échantillon pris au début
            # n'aurait montré que la Genèse — or c'est ailleurs que ça casse : la poésie de
            # Job, et surtout les sections **araméennes** de Daniel 2-7 et d'Esdras 4-7, que
            # le WLC marque d'un préfixe de langue différent.
            .order_by(CorpusVerseModel.book_id, CorpusVerseModel.chapter)
        )).all()

        if not lignes:
            print("Aucun mot hebreu en base.")
            return

        muets, sans_lemme = 0, 0
        exemples: list[str] = []
        prefixes = Counter()
        muets_par_livre = Counter()
        for livre, _c, _v, _p, surface, morph, lemme in lignes:
            lu = decode_hebrew_morph(morph or "")
            prefixes[(morph or "?")[:1]] += 1
            if not lu:
                muets += 1
                muets_par_livre[livre] += 1
                if len(exemples) < 10:
                    exemples.append(f"livre {livre}  {surface}  code={morph!r}")
            if not lemme:
                sans_lemme += 1

        n = len(lignes)
        print(f"  {n} mots examines")
        print(f"  sans lemme lisible   {sans_lemme:>6}  ({100 * sans_lemme / n:.1f} %)")
        print(f"  morphologie muette   {muets:>6}  ({100 * muets / n:.1f} %)")
        if exemples:
            print("\n  codes que le decodeur ne sait pas lire :")
            for e in exemples:
                print(f"    {e}")

        if muets_par_livre:
            print("\n  livres ou le decodeur est muet :")
            for livre, combien in muets_par_livre.most_common(10):
                print(f"    livre {livre:<4} {combien}")

        print("\n  prefixe de langue (H = hebreu, A = arameen) :")
        for tete, combien in prefixes.most_common(5):
            print(f"    {tete!r:<5} {combien}")

        print("\n  echantillon lu :")
        for _b, c, v, p, surface, morph, lemme in lignes[:6]:
            print(f"    {c}:{v}.{p}  {surface:<14} {lemme or '—':<12} "
                  f"{morph:<12} -> {decode_hebrew_morph(morph or '') or '(muet)'}")

        total = await s.scalar(
            select(func.count()).select_from(CorpusLemmaModel)
            .where(CorpusLemmaModel.language == "hbo")
        )
        print(f"\n  {total} lemmes hebreux en base")


if __name__ == "__main__":
    asyncio.run(main())
