"""Une copie des mises en garde avant de les régénérer — **le filet avant la purge**.

    python scripts/urim_sauver_caveats.py

Régénérer 4 449 unités sous une nouvelle invite est une bonne décision **si la nouvelle est
meilleure**, et on ne le saura qu'après. Sans copie, un réglage qui se révèle pire aurait
détruit ce qu'il remplace : le corpus est la seule partie du produit qu'on ne réécrit pas en un
après-midi.

Le fichier n'est pas versionné — c'est un intermédiaire, comme le WLC brut. Il sert à comparer
deux régimes, puis il ne sert plus.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.urim.application.curation import SIGNATAIRE_IA
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusDoctrinalCaveatModel,
    CorpusPericopeModel,
)
from app.core.database import async_session_factory

CIBLE = Path("data/urim_caveats_ancienne_invite.json")


async def _lire() -> list[dict]:
    """La lecture seule — **l'écriture du fichier reste hors de l'async**.

    Une écriture disque bloquante dans une coroutine gèle la boucle ; sur 4 000 lignes ça ne se
    voit pas, mais la règle vaut pour ce dépôt entier et le linter la tient."""
    async with async_session_factory() as s:
        bornes = {
            p.id: f"{p.book_id}:{p.start_ch}:{p.start_v}-{p.end_v}"
            for p in (await s.execute(select(CorpusPericopeModel))).scalars()
        }
        lignes = [
            {
                "unite": bornes.get(c.pericope_id, str(c.pericope_id)),
                "locus": c.axis_code,
                "espece": c.caveat_kind,
                "traditions": c.tradition_scope,
                "corps": c.body,
            }
            for c in (await s.execute(
                select(CorpusDoctrinalCaveatModel).where(
                    CorpusDoctrinalCaveatModel.reviewed_by == SIGNATAIRE_IA
                )
            )).scalars()
        ]

    return lignes


def main() -> None:
    lignes = asyncio.run(_lire())
    CIBLE.parent.mkdir(parents=True, exist_ok=True)
    CIBLE.write_text(json.dumps(lignes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {len(lignes)} mises en garde sauvees dans {CIBLE}")


if __name__ == "__main__":
    main()
