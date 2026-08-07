"""Essai à froid du moteur Urim contre le corpus réel — sans HTTP, sans routes.

    python scripts/urim_smoke.py

Fait tourner les huit étages sur les saisies des simulations, et **affiche ce que le
pasteur verrait** : le motif de chaque étage, l'issue, et les options quand la main lui
revient. C'est le dernier point de contrôle avant d'exposer quoi que ce soit en HTTP.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine.deps import EngineDeps
from app.contexts.urim.engine.normalizer import tokens as decouper
from app.contexts.urim.engine.pipeline import UrimEngine
from app.contexts.urim.engine.state import EntryMode, StudyState
from app.contexts.urim.infrastructure.corpus.index import load_corpus_index
from app.contexts.urim.infrastructure.corpus.readers import (
    IndexedCorpusReader,
    IndexedDoctrineReader,
    IndexedHomileticsReader,
    IndexedVersionResolver,
    RequestScope,
)
from app.core.database import async_session_factory

EGLISE = UUID("11111111-1111-1111-1111-111111111111")
AUTEUR = UUID("22222222-2222-2222-2222-222222222222")
FIGE = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)

SAISIES: tuple[tuple[str, EntryMode], ...] = (
    ("2 Cor 5:17", EntryMode.REFERENCE),
    ("1 Cor 5:17", EntryMode.REFERENCE),
    ("Jean 3:16", EntryMode.REFERENCE),
    ("Romains 8:1-11", EntryMode.REFERENCE),
    ("1 Roi ou 2 Roi, il s'agit de Jezabel", EntryMode.REFERENCE),
    ("une nouvelle creature en Christ", EntryMode.CITATION),
    ("lamour fraternel nexiiste plus dans leglise", EntryMode.CONVICTION),
)


def afficher(titre: str, run) -> None:
    print(f"\n{'=' * 78}\n  {titre}\n{'=' * 78}")
    for entree in run.state.trace:
        print(f"  [{entree.stage_code}] {entree.rationale}")
    dernier = run.results[-1] if run.results else None
    if dernier is None:
        print("  (aucun etage ne s'applique)")
        return
    print(f"\n  ISSUE : {dernier.outcome}")
    if dernier.options:
        print(f"  {len(dernier.options)} option(s) rendues au pasteur :")
        for o in dernier.options:
            print(f"     - {o.code} | {o.label}")
            print(f"       {o.rationale}")
    e = run.state
    print(f"\n  resolu={e.resolved}  pericope={'oui' if e.pericope_id else 'non'}  "
          f"axe={e.axis}  plan={e.plan_source}x{e.subject_matter}")
    if e.theme:
        print(f"  theme propose : {e.theme}")


async def main() -> None:
    async with async_session_factory() as session:
        index = await load_corpus_index(session)

    portee = RequestScope(preached_axes=(), ceiling_reached=False)
    deps = EngineDeps(
        corpus=IndexedCorpusReader(index),
        doctrine=IndexedDoctrineReader(index),
        homiletics=IndexedHomileticsReader(index, portee),
        context=NullEcclesialContext(),
        versions=IndexedVersionResolver(index, portee),
        clock=lambda: FIGE,
    )
    moteur = UrimEngine(deps)
    print(f"corpus snapshot = {index.snapshot}")
    print(f"{len(index.verses)} versets, {len(index.pericopes)} pericopes, "
          f"{len(index.books_by_form)} formes de nom")

    lecteur = IndexedCorpusReader(index)
    print("\n--- controle des lecteurs ---")
    for saisie in ("2 cor 5 17", "1 roi", "jean"):
        mots = decouper(saisie)
        candidats = [
            f"{r.book} {r.chapter}:{r.verse_start}"
            for r in lecteur.parse_reference_candidates(mots)
        ]
        print(f"  {saisie!r:16s} empan={lecteur.find_reference_span(mots)}")
        print(f"                   candidats={candidats}")

    for texte, mode in SAISIES:
        etat = StudyState(
            session_id=uuid4(), church_id=EGLISE, author_id=AUTEUR,
            corpus_snapshot=index.snapshot, entry_mode=mode, raw_input=texte,
        )
        afficher(f"{mode.value} :: {texte}", moteur.run(etat))


if __name__ == "__main__":
    asyncio.run(main())
