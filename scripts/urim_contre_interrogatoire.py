"""D6 — **le contre-interrogatoire** : on demande au modèle de RÉFUTER, pas de confirmer.

    python scripts/urim_contre_interrogatoire.py --livre Mark
    python scripts/urim_contre_interrogatoire.py --limite 40
    python scripts/urim_contre_interrogatoire.py --lire 12     # les prises, en entier

Les cinq détecteurs gratuits attrapent la **forme** et la **cohérence** : une contradiction
interne, un gabarit, une forme interdite, une aberration, une citation absente du passage. Ils
sont incapables d'attraper la seule erreur qui compte vraiment — *cette pesée est fausse sur le
texte*. Aucune expression régulière ne la voit.

D6 tourne donc sur ce que D1-D5 **ne voient pas**, c'est-à-dire sur le corpus entier.

## Pourquoi réfuter et non vérifier

Un modèle à qui l'on demande *« est-ce vrai ? »* répond oui : c'est le même réflexe de serviabilité
qui, sur les pesées, marquait tout `porte`, et qui sur les mises en garde remplissait le plafond.
On lui demande donc l'inverse — *« que le passage ne porte-t-il pas ? »* — et on exige que chaque
réfutation **s'appuie sur le passage**, jamais sur ce qu'il sait d'ailleurs.

⚠️ **Le danger symétrique est réel et le banc devra le surveiller.** Un modèle sommé de réfuter
réfute trop. L'invite dit donc explicitement que la plupart des affirmations tiennent, et que
détruire une ligne juste coûte aussi cher que d'en laisser passer une fausse — c'est la même
règle que « zéro est le cas le plus fréquent », qui a fait tomber le zèle des mises en garde de
81 % à 47 %.

## Ce que ce détecteur ne prouve pas

**Le modèle qui juge est celui qui a écrit.** Il ne s'en souvient pas — il est sans mémoire —
mais il partage ses propres biais : l'accord mesure la **stabilité**, jamais la vérité. On l'a
vu quand 85 % des unités réexaminées sont revenues vides : c'était de la reproductibilité.

**Le désaccord, lui, est un signal fort.** C'est tout ce qu'on lui demande : réduire la file
avant qu'un humain la touche, en montrant où deux passages du même modèle ne s'accordent pas
sur un texte.

## Pourquoi une trace de reprise en fichier, et non en base

Le lot des mises en garde a enseigné qu'un lot sans trace n'est pas reprenable : une unité
examinée sans trouvaille est indiscernable d'une unité jamais examinée, et rattraper cent
unités en referait deux mille six cents.

La trace devrait donc être une table. Elle ne l'est pas **parce que cinq worktrees partagent la
base de dev** et que l'entête d'Alembic y est déjà en avance de deux révisions sur cet arbre.
Un fichier suffit à un lot qu'un développeur lance, et il évite d'ajouter une tête de migration
de plus. À la fusion, ce sera une table.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.urim.application.curation import empreinte_de_curation
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusPericopeModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.config import get_settings
from app.core.database import async_session_factory
from scripts.urim_curate_pericopes import CONCURRENCE, ESSAIS, INTERVALLE, Cadence
from scripts.urim_seed_books import BOOKS

#: La version contre laquelle toute la curation a été écrite. La nommer est obligatoire depuis
#: qu'il y en a quatre — l'oublier avait fait accuser d'invention treize citations exactes.
VERSION_DE_CURATION = "LSG"

TRACE = Path("data/urim_contre_interrogatoire.json")

#: Fermé, comme partout. `incertain` existe pour que le modèle ait où mettre ce qu'il ne sait
#: pas trancher — sans cette issue, il choisirait au hasard entre les deux autres.
VERDICTS = ("tient", "refute", "incertain")

_SYSTEME = (
    "Tu es bibliste. On te donne un passage de la Bible Louis Segond 1910, puis une liste "
    "d'AFFIRMATIONS numérotées portant sur ce passage. Ta tâche n'est pas de les approuver : "
    "c'est de chercher lesquelles le passage NE PORTE PAS.\n"
    "Pour chacune, un verdict parmi exactement trois :\n"
    "- 'tient' : le passage soutient cette affirmation.\n"
    "- 'refute' : le passage la contredit, ou ne la porte pas. Tu dois alors dire EN QUOI, en "
    "t'appuyant sur le texte qu'on te donne — un verset, un mot, une absence précise.\n"
    "- 'incertain' : le passage ne permet ni de la soutenir ni de l'écarter.\n"
    "CINQ RÈGLES QUE TU DOIS SUIVRE CONTRE TON INSTINCT :\n"
    "(0) LA PLUPART DES AFFIRMATIONS TIENNENT. Elles ont été écrites en lisant ce même "
    "passage. Détruire une affirmation juste coûte aussi cher que laisser passer une fausse : "
    "ne réfute que ce que tu peux montrer, pas ce qui te paraît discutable.\n"
    "(1) Ton seul appui est LE PASSAGE FOURNI. Pas ce que tu sais du reste de l'Écriture, pas "
    "un commentaire, pas une tradition. Une affirmation vraie ailleurs mais absente d'ici se "
    "réfute — et c'est précisément ce qu'on cherche.\n"
    "(2) Une affirmation qui dit qu'un sujet est ABSENT du passage est vraie tant que le "
    "passage n'en parle pas. Ne la réfute pas parce que le sujet existe ailleurs dans la Bible.\n"
    "(3) Ne réécris aucune affirmation, ne propose pas de meilleure formulation. Tu juges, tu "
    "ne cures pas.\n"
    "(4) RELIS TON MOTIF AVANT DE CONCLURE. S'il revient à redire l'affirmation autrement, "
    "alors elle TIENT — ce n'est pas une réfutation. Beaucoup d'affirmations sont elles-mêmes "
    "négatives (« le texte ne dit pas X ») : pour en réfuter une, tu dois montrer que le "
    "passage DIT X, pas expliquer une seconde fois qu'il ne le dit pas.\n"
    'Réponds par un objet JSON : {"verdicts": [{"n": 1, "verdict": "...", "motif": "..."}]} '
    "avec une entrée par affirmation, dans l'ordre. `motif` n'est requis que pour 'refute'."
)


@dataclass
class Affirmation:
    unite: UUID
    reference: str
    couche: str
    axe: str
    corps: str


@dataclass
class Verdict:
    affirmation: Affirmation
    verdict: str
    motif: str


def _lire_verdicts(contenu: str, combien: int) -> list[tuple[str, str]] | None:
    """Le JSON du modèle → un verdict par affirmation, ou rien."""
    bloc = re.search(r"\{.*\}", contenu, re.S)
    if bloc is None:
        return None
    try:
        rendus = json.loads(bloc.group(0)).get("verdicts")
    except json.JSONDecodeError:
        return None
    if not isinstance(rendus, list) or len(rendus) != combien:
        return None

    lus: list[tuple[str, str]] = []
    for rendu in rendus:
        if not isinstance(rendu, dict) or rendu.get("verdict") not in VERDICTS:
            return None
        motif = rendu.get("motif") or ""
        # ⚠️ Une réfutation sans motif n'est pas une réfutation, c'est une humeur. On la
        # dégrade en `incertain` plutôt que de la jeter : le modèle a bien signalé quelque
        # chose, il n'a simplement pas su dire quoi.
        verdict = rendu["verdict"]
        if verdict == "refute" and len(str(motif).strip()) < 15:
            verdict = "incertain"
        lus.append((verdict, str(motif).strip()[:800]))
    return lus


async def _une_unite(
    ia, verrou: asyncio.Semaphore, cadence: Cadence,
    affirmations: list[Affirmation], invite: str,
) -> list[Verdict] | None:
    async with verrou:
        for essai in range(ESSAIS):
            avant = ia.echecs
            await cadence.attendre()
            contenu = await ia.demander(_SYSTEME, invite, etiquette="contre-interrogatoire")
            if contenu and ia.echecs == avant:
                lus = _lire_verdicts(contenu, len(affirmations))
                if lus is not None:
                    return [
                        Verdict(a, v, m) for a, (v, m) in zip(affirmations, lus, strict=True)
                    ]
            await asyncio.sleep(2**essai)
    return None


async def _charger(livre_voulu: str | None) -> list[tuple[str, list[Affirmation], str]]:
    """Les unités et leurs affirmations substantielles, avec le texte du passage."""
    par_rang = {rang: label for rang, _osis, _t, label, _a in BOOKS}
    rang_voulu = next(
        (r for r, osis, *_ in BOOKS if osis == livre_voulu), None
    ) if livre_voulu else None

    async with async_session_factory() as s:
        unites = {
            p.id: p for p in (await s.execute(select(CorpusPericopeModel))).scalars()
            if rang_voulu is None or p.book_id == rang_voulu
        }

        versets: dict[tuple[int, int, int], str] = {}
        for livre, ch, v, corps in await s.execute(
            select(
                CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                CorpusVerseModel.verse, CorpusVerseModel.body,
            )
            .join(CorpusVersionModel, CorpusVersionModel.id == CorpusVerseModel.version_id)
            .where(CorpusVersionModel.code == VERSION_DE_CURATION)
        ):
            versets[(livre, ch, v)] = corps

        #: ⚠️ **Seulement ce qui AFFIRME.** Un motif d'`absent` dit « ce passage n'en parle
        #: pas » — le contre-interroger reviendrait à demander au modèle de prouver une
        #: absence, ce qu'aucun texte ne permet. Et ils sont les deux tiers du corpus : les
        #: inclure triplerait la facture pour du bruit.
        claims: dict[UUID, list[Affirmation]] = {}
        for b in (await s.execute(
            select(CorpusDoctrinalBearingModel).where(
                CorpusDoctrinalBearingModel.strength != "absent"
            )
        )).scalars():
            if b.pericope_id in unites:
                claims.setdefault(b.pericope_id, []).append(Affirmation(
                    b.pericope_id, "", "pesée", b.axis_code, b.rationale
                ))
        for c in (await s.execute(select(CorpusDoctrinalCaveatModel))).scalars():
            if c.pericope_id in unites:
                claims.setdefault(c.pericope_id, []).append(Affirmation(
                    c.pericope_id, "", "mise en garde", c.axis_code, c.body
                ))

    lots: list[tuple[str, list[Affirmation], str]] = []
    for unite_id, affirmations in claims.items():
        p = unites[unite_id]
        nom = par_rang.get(p.book_id, "?")
        reference = f"{nom} {p.start_ch}:{p.start_v}-{p.end_v}"
        texte = "\n".join(
            f"{n}. {versets[(p.book_id, p.start_ch, n)]}"
            for n in range(p.start_v, p.end_v + 1)
            if (p.book_id, p.start_ch, n) in versets
        )
        if not texte:
            continue
        for a in affirmations:
            a.reference = reference
        numerotees = "\n".join(
            f"{i}. [{a.couche} · {a.axe}] {a.corps}"
            for i, a in enumerate(affirmations, start=1)
        )
        invite = (
            f"{reference} — « {p.label or 'sans titre'} »\n\n{texte}\n\n"
            f"AFFIRMATIONS A JUGER :\n{numerotees}"
        )
        empreinte = empreinte_de_curation(
            (a.couche, a.axe, a.corps) for a in affirmations
        )
        lots.append((empreinte, affirmations, invite))
    return lots


def _trace_lue() -> dict[str, str]:
    """`unité → empreinte déjà contre-interrogée`. La reprise tient dans ce fichier."""
    if not TRACE.exists():
        return {}
    return json.loads(TRACE.read_text(encoding="utf-8")).get("faites", {})


def _trace_ecrite(faites: dict[str, str], prises: list[dict]) -> None:
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    ancien = json.loads(TRACE.read_text(encoding="utf-8")) if TRACE.exists() else {}
    ancien.setdefault("prises", []).extend(prises)
    ancien["faites"] = {**ancien.get("faites", {}), **faites}
    TRACE.write_text(json.dumps(ancien, ensure_ascii=False, indent=1), encoding="utf-8")


async def interroger(livre: str | None, limite: int | None, lire: int) -> None:
    reglages = get_settings()
    if lire:
        _rapport_des_prises(lire)
        return
    if not reglages.mistral_api_key:
        raise SystemExit("MISTRAL_API_KEY absente — rien a faire.")

    from app.contexts.urim.adapters.mistral import MistralAssistant

    deja = _trace_lue()
    lots = [
        lot for lot in await _charger(livre)
        # ⚠️ L'empreinte, et non l'identifiant : une curation régénérée doit être
        # recontre-interrogée. Un verdict ne vaut que sur l'objet qu'il a regardé.
        if deja.get(str(lot[1][0].unite)) != lot[0]
    ]
    if limite is not None:
        lots = lots[:limite]

    print(f"  {len(deja)} unites deja contre-interrogees")
    print(f"  {len(lots)} a interroger — modele {reglages.mistral_model}\n")
    if not lots:
        return

    ia = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)
    verrou, cadence = asyncio.Semaphore(CONCURRENCE), Cadence(INTERVALLE)
    taches = [
        _une_unite(ia, verrou, cadence, affirmations, invite)
        for _empreinte, affirmations, invite in lots
    ]
    empreintes = {str(a[0].unite): e for e, a, _ in lots}

    compte = dict.fromkeys(VERDICTS, 0)
    faites: dict[str, str] = {}
    prises: list[dict] = []
    sautees = 0

    for fini in asyncio.as_completed(taches):
        verdicts = await fini
        if verdicts is None:
            sautees += 1
            continue
        unite = str(verdicts[0].affirmation.unite)
        faites[unite] = empreintes[unite]
        for v in verdicts:
            compte[v.verdict] += 1
            if v.verdict != "tient":
                prises.append({
                    "reference": v.affirmation.reference, "couche": v.affirmation.couche,
                    "axe": v.affirmation.axe, "affirmation": v.affirmation.corps,
                    "verdict": v.verdict, "motif": v.motif,
                })

    _trace_ecrite(faites, prises)
    total = sum(compte.values()) or 1
    print(f"  {len(faites)} unites interrogees, {sautees} sautees\n")
    for verdict in VERDICTS:
        print(f"    {verdict:<10} {compte[verdict]:>6}  {100 * compte[verdict] / total:5.1f} %")
    print("\n  ⚠️ Si 'refute' depasse quelques pour cent, l'invite refute trop —")
    print("     detruire une ligne juste coute aussi cher que d'en laisser passer une fausse.")
    print(f"\n  --lire N pour relire les prises. Trace : {TRACE}")


def _rapport_des_prises(combien: int) -> None:
    """🔴 **Relire les prises, toujours.** Neuf « formes interdites » signalées un jour, huit
    etaient les meilleures lignes du corpus. Un detecteur qu'on ne relit pas fait arbitrer sur
    sa parole."""
    if not TRACE.exists():
        print("  aucune trace — lancer le contre-interrogatoire d'abord.")
        return
    prises = json.loads(TRACE.read_text(encoding="utf-8")).get("prises", [])
    refutes = [p for p in prises if p["verdict"] == "refute"]
    print(f"  {len(prises)} prises, dont {len(refutes)} refutees\n")
    for p in refutes[:combien]:
        print(f"\n  {p['reference']}   [{p['couche']} · {p['axe']}]")
        print(f"    affirmation : {p['affirmation']}")
        print(f"    refutation  : {p['motif']}")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--livre", help="code OSIS, ex. Mark, Rom")
    analyseur.add_argument("--limite", type=int, help="nombre d'unites")
    analyseur.add_argument("--lire", type=int, default=0, help="relire N prises")
    a = analyseur.parse_args()
    asyncio.run(interroger(a.livre, a.limite, a.lire))


if __name__ == "__main__":
    main()
