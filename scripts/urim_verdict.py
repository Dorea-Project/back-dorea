"""Poser un verdict de relecture en ligne de commande — **le chemin de service, plus le chemin
normal**.

    python scripts/urim_verdict.py --ref "Apocalypse 5:5-14" --portee D4 \\
        --verdict accepte --identifiant kouassi --secret "…" \\
        --note "le texte porte reellement huit loci"

    python scripts/urim_verdict.py --ref "Romains 12:9-16" --portee ensemble --retirer

🔴 **Ce script ne dit plus le nom du signataire ; il le prouve.** Il portait `--par "Richmond"`,
et c'est par là qu'un verdict a été posé au nom du propriétaire du dépôt pour un essai — il a
fallu le retirer, d'où `--retirer`. Une garantie que la surface HTTP tient et qu'un script
d'à-côté contourne n'est pas une garantie : c'est une porte de derrière avec un panneau dessus.
Le nom vient donc du registre (`scripts/urim_relecteur.py`), ici comme sur la route.

**Le chemin normal est désormais l'écran** : `GET /api/backoffice/platform/urim/relecture/file`
puis `POST …/verdict`. Un théologien ne tapera jamais `--portee D4`, et c'est précisément
pourquoi la file est restée à zéro relecture pendant que l'outillage, lui, fonctionnait. Ce
script reste pour le développement et la reprise.

`--portee ensemble` dit que l'unité a été relue **en entier** et couvre tous les détecteurs.
C'est ce qui répond à *« quelle part du corpus un humain a-t-il vraiment relue ? »*.

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
    COUCHE_MISE_EN_GARDE,
    COUCHE_PESEE,
    empreinte_de_curation,
    verifier_verdict,
)
from app.contexts.urim.application.relecture import RegistreDesRelecteurs
from app.contexts.urim.domain.errors import CurationInvalideError, RelecteurInconnuError
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusPericopeModel,
    CorpusReviewModel,
)
from app.contexts.urim.infrastructure.persistence.relecture_repository import (
    SqlRegistreRepository,
)
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS


async def poser(
    ref: str, portee: str, verdict: str, identifiant: str, secret: str,
    note: str | None, retirer: bool,
) -> None:
    """Poser un verdict, ou le retirer.

    ⚠️ **Le retrait n'est pas un détail d'outillage.** Un verdict est une affirmation qu'un
    humain nommé a jugé ; s'il a été posé à tort — par erreur, par un essai, au nom de
    quelqu'un qui n'a rien jugé — le corriger en le *remplaçant* laisserait une signature à la
    place d'une autre. La seule réparation honnête est de rendre la table à ce qu'elle doit
    dire : personne n'a relu cette unité.

    Le retrait ne demande pas de secret, et c'est délibéré : il n'affirme rien. On n'exige pas
    de s'authentifier pour effacer une affirmation qu'on soupçonne fausse — sans quoi un verdict
    signé d'un identifiant perdu serait indélébile."""
    par_rang = {rang: nom for rang, _osis, _t, nom, _a in BOOKS}

    async with async_session_factory() as s:
        nom = ""
        if not retirer:
            try:
                nom = (await RegistreDesRelecteurs(
                    SqlRegistreRepository(s)
                ).identifier(f"{identifiant}:{secret}")).nom
                verifier_verdict(verdict, portee, nom)
            except (RelecteurInconnuError, CurationInvalideError) as refus:
                raise SystemExit(f"  refuse : {refus}") from refus

        cible = None
        for p in (await s.execute(select(CorpusPericopeModel))).scalars():
            libelle = par_rang.get(p.book_id, "?")
            if f"{libelle} {p.start_ch}:{p.start_v}-{p.end_v}" == ref:
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
            lignes.append((COUCHE_PESEE, b.axis_code, b.rationale))
        for c in (await s.execute(
            select(CorpusDoctrinalCaveatModel).where(
                CorpusDoctrinalCaveatModel.pericope_id == cible.id
            )
        )).scalars():
            lignes.append((COUCHE_MISE_EN_GARDE, c.axis_code, c.body))

        empreinte = empreinte_de_curation(lignes)
        existant = await s.get(CorpusReviewModel, (cible.id, portee))
        if existant is None:
            s.add(CorpusReviewModel(
                pericope_id=cible.id, scope=portee, verdict=verdict,
                judged_fingerprint=empreinte, note=note,
                reviewed_by=nom, reviewed_at=datetime.now(UTC),
            ))
        else:
            # Un relecteur change d'avis : c'est son droit, et la trace suit son dernier mot.
            existant.verdict = verdict
            existant.judged_fingerprint = empreinte
            existant.note = note
            existant.reviewed_by = nom
            existant.reviewed_at = datetime.now(UTC)
        await s.commit()

    print(f"  {ref} — {portee} : {verdict} (par {nom})")
    print(f"  empreinte jugee : {empreinte}  ({len(lignes)} lignes de curation)")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--ref", required=True, help='ex. "Apocalypse 5:5-14"')
    analyseur.add_argument("--portee", required=True, help="D1..D5, ou ensemble")
    analyseur.add_argument("--verdict", default="", help="accepte | corrige | a_reprendre")
    analyseur.add_argument("--identifiant", default="", help="un relecteur enrole")
    analyseur.add_argument("--secret", default="", help="son secret — jamais un nom")
    analyseur.add_argument("--note", help="pourquoi — facultatif, et precieux")
    analyseur.add_argument(
        "--retirer", action="store_true", help="retirer un verdict pose a tort"
    )
    a = analyseur.parse_args()
    asyncio.run(poser(
        a.ref, a.portee, a.verdict, a.identifiant, a.secret, a.note, a.retirer
    ))


if __name__ == "__main__":
    main()
