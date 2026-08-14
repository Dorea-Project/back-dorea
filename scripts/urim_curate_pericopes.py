"""Découpage de l'Écriture en unités littéraires, par le modèle — **la clé de voûte**.

    python scripts/urim_curate_pericopes.py                 # les 1189 chapitres
    python scripts/urim_curate_pericopes.py --livre Mal     # un seul livre, pour juger
    python scripts/urim_curate_pericopes.py --limite 20     # les 20 premiers chapitres nus

## Pourquoi cette table et pas les cinq autres

`bearing`, `caveat`, `context_note`, `feasibility` sont **toutes** clées sur `pericope_id`.
Sans unité littéraire, `bound_pericope` ne trouve rien, `pericope_id` reste nul, et les quatre
étages suivants dégradent en cascade : le pasteur reçoit son verset, puis plus rien. Huit
péricopes couvraient 72 versets sur 31 170 — c'est tout ce qui séparait le moteur du vide.

## Qui signe

`reviewed_by = 'ia-mistral'`, et c'est un choix explicite. Le schéma n'a jamais exigé un
humain : il exige **une signature**, et les huit unités de démonstration portaient déjà
`semis-demo`. Nommer le modèle est donc plus honnête que ce qui existait, à une condition —
que la signature remonte jusqu'à l'écran du pasteur, pour qu'une pesée générée ne se confonde
pas avec une pesée relue. C'est la contrepartie, et elle n'est pas négociable.

Un relecteur qui re-signe une unité par la surface de curation l'élève : `reviewed_by` devient
son nom, et la trace de ce qui reste non relu se réduit d'autant.

## Pourquoi le découpage, et pas la doctrine

C'est le moins théologique des six objets curés : une péricope est une **structure
littéraire** — où une péroraison commence, où un récit se referme —, pas un jugement sur ce
que le texte enseigne. Un modèle y est bon et un humain le vérifie vite. Les pesées
doctrinales, elles, restent à écrire par quelqu'un qui répond de ce qu'il affirme.

## Ce que le script refuse d'écrire

Une sortie de modèle n'est pas une donnée tant qu'elle n'a pas été vérifiée contre le texte :
bornes hors du chapitre, trous, chevauchements, motif vide — tout cela est rejeté et le
chapitre est **sauté**, jamais rattrapé par une valeur inventée. Un chapitre absent se voit
au décompte final ; un chapitre faux ne se voit nulle part.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.contexts.urim.application.curation import SIGNATAIRE_IA
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusPericopeModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.config import get_settings
from app.core.database import async_session_factory
from scripts.urim_ecarts import VERSION_DE_CURATION
from scripts.urim_seed_books import BOOKS

NS = UUID(str(uuid5(NAMESPACE_URL, "dorea:urim:corpus")))

#: Le signataire, **emprunté au service de curation** et non redéfini ici. Le garde qui
#: refuse les signatures anonymes et la chaîne qu'écrit ce script doivent être la même
#: valeur, sinon la surface refuserait un jour ce que le semis a écrit la veille.

#: Combien de chapitres en vol à la fois.
#:
#: ⚠️ Huit a coûté un passage entier : **1143 chapitres sur 1178 refusés en 429**, et le script
#: les a comptés comme sautés sans jamais réessayer. Un verrou de concurrence ne borne pas un
#: débit — il borne un nombre d'appels *simultanés*, ce qui n'est pas la même chose quand la
#: contrainte de l'API est « tant de requêtes par seconde ».
CONCURRENCE = 3

#: L'intervalle minimal entre deux appels. C'est lui qui borne réellement le débit.
INTERVALLE = 0.7

#: Combien de fois on réessaie avant d'abandonner un chapitre. Le 429 est **transitoire** :
#: l'abandonner au premier refus revient à jeter un chapitre pour une seconde d'attente.
ESSAIS = 5

_SYSTEME = (
    "Tu es bibliste. On te donne un chapitre entier de la Bible Louis Segond 1910, verset par "
    "verset. Découpe-le en PÉRICOPES : les unités littéraires naturelles du texte — un récit "
    "qui commence et se referme, un discours, un oracle, une péroraison. "
    "RÈGLES STRICTES : (1) les unités doivent couvrir TOUT le chapitre, du premier au dernier "
    "verset, sans trou ni chevauchement ; (2) elles se suivent dans l'ordre ; (3) chaque unité "
    "porte un intitulé court en français et un motif expliquant POURQUOI elle tient ensemble et "
    "pourquoi couper ailleurs amputerait le sens ; (4) un chapitre court peut ne former qu'une "
    "seule unité, c'est une réponse valide. "
    "Tu ne commentes pas la doctrine et tu ne dis pas ce que le texte enseigne : tu décris la "
    "STRUCTURE. Réponds par un objet JSON : "
    '{"unites": [{"debut": 1, "fin": 11, "titre": "...", "motif": "..."}]}'
)


def _decoupage_depuis(contenu: str, dernier: int) -> list[dict] | None:
    """Le JSON du modèle → des unités **vérifiées contre le chapitre**, ou rien.

    ⚠️ La vérification est la moitié du travail. Un modèle qui rend `fin: 31` sur un chapitre
    de 25 versets produit une péricope que le moteur proposera au pasteur et dont le texte
    n'existe pas. On préfère un chapitre manquant à un chapitre faux : le premier se compte,
    le second se découvre en chaire."""
    bloc = re.search(r"\{.*\}", contenu, re.S)
    if bloc is None:
        return None
    try:
        unites = json.loads(bloc.group(0)).get("unites")
    except json.JSONDecodeError:
        return None
    if not isinstance(unites, list) or not unites:
        return None

    attendu = 1
    propres: list[dict] = []
    for unite in unites:
        if not isinstance(unite, dict):
            return None
        debut, fin = unite.get("debut"), unite.get("fin")
        titre, motif = unite.get("titre"), unite.get("motif")
        if not isinstance(debut, int) or not isinstance(fin, int):
            return None
        # Contiguïté stricte : chaque unité reprend exactement où la précédente s'arrête.
        if debut != attendu or fin < debut or fin > dernier:
            return None
        if not isinstance(motif, str) or not motif.strip():
            return None  # `rationale` est NOT NULL, et un motif vide ne motive rien
        propres.append({
            "debut": debut, "fin": fin,
            "titre": (titre or "").strip()[:200] or None,
            "motif": motif.strip(),
        })
        attendu = fin + 1

    return propres if attendu == dernier + 1 else None


class Cadence:
    """Un débit, pas un nombre d'appels simultanés — la distinction a coûté un passage entier.

    Les appels se sérialisent sur un verrou le temps de respecter l'intervalle, puis partent en
    parallèle. La concurrence sert alors à absorber la latence, pas à forcer le débit."""

    def __init__(self, intervalle: float) -> None:
        self._intervalle = intervalle
        self._verrou = asyncio.Lock()
        self._dernier = 0.0

    async def attendre(self) -> None:
        async with self._verrou:
            maintenant = asyncio.get_running_loop().time()
            repos = self._dernier + self._intervalle - maintenant
            if repos > 0:
                await asyncio.sleep(repos)
            self._dernier = asyncio.get_running_loop().time()


async def _un_chapitre(
    ia: MistralAssistant, verrou: asyncio.Semaphore, cadence: Cadence,
    livre: str, rang: int, chapitre: int, versets: list[tuple[int, str]],
) -> tuple[int, int, list[dict] | None]:
    corps = "\n".join(f"{numero}. {texte}" for numero, texte in versets)
    dernier = versets[-1][0]
    # ⚠️ **Le compte, répété en toutes lettres — la Segond ne numérote pas comme l'anglais.**
    #
    # Six chapitres résistaient à tous les réessais, et ce n'était pas le débit : le modèle
    # répondait depuis la versification qu'il a en mémoire au lieu de lire le texte fourni.
    # Psaume 47 compte 10 versets ici et il rendait `fin: 11` ; Job 41 en compte 25 et il
    # rendait 34 ; Ésaïe 9 en compte 20 et il en voyait 21. La validation les rejetait — bien —
    # mais aucune insistance sur le format n'y aurait rien changé : ce n'est pas une erreur de
    # forme, c'est une autre Bible.
    invite = (
        f"{livre} {chapitre} — ce chapitre compte EXACTEMENT {dernier} versets, numérotés de 1 "
        f"à {dernier}. N'utilise aucune autre numérotation que celle affichée ci-dessous, même "
        f"si tu en connais une différente pour ce passage. La dernière unité doit finir au "
        f"verset {dernier}.\n\n{corps}"
    )

    async with verrou:
        for essai in range(ESSAIS):
            await cadence.attendre()
            contenu = await ia.demander(_SYSTEME, invite)
            if contenu:
                decoupage = _decoupage_depuis(contenu, versets[-1][0])
                if decoupage is not None:
                    return rang, chapitre, decoupage
            # `demander` avale l'exception et rend `None` : on ne distingue pas ici un 429 d'une
            # sortie mal formée. Réessayer les deux est sans danger — le second cas est
            # simplement rare, et une attente croissante ne lui coûte que du temps.
            await asyncio.sleep(2 ** essai)

    return rang, chapitre, None


async def curer(livre_voulu: str | None, limite: int | None) -> None:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        raise SystemExit("MISTRAL_API_KEY absente — rien à faire.")

    par_rang = {rang: (osis, nom) for rang, osis, _, nom, _ in BOOKS}
    ia = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)

    async with async_session_factory() as s:
        # Les chapitres **déjà curés** — par qui que ce soit. On ne repasse jamais sur une
        # unité existante : les huit de démonstration restent, et une relecture humaine ne se
        # fait pas écraser par un nouveau passage du modèle.
        curesdeja = {
            (r[0], r[1]) for r in await s.execute(
                select(CorpusPericopeModel.book_id, CorpusPericopeModel.start_ch)
            )
        }

        # 🔴 **Nommer la version — et ici l'absence de filtre ne panache pas, elle empile.**
        #
        # Les trois autres lots rangent les versets dans un dictionnaire : les quatre
        # traductions du corpus s'y écrasent l'une l'autre et il en reste une, arbitraire. Ce
        # script-ci **accumule dans une liste**, triée par (livre, chapitre, verset) sans la
        # version. Le chapitre servi au modèle serait donc le verset 1 quatre fois — Segond,
        # Darby, Ostervald, Martin — puis le verset 2 quatre fois, et ainsi de suite.
        #
        # Ce qu'on lui demande est un **découpage en péricopes** : où le mouvement du texte
        # change. Sur un chapitre lu quatre fois de suite, la réponse n'est pas approximative,
        # elle n'a plus d'objet — et elle deviendrait la borne de toute la curation en aval,
        # puisque pesées, mises en garde et faisabilités se posent sur ces unités-là.
        #
        # ⚠️ Les 4 561 unités en base ont été découpées sous les xid 4739-4833, Darby est entrée
        # à 5407 : elles ont lu de la Segond pure et **rien n'est à refaire**.
        chapitres: dict[tuple[int, int], list[tuple[int, str]]] = defaultdict(list)
        lignes = await s.execute(
            select(
                CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                CorpusVerseModel.verse, CorpusVerseModel.body,
            )
            .join(CorpusVersionModel, CorpusVersionModel.id == CorpusVerseModel.version_id)
            .where(CorpusVersionModel.code == VERSION_DE_CURATION)
            .order_by(
                CorpusVerseModel.book_id, CorpusVerseModel.chapter, CorpusVerseModel.verse
            )
        )
        for rang, chapitre, verset, corps in lignes:
            chapitres[(rang, chapitre)].append((verset, corps))
        # Un corpus non chargé ne rendrait aucun chapitre : le script annoncerait sereinement
        # « 0 a decouper » et sortirait, comme s'il avait fini.
        if not chapitres:
            raise SystemExit(f"  aucun verset en {VERSION_DE_CURATION} — corpus non chargé.")

    a_faire = [
        cle for cle in sorted(chapitres)
        if cle not in curesdeja
        and (livre_voulu is None or par_rang.get(cle[0], ("", ""))[0] == livre_voulu)
    ]
    if limite is not None:
        a_faire = a_faire[:limite]

    print(f"  {len(chapitres)} chapitres au corpus, {len(curesdeja)} deja cures")
    print(f"  {len(a_faire)} a decouper — modele {reglages.mistral_model}\n")
    if not a_faire:
        return

    verrou = asyncio.Semaphore(CONCURRENCE)
    cadence = Cadence(INTERVALLE)
    taches = [
        _un_chapitre(
            ia, verrou, cadence, par_rang[rang][1], rang, chapitre, chapitres[(rang, chapitre)]
        )
        for rang, chapitre in a_faire
        if rang in par_rang
    ]

    ecrites = sautes = 0
    maintenant = datetime.now(UTC)
    lot: list[CorpusPericopeModel] = []

    for fini in asyncio.as_completed(taches):
        rang, chapitre, unites = await fini
        if unites is None:
            sautes += 1
            print(f"  ! saute — {par_rang[rang][1]} {chapitre}")
            continue
        for unite in unites:
            lot.append(CorpusPericopeModel(
                # Déterministe : relancer le script ne crée pas de doublon et ne casse aucune
                # préparation qui référencerait déjà l'unité.
                id=uuid5(NS, f"pericope:ia:{rang}:{chapitre}:{unite['debut']}-{unite['fin']}"),
                book_id=rang, start_ch=chapitre, start_v=unite["debut"],
                end_ch=chapitre, end_v=unite["fin"],
                label=unite["titre"], rationale=unite["motif"],
                source_ref=f"Mistral {reglages.mistral_model} sur LSG 1910 — non relu",
                reviewed_by=SIGNATAIRE_IA, reviewed_at=maintenant,
            ))
        ecrites += 1

        # On écrit **au fil de l'eau** : mille chapitres gardés en mémoire jusqu'au bout
        # signifieraient tout perdre sur une coupure, après avoir payé tous les appels.
        if len(lot) >= 200:
            await _ecrire(lot)
            lot = []
            print(f"  … {ecrites}/{len(taches)} chapitres")

    if lot:
        await _ecrire(lot)

    print(f"\n  {ecrites} chapitres decoupes, {sautes} sautes")


async def _ecrire(lot: list[CorpusPericopeModel]) -> None:
    async with async_session_factory() as s:
        s.add_all(lot)
        await s.commit()


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--livre", help="code OSIS, ex. Mal, Rom, John")
    analyseur.add_argument("--limite", type=int, help="nombre de chapitres a traiter")
    arguments = analyseur.parse_args()
    asyncio.run(curer(arguments.livre, arguments.limite))


if __name__ == "__main__":
    main()
