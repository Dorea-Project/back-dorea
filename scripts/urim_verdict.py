"""Poser un verdict de relecture sur une unité — **le geste qui fait décroître la file**.

    python scripts/urim_verdict.py --ref "Apocalypse 5:5-14" --portee D4 \\
        --verdict accepte --par "Richmond" --note "le texte porte reellement huit loci"

    python scripts/urim_verdict.py --ref "Romains 12:9-16" --portee ensemble \\
        --verdict corrige --par "Richmond"

`--portee ensemble` dit que l'unité a été relue **en entier**, et couvre tous les détecteurs.
C'est aussi la seule chose qui saura répondre un jour à *« quelle part du corpus un humain
a-t-il vraiment relue ? »*.

⚠️ **Le verdict est signé d'un nom qui désigne quelqu'un.** Ni `ia-mistral`, ni `demo`, ni
`test` : toute la valeur de cette table tient à ce qu'une machine n'y écrive jamais. Une file
d'attente que le modèle pourrait vider lui-même ne mesurerait plus rien — et le `CHECK` en base
le tient, pas seulement ce script.

L'empreinte de la curation est prise **au moment du verdict**. Si les pesées de l'unité sont
régénérées plus tard, l'accord se périme et l'unité revient en file : *une décision ne vaut que
sur l'objet qu'elle a regardé.*
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.urim.application.curation import (
    empreinte_de_curation,
    verifier_verdict,
)
from app.contexts.urim.domain.errors import CurationInvalideError
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusPericopeModel,
    CorpusReviewModel,
)
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS


async def poser(
    ref: str, portee: str, verdict: str, par: str, note: str | None, retirer: bool
) -> None:
    """Poser un verdict, ou le retirer.

    ⚠️ **Le retrait n'est pas un détail d'outillage.** Un verdict est une affirmation qu'un
    humain nommé a jugé ; s'il a été posé à tort — par erreur, par un essai, au nom de
    quelqu'un qui n'a rien jugé — le corriger en le *remplaçant* laisserait une signature à la
    place d'une autre. La seule réparation honnête est de rendre la table à ce qu'elle doit
    dire : personne n'a relu cette unité."""
    if not retirer:
        try:
            verifier_verdict(verdict, portee, par)
        except CurationInvalideError as refus:
            raise SystemExit(f"  refuse : {refus}") from refus

    par_rang = {rang: nom for rang, _osis, _t, nom, _a in BOOKS}

    async with async_session_factory() as s:
        cible = None
        for p in (await s.execute(select(CorpusPericopeModel))).scalars():
            nom = par_rang.get(p.book_id, "?")
            if f"{nom} {p.start_ch}:{p.start_v}-{p.end_v}" == ref:
                cible = p
                break
        if cible is None:
            raise SystemExit(f"  aucune unite a « {ref} »")

        if retirer:
            existant = await s.get(CorpusReviewModel, (cible.id, portee))
            if existant is None:
                print(f"  aucun verdict a retirer sur {ref} — {portee}")
                return
            await s.delete(existant)
            await s.commit()
            print(f"  verdict retire : {ref} — {portee} (etait signe {existant.reviewed_by})")
            return

        lignes: list[tuple[str, str, str]] = []
        for b in (await s.execute(
            select(CorpusDoctrinalBearingModel).where(
                CorpusDoctrinalBearingModel.pericope_id == cible.id
            )
        )).scalars():
            lignes.append(("pesée", b.axis_code, b.rationale))
        for c in (await s.execute(
            select(CorpusDoctrinalCaveatModel).where(
                CorpusDoctrinalCaveatModel.pericope_id == cible.id
            )
        )).scalars():
            lignes.append(("mise en garde", c.axis_code, c.body))

        empreinte = empreinte_de_curation(lignes)
        existant = await s.get(CorpusReviewModel, (cible.id, portee))
        if existant is None:
            s.add(CorpusReviewModel(
                pericope_id=cible.id, scope=portee, verdict=verdict,
                judged_fingerprint=empreinte, note=note,
                reviewed_by=par.strip(), reviewed_at=datetime.now(UTC),
            ))
        else:
            # Un relecteur change d'avis : c'est son droit, et la trace suit son dernier mot.
            existant.verdict = verdict
            existant.judged_fingerprint = empreinte
            existant.note = note
            existant.reviewed_by = par.strip()
            existant.reviewed_at = datetime.now(UTC)
        await s.commit()

    print(f"  {ref} — {portee} : {verdict} (par {par.strip()})")
    print(f"  empreinte jugee : {empreinte}  ({len(lignes)} lignes de curation)")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--ref", required=True, help='ex. "Apocalypse 5:5-14"')
    analyseur.add_argument("--portee", required=True, help="D1..D5, ou ensemble")
    analyseur.add_argument("--verdict", default="", help="accepte | corrige | a_reprendre")
    analyseur.add_argument("--par", default="", help="le nom du relecteur")
    analyseur.add_argument("--note", help="pourquoi — facultatif, et precieux")
    analyseur.add_argument(
        "--retirer", action="store_true", help="retirer un verdict pose a tort"
    )
    a = analyseur.parse_args()
    asyncio.run(poser(a.ref, a.portee, a.verdict, a.par, a.note, a.retirer))


if __name__ == "__main__":
    main()
