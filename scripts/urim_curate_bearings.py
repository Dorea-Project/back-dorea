"""Les dix loci pesés sur chaque unité littéraire — **la couche doctrinale**.

    python scripts/urim_curate_bearings.py                 # toutes les unités non pesées
    python scripts/urim_curate_bearings.py --livre Mal     # un livre, pour juger
    python scripts/urim_curate_bearings.py --limite 20     # les 20 premières

Suite de `urim_curate_pericopes.py`, et **dépendant de lui** : une pesée se clé sur une unité.

## Les dix d'un coup, `absent` compris

C'est S38, et le service HTTP l'impose déjà. Une unité sans ligne sur un axe et une unité
marquée `absent` sur cet axe ne disent pas la même chose :

    aucune ligne  →  personne n'a encore regardé
    `absent`      →  quelqu'un a regardé, et le texte n'en dit rien

C'est le seul endroit du produit où le silence porte une information. Écrire six loci sur dix
donnerait une curation à moitié faite qui ressemble à une curation finie.

## Le piège de cette génération, et il n'est pas technique

Un modèle serviable marque tout `porte`. Il aura envie de trouver de la christologie dans un
recensement des Nombres, parce qu'on le lui a demandé et qu'il veut aider. Une curation où
neuf axes sur dix « portent » ne dit plus rien — elle a le volume d'une relecture et le
contenu d'un bruit de fond.

Deux contrepoids sont écrits dans l'invite, et ce sont eux qui décident de la qualité :

- **`absent` est le cas ORDINAIRE.** La plupart des textes ne parlent ni des anges, ni des
  démons, ni de l'Église. Le dire n'est pas un aveu de faiblesse, c'est le travail.
- **`resiste` doit servir.** Un texte qui *complique* un axe n'est pas un texte qui s'en tait,
  et c'est exactement ce que le moteur affiche au même rang que ce qui porte — la seule
  mécanique anti-proof-texting du produit. Un corpus sans aucun `resiste` la laisse éteinte.

Le décompte final imprime la distribution des quatre valeurs. Si `porte` écrase tout, la
génération est à refaire avec une autre invite — et ça se verra, plutôt que de se découvrir
en chaire.

## Ce que ce script n'écrit pas

Ni mises en garde, ni contexte historique, ni faisabilité homilétique. Une pesée dit *sur quel
locus ce texte porte* ; un caveat dit *ce que le texte ne dit pas*, et se trompe plus lourdement.
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
    CorpusDoctrinalAxisModel,
    CorpusDoctrinalBearingModel,
    CorpusPericopeModel,
    CorpusVerseModel,
)
from app.core.config import get_settings
from app.core.database import async_session_factory
from scripts.urim_curate_pericopes import CONCURRENCE, ESSAIS, INTERVALLE, Cadence
from scripts.urim_seed_books import BOOKS

_FORCES = ("dominant", "porte", "resiste", "absent")

_SYSTEME = (
    "Tu es bibliste. On te donne une péricope de la Bible Louis Segond 1910. Pèse-la sur les DIX "
    "loci de la dogmatique classique, dans cet ordre exact : theologie_propre, christologie, "
    "pneumatologie, anthropologie, hamartiologie, soteriologie, ecclesiologie, angelologie, "
    "demonologie, eschatologie. "
    "Pour CHAQUE locus, donne une force parmi : "
    "'dominant' (le locus dont le passage TRAITE — AU PLUS UN, et parfois AUCUN), "
    "'porte' (le passage dit quelque chose de substantiel sur ce locus), "
    "'resiste' (le passage COMPLIQUE ce locus : il le nuance, le tend, ou contredit une lecture "
    "trop simple qu'on en ferait), "
    "'absent' (le passage n'en dit rien). "
    "TROIS RÈGLES QUE TU DOIS SUIVRE CONTRE TON INSTINCT : "
    "(0) Le dominant est ce que le texte ARGUMENTE, jamais ce qu'il MENTIONNE. Test du "
    "retrait : si on ôtait ce locus, le passage perdrait-il son propos ? Une illustration, un "
    "exemple, une incise ne sont JAMAIS dominants — une liste d'exhortations morales qui cite "
    "les anges en exemple d'hospitalité n'a pas l'angélologie pour dominant. Si AUCUN locus "
    "n'est le sujet du passage — une liste, une généalogie, un récit à plusieurs objets — ne "
    "mets AUCUN dominant : c'est une réponse juste et attendue. Et 'theologie_propre' n'est "
    "PAS un défaut : presque tout texte biblique mentionne Dieu, cela n'en fait pas son sujet. "
    "Ne le retiens que si l'action ou la nature de Dieu est ce que le passage soutient. "
    "(1) 'absent' est le cas ORDINAIRE. La plupart des passages ne disent rien des anges, des "
    "démons, de l'Église ou de l'Esprit. Ne cherche pas à trouver quelque chose partout : "
    "marquer 'absent' est une réponse juste et attendue, souvent pour six ou sept locus sur dix. "
    "(2) Utilise 'resiste' quand c'est vrai. Un texte qui complique un locus est précieux — il "
    "empêche de le citer trop vite à l'appui d'une thèse. "
    "Chaque locus porte un motif d'une phrase, y compris 'absent' : dire POURQUOI un texte ne "
    "parle pas d'un locus est aussi utile que de dire qu'il en parle. Le motif s'appuie sur CE "
    "passage, jamais sur ce que tu sais d'ailleurs. "
    'Réponds par un objet JSON : {"pesees": [{"locus": "...", "force": "...", "motif": "..."}]} '
    "avec les dix, dans l'ordre."
)


def _pesees_depuis(contenu: str, loci: set[str]) -> list[dict] | None:
    """Le JSON du modèle → dix pesées vérifiées, ou rien.

    ⚠️ Les mêmes règles que le service HTTP, appliquées ici : les dix loci exactement, aucun
    motif vide. Le script écrit en base directement — s'il était plus permissif que la surface,
    il produirait des unités que la surface elle-même refuserait de corriger. Et il ne doit pas
    être plus **strict** non plus : voir le commentaire sur le dominant, plus bas."""
    bloc = re.search(r"\{.*\}", contenu, re.S)
    if bloc is None:
        return None
    try:
        pesees = json.loads(bloc.group(0)).get("pesees")
    except json.JSONDecodeError:
        return None
    if not isinstance(pesees, list) or len(pesees) != len(loci):
        return None

    propres: list[dict] = []
    vus: set[str] = set()
    for pesee in pesees:
        if not isinstance(pesee, dict):
            return None
        locus, force, motif = pesee.get("locus"), pesee.get("force"), pesee.get("motif")
        if locus not in loci or locus in vus or force not in _FORCES:
            return None
        if not isinstance(motif, str) or not motif.strip():
            return None
        vus.add(locus)
        propres.append({"locus": locus, "force": force, "motif": motif.strip()[:2000]})

    # ⚠️ **On n'exige PAS un dominant, et c'était le défaut le plus coûteux de ce script.**
    #
    # J'imposais « exactement un ». Le modèle rendait dix pesées valides et aucun dominant sur
    # Hébreux 13:1-6 — une liste d'exhortations n'a pas UN sujet —, la validation rejetait, et
    # l'unité était sautée. Ce sont les 803 unités jamais pesées.
    #
    # Pire : là où il s'exécutait, il désignait le détail le plus frappant. L'angélologie
    # dominait Hébreux 13 à cause de « quelques-uns ont logé des anges », et un pasteur qui
    # préparait l'adultère recevait un thème sur les anges.
    #
    # Or `bear_axes` gérait les trois cas depuis le premier jour : un dominant → il continue ;
    # plusieurs → il les rend au même rang ; aucun mais des portants → *« aucun axe ne domine
    # ce texte ; voici ceux qu'il porte »*. **Ma validation était plus stricte que le
    # produit** — j'avais inventé une contrainte que la conception n'avait pas, et elle
    # forçait le moteur à deviner là où il savait demander.
    return propres if vus == loci else None


async def _une_unite(
    ia: MistralAssistant, verrou: asyncio.Semaphore, cadence: Cadence,
    loci: set[str], unite_id: UUID, entete: str, texte: str,
) -> tuple[UUID, list[dict] | None]:
    invite = f"{entete}\n\n{texte}"
    async with verrou:
        for essai in range(ESSAIS):
            await cadence.attendre()
            contenu = await ia.demander(_SYSTEME, invite)
            if contenu:
                pesees = _pesees_depuis(contenu, loci)
                if pesees is not None:
                    return unite_id, pesees
            await asyncio.sleep(2 ** essai)
    return unite_id, None


async def peser(livre_voulu: str | None, limite: int | None) -> None:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        raise SystemExit("MISTRAL_API_KEY absente — rien à faire.")

    par_rang = {rang: (osis, nom) for rang, osis, _, nom, _ in BOOKS}
    ia = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)

    async with async_session_factory() as s:
        loci = {
            a.code for a in (
                await s.execute(select(CorpusDoctrinalAxisModel))
            ).scalars()
        }
        # Les unités **déjà pesées** — par qui que ce soit. On ne repasse jamais dessus : une
        # relecture humaine ne se fait pas écraser par un nouveau passage du modèle.
        pesees_deja = {
            r[0] for r in await s.execute(
                select(CorpusDoctrinalBearingModel.pericope_id).distinct()
            )
        }
        unites = list((await s.execute(select(CorpusPericopeModel))).scalars())

        versets: dict[tuple[int, int, int], str] = {}
        for rang, chapitre, verset, corps in await s.execute(
            select(
                CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                CorpusVerseModel.verse, CorpusVerseModel.body,
            )
        ):
            versets[(rang, chapitre, verset)] = corps

    a_faire = [
        u for u in sorted(unites, key=lambda u: (u.book_id, u.start_ch, u.start_v))
        if u.id not in pesees_deja
        and (livre_voulu is None or par_rang.get(u.book_id, ("", ""))[0] == livre_voulu)
    ]
    if limite is not None:
        a_faire = a_faire[:limite]

    print(f"  {len(unites)} unites, {len(pesees_deja)} deja pesees")
    print(f"  {len(a_faire)} a peser — modele {reglages.mistral_model}\n")
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
        taches.append(_une_unite(ia, verrou, cadence, loci, u.id, entete, corps))

    faites = sautees = 0
    maintenant = datetime.now(UTC)
    distribution: dict[str, int] = dict.fromkeys(_FORCES, 0)
    lot: list[CorpusDoctrinalBearingModel] = []

    for fini in asyncio.as_completed(taches):
        unite_id, pesees = await fini
        if pesees is None:
            sautees += 1
            continue
        for pesee in pesees:
            distribution[pesee["force"]] += 1
            lot.append(CorpusDoctrinalBearingModel(
                pericope_id=unite_id, axis_code=pesee["locus"], strength=pesee["force"],
                rationale=pesee["motif"],
                source_ref=f"Mistral {reglages.mistral_model} sur LSG 1910 — non relu",
                reviewed_by=SIGNATAIRE_IA, reviewed_at=maintenant,
            ))
        faites += 1

        if len(lot) >= 500:
            await _ecrire(lot)
            lot = []
            print(f"  … {faites}/{len(taches)} unites")

    if lot:
        await _ecrire(lot)

    print(f"\n  {faites} unites pesees, {sautees} sautees")
    total = sum(distribution.values()) or 1
    print("  distribution — si « porte » ecrase tout, l'invite est a refaire :")
    for force in _FORCES:
        part = 100 * distribution[force] / total
        print(f"    {force:10} {distribution[force]:>7}  {part:5.1f} %")


async def _ecrire(lot: list[CorpusDoctrinalBearingModel]) -> None:
    async with async_session_factory() as s:
        s.add_all(lot)
        await s.commit()


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--livre", help="code OSIS, ex. Mal, Rom, John")
    analyseur.add_argument("--limite", type=int, help="nombre d'unites a peser")
    arguments = analyseur.parse_args()
    asyncio.run(peser(arguments.livre, arguments.limite))


if __name__ == "__main__":
    main()
