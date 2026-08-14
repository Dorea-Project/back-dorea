"""Les 18 couples plan x matiere, pesés sur chaque unité — **la faisabilité homilétique**.

    python scripts/urim_curate_feasibility.py                 # toutes les unités
    python scripts/urim_curate_feasibility.py --livre Mal     # un livre, pour juger
    python scripts/urim_curate_feasibility.py --limite 20

Troisième couche, après le découpage et les pesées. Elle répond à une question que le pasteur
se pose vraiment : *ce texte supporte-t-il le sermon que j'ai en tête ?*

## Un refus voyage avec son motif, toujours

`refus_motive` en base l'impose : `feasible = false` sans `refusal_reason` est rejeté par
PostgreSQL. C'est la même règle partout dans Urim — *un refus muet est un refus qu'on ne peut
pas contester*. Et l'étage 6 affiche les refusés **avec** les faisables, parce que les cacher
laisserait le pasteur croire qu'on n'y a pas pensé.

## Les 18, et pas seulement les possibles

La surface HTTP n'exige pas la complétude ici, contrairement aux dix loci. On l'impose quand
même : un couple manquant serait indiscernable d'un oubli, alors qu'un couple présent et refusé
dit quelque chose. C'est le même raisonnement que `absent` pour les pesées.

## Le risque de proof-texting n'est pas une propriété du texte

Il est porté par le **triplet** — le passage, le plan, la matière. Le thématique est
structurellement plus risqué que l'expositif, parce que les textes y sont convoqués pour
confirmer une idée décidée d'avance plutôt que suivis dans leur ordre. L'invite le dit, sinon
le modèle rend « faible » partout et l'information disparaît.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.contexts.urim.application.curation import SIGNATAIRE_IA
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusHomileticFeasibilityModel,
    CorpusPericopeModel,
    CorpusPlanSourceModel,
    CorpusSubjectMatterModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.config import get_settings
from app.core.database import async_session_factory
from scripts.urim_curate_pericopes import CONCURRENCE, ESSAIS, INTERVALLE, Cadence
from scripts.urim_ecarts import VERSION_DE_CURATION
from scripts.urim_seed_books import BOOKS

_RISQUES = ("faible", "moyen", "eleve")

_SYSTEME = (
    "Tu es homilète. On te donne une péricope de la Bible Louis Segond 1910. Dis, pour CHACUN "
    "des 18 couples possibles, si un sermon de cette forme tient sur CE passage. "
    "Les 3 sources de plan : 'textuel' (le plan suit le mouvement du texte verset par verset), "
    "'expositif' (le plan expose l'unité entière dans son ordre), 'thematique' (le plan part "
    "d'une idée et convoque le texte). "
    "Les 6 matières : 'biographique' (un personnage), 'doctrinal' (une doctrine), 'ethique' (une "
    "conduite), 'historique' (un événement), 'typologique' (une figure qui en annonce une autre), "
    "'prophetique' (une annonce). "
    "Pour chaque couple : faisable (booléen), motif_refus (obligatoire si faisable est faux — "
    "dis ce qui MANQUE AU TEXTE, jamais ce qui manque au prédicateur : 'ce passage ne porte "
    "aucun personnage', pas 'vous manquez de matière'), et risque de proof-texting parmi "
    "'faible', 'moyen', 'eleve'. "
    "DEUX RÈGLES : (1) refuse franchement. Un récit sans personnage nommé ne supporte pas un "
    "sermon biographique, et le dire est utile ; répondre 'faisable' partout ne rend service à "
    "personne. (2) Le risque appartient au COUPLE, pas au texte : 'thematique' est "
    "structurellement plus risqué que 'expositif', parce que le texte y est convoqué pour "
    "confirmer une idée décidée d'avance au lieu d'être suivi. Ne mets pas 'faible' partout. "
    'Réponds par un objet JSON : {"couples": [{"plan": "...", "matiere": "...", '
    '"faisable": true, "motif_refus": "", "risque": "..."}]} avec les 18.'
)


def _couples_depuis(contenu: str, plans: set[str], matieres: set[str]) -> list[dict] | None:
    """Le JSON du modèle → 18 couples vérifiés, ou rien.

    ⚠️ `refus_motive` est une contrainte PostgreSQL : un refus sans motif ferait échouer
    l'insertion de tout le lot, pas seulement de la ligne fautive. On l'attrape ici, où l'on
    sait encore de quel chapitre il s'agit."""
    bloc = re.search(r"\{.*\}", contenu, re.S)
    if bloc is None:
        return None
    try:
        couples = json.loads(bloc.group(0)).get("couples")
    except json.JSONDecodeError:
        return None
    attendus = {(p, m) for p in plans for m in matieres}
    if not isinstance(couples, list) or len(couples) != len(attendus):
        return None

    propres: list[dict] = []
    vus: set[tuple[str, str]] = set()
    for couple in couples:
        if not isinstance(couple, dict):
            return None
        plan, matiere = couple.get("plan"), couple.get("matiere")
        risque, faisable = couple.get("risque"), couple.get("faisable")
        if (plan, matiere) not in attendus or (plan, matiere) in vus:
            return None
        if risque not in _RISQUES or not isinstance(faisable, bool):
            return None
        motif = (couple.get("motif_refus") or "").strip()
        if not faisable and not motif:
            return None  # `refus_motive` en base — un refus muet ne se conteste pas
        vus.add((plan, matiere))
        propres.append({
            "plan": plan, "matiere": matiere, "faisable": faisable,
            "motif": motif[:1000], "risque": risque,
        })

    return propres if vus == attendus else None


async def _une_unite(
    ia: MistralAssistant, verrou: asyncio.Semaphore, cadence: Cadence,
    plans: set[str], matieres: set[str], unite_id: UUID, entete: str, texte: str,
) -> tuple[UUID, list[dict] | None]:
    invite = f"{entete}\n\n{texte}"
    async with verrou:
        for essai in range(ESSAIS):
            await cadence.attendre()
            contenu = await ia.demander(_SYSTEME, invite)
            if contenu:
                couples = _couples_depuis(contenu, plans, matieres)
                if couples is not None:
                    return unite_id, couples
            await asyncio.sleep(2 ** essai)
    return unite_id, None


async def evaluer(livre_voulu: str | None, limite: int | None) -> None:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        raise SystemExit("MISTRAL_API_KEY absente — rien à faire.")

    par_rang = {rang: (osis, nom) for rang, osis, _, nom, _ in BOOKS}
    ia = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)

    async with async_session_factory() as s:
        plans = {p.code for p in (await s.execute(select(CorpusPlanSourceModel))).scalars()}
        matieres = {
            m.code for m in (await s.execute(select(CorpusSubjectMatterModel))).scalars()
        }
        deja = {
            r[0] for r in await s.execute(
                select(CorpusHomileticFeasibilityModel.pericope_id).distinct()
            )
        }
        unites = list((await s.execute(select(CorpusPericopeModel))).scalars())

        # 🔴 **Nommer la version, parce que la clé ne la porte pas.**
        #
        # Les quatre traductions du corpus partagent la clé (livre, chapitre, verset) : sans ce
        # filtre, la dernière lue écrase les trois autres et c'est l'ordre physique de la table
        # qui choisit le texte servi au modèle.
        #
        # Ici le dégât aurait été le plus silencieux des trois lots. Une faisabilité ne cite
        # rien et n'écrit aucun motif : elle rend dix-huit `oui/non`. Aucun détecteur de
        # `urim_ecarts.py` ne peut la contredire — pas de citation à comparer, pas de tournure à
        # compter. Elle serait entrée fausse et serait restée vraie pour tout le monde.
        #
        # ⚠️ Les 81 943 lignes en base ont été écrites sous les xid 4739-5267, Darby est entrée
        # à 5407 : elles ont lu de la Segond pure et **rien n'est à refaire**.
        versets: dict[tuple[int, int, int], str] = {}
        for rang, chapitre, verset, corps in await s.execute(
            select(
                CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                CorpusVerseModel.verse, CorpusVerseModel.body,
            )
            .join(CorpusVersionModel, CorpusVersionModel.id == CorpusVerseModel.version_id)
            .where(CorpusVersionModel.code == VERSION_DE_CURATION)
        ):
            versets[(rang, chapitre, verset)] = corps
        # Sur un corpus non chargé, le modèle jugerait dix-huit formes de sermon sur un passage
        # vide — et rendrait dix-huit verdicts qu'aucune relecture ne saurait attraper.
        if not versets:
            raise SystemExit(f"  aucun verset en {VERSION_DE_CURATION} — corpus non chargé.")

    a_faire = [
        u for u in sorted(unites, key=lambda u: (u.book_id, u.start_ch, u.start_v))
        if u.id not in deja
        and (livre_voulu is None or par_rang.get(u.book_id, ("", ""))[0] == livre_voulu)
    ]
    if limite is not None:
        a_faire = a_faire[:limite]

    print(f"  {len(unites)} unites, {len(deja)} deja evaluees")
    print(f"  {len(a_faire)} a evaluer — modele {reglages.mistral_model}\n")
    if not a_faire:
        return

    verrou = asyncio.Semaphore(CONCURRENCE)
    cadence = Cadence(INTERVALLE)
    taches = []
    for u in a_faire:
        nom = par_rang.get(u.book_id, ("", "?"))[1]
        corps = "\n".join(
            f"{n}. {versets[(u.book_id, u.start_ch, n)]}"
            for n in range(u.start_v, u.end_v + 1)
            if (u.book_id, u.start_ch, n) in versets
        )
        entete = f"{nom} {u.start_ch}:{u.start_v}-{u.end_v} — « {u.label or 'sans titre'} »"
        taches.append(
            _une_unite(ia, verrou, cadence, plans, matieres, u.id, entete, corps)
        )

    faites = sautees = 0
    maintenant = datetime.now(UTC)
    refuses = 0
    risques: dict[str, int] = dict.fromkeys(_RISQUES, 0)
    lot: list[CorpusHomileticFeasibilityModel] = []

    for fini in asyncio.as_completed(taches):
        unite_id, couples = await fini
        if couples is None:
            sautees += 1
            continue
        for couple in couples:
            refuses += not couple["faisable"]
            risques[couple["risque"]] += 1
            lot.append(CorpusHomileticFeasibilityModel(
                pericope_id=unite_id, plan_source=couple["plan"],
                subject_matter=couple["matiere"], feasible=couple["faisable"],
                refusal_reason=couple["motif"] or None,
                proof_text_risk=couple["risque"],
                # ⚠️ Pas de `source_ref` ici : cette table n'en porte pas, contrairement aux
                # péricopes et aux pesées. Je l'avais recopié du script voisin et le semis est
                # tombé au premier lot — la provenance tient donc au seul `reviewed_by`.
                reviewed_by=SIGNATAIRE_IA, reviewed_at=maintenant,
            ))
        faites += 1

        if len(lot) >= 900:
            await _ecrire(lot)
            lot = []
            print(f"  … {faites}/{len(taches)} unites")

    if lot:
        await _ecrire(lot)

    total = sum(risques.values()) or 1
    print(f"\n  {faites} unites evaluees, {sautees} sautees")
    print(f"  {refuses}/{total} couples refuses ({100 * refuses / total:.1f} %)")
    print("  risque de proof-texting — si « faible » ecrase tout, l'invite est a refaire :")
    for risque in _RISQUES:
        print(f"    {risque:8} {risques[risque]:>7}  {100 * risques[risque] / total:5.1f} %")


async def _ecrire(lot: list[CorpusHomileticFeasibilityModel]) -> None:
    async with async_session_factory() as s:
        s.add_all(lot)
        await s.commit()


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--livre", help="code OSIS, ex. Mal, Rom, John")
    analyseur.add_argument("--limite", type=int, help="nombre d'unites a evaluer")
    arguments = analyseur.parse_args()
    asyncio.run(evaluer(arguments.livre, arguments.limite))


if __name__ == "__main__":
    main()
