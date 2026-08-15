"""Enrôler un relecteur — **le geste qui donne un nom au signataire**.

    python scripts/urim_relecteur.py --enroler kouassi --nom "Kouassi Jean"
    python scripts/urim_relecteur.py --lister
    python scripts/urim_relecteur.py --revoquer kouassi

🔴 **Pourquoi ce script existe.** `reviewed_by` était un champ de formulaire. Aucun validateur ne
peut refuser un nom *parce qu'il est celui de quelqu'un d'autre* — et un verdict d'essai a été
posé au nom du propriétaire du dépôt, qu'il a fallu retirer (d'où `--retirer` sur
`urim_verdict.py`). Le défaut n'était pas dans le garde, il était en amont : *tant que le nom est
une donnée d'entrée, aucune vérification ne le sauve.*

Ici, le nom est **inscrit une fois**, hors ligne, avec un secret. La surface le rend contre la
preuve de ce secret, et plus aucune route ne lit de `reviewed_by`.

⚠️ **Ce que ça garantit, et ce que ça ne garantit pas.** Pas « c'est bien Kouassi Jean » : il n'y
a pas d'identité authentifiée dans ce produit avant la console d'administration Dorea
(`docs/Dorea_Platform_Admin.md` — comptes staff nominatifs, mot de passe + OTP, journal d'audit).
Ça garantit qu'on ne signe que d'un nom **dont on détient le secret**, et que ce nom se
**révoque**. C'est un cran, pas la fin.

Le secret ne s'affiche **qu'une fois**, à l'enrôlement : la base n'en garde que l'empreinte. Le
perdre oblige à ré-enrôler, ce qui est le comportement voulu — un secret qu'on peut retrouver
depuis la base est un secret que quelqu'un d'autre peut retrouver aussi.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.urim.application.curation import SIGNATAIRE_IA
from app.contexts.urim.application.relecture import empreinte_de_secret
from app.contexts.urim.infrastructure.persistence.corpus_models import CorpusReviewerModel
from app.core.database import async_session_factory


async def enroler(identifiant: str, nom: str) -> None:
    if identifiant == SIGNATAIRE_IA or nom == SIGNATAIRE_IA:
        raise SystemExit("  refuse : la machine ne s'enrole pas.")
    if len(nom.strip()) < 3:
        raise SystemExit("  refuse : un nom qui designe quelqu'un, pas une abreviation.")

    secret = secrets.token_urlsafe(32)
    async with async_session_factory() as s:
        existant = await s.get(CorpusReviewerModel, identifiant)
        if existant is not None:
            # Ré-enrôler remplace le secret et **réactive** : c'est la sortie de « secret perdu »,
            # et elle doit exister, sinon la seule issue serait d'écrire en base à la main.
            existant.display_name = nom.strip()
            existant.secret_hash = empreinte_de_secret(secret)
            existant.active = True
            existant.revoked_at = None
        else:
            s.add(CorpusReviewerModel(
                identifiant=identifiant, display_name=nom.strip(),
                secret_hash=empreinte_de_secret(secret), active=True,
                enrolled_at=datetime.now(UTC),
            ))
        await s.commit()

    print(f"  relecteur enrole : {identifiant} — signera « {nom.strip()} »")
    print("  en-tete a presenter sur chaque ecriture (affiche UNE SEULE FOIS) :")
    print(f"\n    X-Urim-Relecteur: {identifiant}:{secret}\n")


async def revoquer(identifiant: str) -> None:
    """La ligne reste. **On retire le pouvoir de signer, pas la trace d'avoir signé.**

    Supprimer la ligne laisserait des verdicts signés d'un nom que plus rien ne rattache à
    quelqu'un — exactement l'état que ce registre existe pour empêcher."""
    async with async_session_factory() as s:
        ligne = await s.get(CorpusReviewerModel, identifiant)
        if ligne is None:
            raise SystemExit(f"  aucun relecteur « {identifiant} »")
        ligne.active = False
        ligne.revoked_at = datetime.now(UTC)
        await s.commit()
    print(f"  {identifiant} ne peut plus signer. Ses verdicts restent, et disent toujours qui.")


async def lister() -> None:
    async with async_session_factory() as s:
        lignes = (await s.execute(
            select(CorpusReviewerModel).order_by(CorpusReviewerModel.enrolled_at)
        )).scalars().all()
    if not lignes:
        print("  aucun relecteur enrole — aucune ecriture de curation n'est possible.")
        return
    for ligne in lignes:
        etat = "actif" if ligne.active else "revoque"
        print(f"  {ligne.identifiant:<20} {ligne.display_name:<30} {etat}")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--enroler", help="l'identifiant technique, ex. kouassi")
    analyseur.add_argument("--nom", help="le nom qui sera ecrit dans reviewed_by")
    analyseur.add_argument("--revoquer", help="retirer le pouvoir de signer")
    analyseur.add_argument("--lister", action="store_true")
    a = analyseur.parse_args()

    if a.enroler:
        if not a.nom:
            raise SystemExit("  --nom est requis : c'est lui que le pasteur lira.")
        asyncio.run(enroler(a.enroler.strip(), a.nom))
    elif a.revoquer:
        asyncio.run(revoquer(a.revoquer.strip()))
    else:
        asyncio.run(lister())


if __name__ == "__main__":
    main()
