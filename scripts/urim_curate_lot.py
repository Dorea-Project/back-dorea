"""Conduire une curation **jusqu'au bout**, par tranches, sans y revenir.

    python scripts/urim_curate_lot.py                 # pesées puis faisabilité
    python scripts/urim_curate_lot.py --couche pesees
    python scripts/urim_curate_lot.py --tranche 250

Les scripts de curation savent traiter une tranche ; aucun ne sait mener une couche à son
terme. Les mener à la main a coûté trois pannes en deux jours, et ce pilote existe pour
chacune d'elles.

## La sonde de crédit, avant chaque tranche

Le compte Mistral s'est épuisé en pleine démonstration, et la panne était **silencieuse** :
`demander` avale l'exception, rend `None`, et le chantier compte des unités « sautées » pendant
qu'un pasteur reçoit un écran vide. On sonde donc d'abord — un appel trivial — et on s'arrête
en le **disant** plutôt que de brasser mille unités pour rien.

## L'arrêt se mesure en base, jamais en comptant les tours

`for tour in range(9)` suppose que chaque tranche aboutit. Elles n'aboutissent pas toujours :
une validation rejette, un 429 passe au travers des réessais. On relit donc le décompte réel
entre chaque tranche, et on s'arrête quand la couche est **constatée** complète.

Le garde d'immobilité vient de la même famille : si une tranche n'ajoute rien, insister ne
sert à rien — ce qui reste échoue pour une raison qu'une tranche de plus ne changera pas.

## Une seule tranche à la fois, et on attend sa fin

Deux processus de curation ont tourné une nuit entière après que j'ai cru les arrêter : le
signal avait tué le script parent, pas les enfants. Ici il n'y a pas de parent — le pilote
**est** le processus, et il attend chaque tranche avant la suivante.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.core.config import get_settings
from app.core.database import async_session_factory

RACINE = Path(__file__).resolve().parents[1]

#: `(script, table, libellé)` — l'ordre compte : la faisabilité se clé sur les unités, et
#: rien n'oblige à la calculer avant que les pesées ne soient posées.
COUCHES: dict[str, tuple[str, str]] = {
    "pesees": ("urim_curate_bearings", "urim_corpus_doctrinal_bearing"),
    "faisabilite": ("urim_curate_feasibility", "urim_corpus_homiletic_feasibility"),
}

#: Au-delà, on ne s'acharne pas : ce qui reste échoue pour une raison qu'une tranche de plus
#: ne changera pas — une validation qui rejette, une versification qui diverge.
TRANCHES_STERILES_MAX = 2


async def _avancement(table: str) -> tuple[int, int]:
    async with async_session_factory() as s:
        fait = await s.scalar(text(f"SELECT count(DISTINCT pericope_id) FROM {table}"))
        tout = await s.scalar(text("SELECT count(*) FROM urim_corpus_pericope"))
    return fait or 0, tout or 0


async def _credit_ouvert() -> bool:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        return False
    assistant = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)
    return bool(await assistant.demander('Reponds {"ok": true}.', "sonde"))


def _lancer(script: str, tranche: int) -> None:
    """Une tranche, en sous-processus, **attendue**.

    Le sous-processus plutôt que l'import : chaque tranche repart d'un état propre — pas
    d'index gardé en mémoire, pas de session traînante — et une tranche qui meurt ne tue pas
    le pilote."""
    subprocess.run(
        [sys.executable, str(RACINE / "scripts" / f"{script}.py"), "--limite", str(tranche)],
        cwd=RACINE,
        check=False,
    )


async def conduire(couches: list[str], tranche: int) -> int:
    for couche in couches:
        script, table = COUCHES[couche]
        print(f"\n{'=' * 62}\n  {couche}\n{'=' * 62}")
        steriles = 0
        while True:
            fait, tout = await _avancement(table)
            if fait >= tout:
                print(f"  {couche} COMPLETE — {fait}/{tout}")
                break
            if not await _credit_ouvert():
                print(f"  CREDIT EPUISE — arret a {fait}/{tout}")
                return 1
            print(f"  {fait}/{tout} — tranche de {tranche}")
            _lancer(script, tranche)

            apres, _ = await _avancement(table)
            if apres == fait:
                steriles += 1
                print(f"  tranche sans effet ({steriles}/{TRANCHES_STERILES_MAX})")
                if steriles >= TRANCHES_STERILES_MAX:
                    print(f"  {couche} BLOQUEE a {apres}/{tout} — le reste ne passe pas")
                    break
            else:
                steriles = 0
    return 0


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--couche", choices=sorted(COUCHES), help="une seule couche")
    analyseur.add_argument("--tranche", type=int, default=500)
    arguments = analyseur.parse_args()
    couches = [arguments.couche] if arguments.couche else ["pesees", "faisabilite"]
    raise SystemExit(asyncio.run(conduire(couches, arguments.tranche)))


if __name__ == "__main__":
    main()
