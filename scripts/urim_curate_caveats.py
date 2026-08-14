"""Les mises en garde — **ce que le texte ne dit pas**.

    python scripts/urim_curate_caveats.py                 # toutes les unités sans caveat
    python scripts/urim_curate_caveats.py --livre Mal     # un livre, pour juger
    python scripts/urim_curate_caveats.py --limite 20

C'est la dimension qui protège le pasteur en chaire, et elle était à **0,1 %** : six lignes
posées à la main sur 4 561 unités. Les six disent l'intention mieux qu'une spécification —
2 Corinthiens 9 y porte la garde contre l'évangile de prospérité : *« sème abondamment » vise
une collecte pour les saints de Jérusalem ; le texte ne promet aucun retour matériel au
donateur.*

## Deux espèces, et la seconde ne prend jamais parti

**Exégétique** — le texte ne précise pas, le narrateur ne juge pas, la promesse est bornée à sa
situation. Aucune tradition en cause.

**Confessionnel** — *« ici les traditions divergent »*, jamais *« votre tradition dit X »*. La
contrainte `confessionnel_borne` l'exige en base : un caveat confessionnel sans tradition est
refusé par le schéma. Il s'affiche pourtant toujours, y compris quand la tradition de l'église
est inconnue — c'est la formulation qui le rend possible.

## Trois interdits écrits dans l'invite, et ce sont eux qui décident de la qualité

**Zéro mise en garde est une réponse juste.** Beaucoup de passages ne portent aucun piège.
Exiger une ligne par unité produirait 4 561 avertissements dont personne ne lirait le
quatre-vingtième — le volume d'une relecture et le contenu d'un bruit de fond. Même leçon que
`absent` sur les pesées.

**Aucune variante textuelle.** Le modèle affirmera volontiers que « certains manuscrits
ajoutent… » et il inventera. Les variantes ont leur table, alimentée par un apparat critique ;
un caveat qui en parle doit venir d'un humain. C'est la seule limite de ce lot qui restera après
lui.

**La source est le passage, jamais une autorité.** Pas de NA28, pas de commentaire, pas de
concile : le modèle ne peut pas être vérifié dessus. `source_ref` porte donc les versets du
passage — ce qui rend chaque mise en garde contrôlable en la relisant.

## Ce que ce lot fait de neuf : le modèle voit la curation

Jusqu'ici les invites d'Urim ne montraient au modèle que la phrase du pasteur ou le texte brut.
Ici on lui passe **les pesées déjà curées** de l'unité — quels loci elle porte, lequel domine,
lesquels résistent. Une mise en garde qui ignorerait la lecture doctrinale déjà établie
parlerait d'un autre texte que celui qu'Urim affichera.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.contexts.urim.application.curation import (
    SIGNATAIRE_IA,
    verifier_forme_machine,
)
from app.contexts.urim.domain.errors import CurationInvalideError
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusExaminationModel,
    CorpusPericopeModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.config import get_settings
from app.core.database import async_session_factory
from scripts.urim_curate_pericopes import CONCURRENCE, ESSAIS, INTERVALLE, Cadence
from scripts.urim_ecarts import VERSION_DE_CURATION
from scripts.urim_seed_books import BOOKS

_ESPECES = ("exegetique", "confessionnel")

#: La dimension au registre d'examen — c'est elle qui rend ce lot reprenable.
_DIMENSION = "caveat"

#: ⚠️ **Fermé**, comme les loci. Une tradition inventée deviendrait une étiquette que personne
#: ne revendique, collée à une divergence que personne ne conteste.
_TRADITIONS = frozenset({
    "reformee", "lutherienne", "catholique", "orthodoxe",
    "arminienne", "pentecotiste", "wesleyenne", "baptiste",
})

#: 🔴 **Deux, et le chiffre vient de l'étalon — pas de mon intuition.**
#:
#: Il était à trois, et la distribution a montré ce que ça produisait : sur 4 449 unités,
#: 48 % à zéro, **12 unités à une**, 27 % à deux, 25 % à trois. Un modèle qui jugerait au
#: mérite donnerait une pente ; ce trou à un est la signature d'un quota rempli.
#:
#: Les six mises en garde posées **à la main** disent la forme juste : quatre unités en portent
#: deux, deux en portent une, aucune n'en porte trois. Un pasteur qui prépare lit un
#: avertissement, éventuellement deux ; au troisième il ne les hiérarchise plus.
_MAX_PAR_UNITE = 2

_SYSTEME = (
    "Tu es bibliste. On te donne une péricope de la Bible Louis Segond 1910 et la lecture "
    "doctrinale déjà établie sur elle. Ta tâche est de relever les MISES EN GARDE : ce que le "
    "texte NE DIT PAS, et qu'un prédicateur pressé lui ferait dire.\n"
    "Deux espèces, et une seule peut nommer des traditions :\n"
    "- 'exegetique' : le passage ne précise pas un point, le narrateur ne porte aucun jugement, "
    "une formule est dense et son mécanisme n'est pas expliqué, une promesse est bornée à sa "
    "situation et n'énonce pas une loi générale. Pas de tradition.\n"
    "- 'confessionnel' : les traditions chrétiennes divergent sur ce point, et le texte ne "
    "tranche pas. Tu écris « ici les traditions divergent », JAMAIS « telle tradition a tort » "
    "ni « votre tradition dit ». Tu nommes AU MOINS DEUX traditions parmi exactement : "
    f"{', '.join(sorted(_TRADITIONS))}.\n"
    "SIX RÈGLES QUE TU DOIS SUIVRE CONTRE TON INSTINCT :\n"
    "(0) LE TEST QUI DÉCIDE DE TOUT — n'écris une mise en garde que si un prédicateur "
    "affirmerait PLAUSIBLEMENT le contraire depuis une chaire. « La postérité de la femme "
    "n'est pas explicitement identifiée comme le Christ » est une bonne mise en garde : on le "
    "prêche partout, et le texte ne le dit pas. « Le texte ne détaille pas les conséquences "
    "sociales de cette union » n'en est pas une : personne ne prêche le contraire, et le "
    "constat ne sert à rien. Tout texte laisse mille choses non précisées ; seules comptent "
    "celles qu'on lui fait dire.\n"
    "(1) ZÉRO EST LE CAS LE PLUS FRÉQUENT, ET DE LOIN. La plupart des passages ne portent "
    "aucun piège : un récit, une généalogie, un miracle raconté simplement, une exhortation "
    "claire n'appellent AUCUNE mise en garde. Rendre une liste vide est la bonne réponse plus "
    "d'une fois sur deux. Ne cherche pas un piège pour en trouver un.\n"
    "(2) SI, ET SEULEMENT SI, le passage en porte un, écris-en UNE : la principale. Deux est un "
    "maximum réservé aux textes qui portent deux pièges vraiment distincts. N'écris jamais une "
    "seconde ligne pour étoffer la première.\n"
    "(3) N'invente JAMAIS de variante textuelle ni de manuscrit. N'écris jamais « certains "
    "manuscrits ajoutent », « les éditions divergent », « l'apparat critique ». C'est "
    "formellement interdit, même si tu crois te souvenir d'une variante.\n"
    "(4) Ne cite AUCUNE autorité extérieure : pas de commentateur, pas d'édition critique, pas "
    "de concile, pas de confession de foi. Ton seul appui est le passage qu'on te donne.\n"
    "(5) Une mise en garde dit ce que le texte NE DIT PAS. Elle ne prêche pas, elle ne corrige "
    "pas le lecteur, elle n'affirme aucune doctrine, et surtout elle ne NIE aucune doctrine : "
    "écrire qu'un passage « ne présente pas la faute comme universelle » revient à trancher "
    "une question que le reste de l'Écriture traite ailleurs. Dis que CE passage ne le dit "
    "pas, jamais que la chose n'est pas. Une ou deux phrases sobres.\n"
    "Chaque mise en garde porte le locus concerné, parmi ceux de la lecture doctrinale fournie. "
    'Réponds par un objet JSON : {"gardes": [{"locus": "...", "espece": "...", '
    '"traditions": [...], "corps": "..."}]} — au plus DEUX, et la liste peut être vide.'
)

#: 🔴 **La distribution a dit que le plafond n'était pas le sujet.**
#:
#: Sur 4 207 unités : 46 % à zéro, **11 unités à une**, 28 % à deux, 26 % à trois. Un modèle
#: qui jugerait chaque texte au mérite donnerait une pente ; ce trou à un est la signature d'un
#: quota. Le modèle ne comptait pas les pièges, il décidait « ce texte mérite-t-il des mises en
#: garde ? » puis remplissait. Baisser le plafond à deux aurait déplacé la masse sur deux.
#:
#: La règle (1) nomme donc la forme attendue — **une seule, presque toujours** — au lieu de
#: borner un maximum. C'est ce qui avait marché pour les pesées avec « `absent` est le cas
#: ORDINAIRE ».
_ATTENDU = "0 souvent · 1 quand il y en a · 2 rare · 3 exceptionnel"


def _gardes_depuis(contenu: str, loci_permis: set[str]) -> list[dict] | None:
    """Le JSON du modèle → des mises en garde vérifiées, ou rien.

    ⚠️ **Une liste vide est un succès**, pas un échec : c'est la réponse attendue sur la plupart
    des textes. La distinguer d'un refus de parser est tout l'objet du `None`."""
    bloc = re.search(r"\{.*\}", contenu, re.S)
    if bloc is None:
        return None
    try:
        gardes = json.loads(bloc.group(0)).get("gardes")
    except json.JSONDecodeError:
        return None
    if not isinstance(gardes, list):
        return None

    propres: list[dict] = []
    for garde in gardes[:_MAX_PAR_UNITE]:
        if not isinstance(garde, dict):
            continue
        locus, espece = garde.get("locus"), garde.get("espece")
        corps = garde.get("corps")
        if locus not in loci_permis or espece not in _ESPECES:
            continue
        if not isinstance(corps, str) or len(corps.strip()) < 20:
            continue
        # ⚠️ Le garde-fou qui compte, et il vient désormais de `curation.py` — la même règle
        # que la route Plateforme applique. Recopiée ici, elle aurait divergé le jour où l'une
        # des deux aurait été corrigée. L'interdit d'invite n'est pas une garantie ; celui-ci
        # l'est, et il est unique.
        try:
            verifier_forme_machine(corps, SIGNATAIRE_IA)
        except CurationInvalideError:
            continue

        traditions = garde.get("traditions")
        if espece == "confessionnel":
            retenues = sorted(
                {t for t in traditions if t in _TRADITIONS}
                if isinstance(traditions, list) else set()
            )
            # Une divergence exige au moins deux partis. Un seul nommé serait un procès.
            if len(retenues) < 2:
                continue
        else:
            retenues = None

        propres.append({
            "locus": locus, "espece": espece,
            "traditions": retenues, "corps": corps.strip()[:2000],
        })
    return propres


async def _une_unite(
    ia: MistralAssistant, verrou: asyncio.Semaphore, cadence: Cadence,
    loci_permis: set[str], unite_id: UUID, invite: str,
) -> tuple[UUID, list[dict] | None]:
    async with verrou:
        for essai in range(ESSAIS):
            await cadence.attendre()
            contenu = await ia.demander(_SYSTEME, invite, etiquette="caveats")
            if contenu:
                gardes = _gardes_depuis(contenu, loci_permis)
                if gardes is not None:
                    return unite_id, gardes
            await asyncio.sleep(2**essai)
    return unite_id, None


async def curer(livre_voulu: str | None, limite: int | None, purge: bool) -> None:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        raise SystemExit("MISTRAL_API_KEY absente — rien à faire.")

    if purge:
        # ⚠️ **Seulement ce que l'IA a écrit.** Les six lignes posées à la main disent
        # l'intention du produit ; les effacer pour reprendre un essai serait perdre l'étalon.
        #
        # Et **bornée par `--livre`**, sans quoi éprouver une invite sur un livre effacerait la
        # curation des soixante-cinq autres — une heure de modèle pour juger un réglage.
        async with async_session_factory() as s:
            portee = []
            if livre_voulu:
                rangs = [r for r, osis, *_ in BOOKS if osis == livre_voulu]
                if not rangs:
                    raise SystemExit(f"  livre inconnu : {livre_voulu}")
                unites_du_livre = select(CorpusPericopeModel.id).where(
                    CorpusPericopeModel.book_id == rangs[0]
                )
                portee = [CorpusDoctrinalCaveatModel.pericope_id.in_(unites_du_livre)]
            await s.execute(
                delete(CorpusDoctrinalCaveatModel).where(
                    CorpusDoctrinalCaveatModel.reviewed_by == SIGNATAIRE_IA, *portee
                )
            )
            # ⚠️ Et son registre d'examen, sinon la purge serait un piège : les unités
            # resteraient marquées « examinées » et la relance ne ferait rien du tout.
            portee_examen = []
            if livre_voulu:
                portee_examen = [
                    CorpusExaminationModel.pericope_id.in_(
                        select(CorpusPericopeModel.id).where(
                            CorpusPericopeModel.book_id == rangs[0]
                        )
                    )
                ]
            await s.execute(
                delete(CorpusExaminationModel).where(
                    CorpusExaminationModel.dimension == _DIMENSION,
                    CorpusExaminationModel.examined_by == SIGNATAIRE_IA,
                    *portee_examen,
                )
            )
            await s.commit()
        print("  mises en garde de l'IA effacees — les 6 relues a la main sont gardees\n")

    par_rang = {rang: (osis, nom) for rang, osis, _, nom, _ in BOOKS}
    ia = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)

    async with async_session_factory() as s:
        # ⚠️ **On saute ce qui a été EXAMINÉ, pas ce qui porte une trouvaille.**
        #
        # 🔴 Le premier lot se fondait sur la présence d'une mise en garde. Les 2 525 unités
        # où le modèle avait justement répondu « rien à signaler » repassaient donc à chaque
        # relance : rattraper 106 unités sautées en aurait refait 2 631, et le second passage
        # aurait rendu d'autres résultats sur des unités déjà jugées, sans qu'on sache
        # lesquelles croire.
        deja = {
            r[0] for r in await s.execute(
                select(CorpusExaminationModel.pericope_id).where(
                    CorpusExaminationModel.dimension == _DIMENSION
                )
            )
        }
        # Les six mises en garde posées à la main précèdent le registre : leur unité est
        # examinée, quoi qu'en dise une table créée après elles.
        deja |= {
            r[0] for r in await s.execute(
                select(CorpusDoctrinalCaveatModel.pericope_id).distinct()
            )
        }
        unites = list((await s.execute(select(CorpusPericopeModel))).scalars())

        #: La lecture doctrinale déjà curée, montrée au modèle. Sans elle, la mise en garde
        #: parlerait d'un autre texte que celui qu'Urim affiche.
        pesees: dict[UUID, list[tuple[str, str, str]]] = {}
        for unite_id, axe, force, motif in await s.execute(
            select(
                CorpusDoctrinalBearingModel.pericope_id,
                CorpusDoctrinalBearingModel.axis_code,
                CorpusDoctrinalBearingModel.strength,
                CorpusDoctrinalBearingModel.rationale,
            ).where(CorpusDoctrinalBearingModel.strength != "absent")
        ):
            pesees.setdefault(unite_id, []).append((axe, force, motif))

        # 🔴 **Le filtre de version, dont l'absence n'aurait rien signalé du tout.**
        #
        # Ce dictionnaire est indexé sur (livre, chapitre, verset) **sans la version**. Le
        # corpus en porte quatre — LSG, Darby, Ostervald, Martin 1744 — et chacune écrit sur la
        # clé de la précédente : le texte servi au modèle devenait un panachage que seul l'ordre
        # physique de la table décidait, pendant que `source_ref` signait « LSG 1910 » dessous.
        #
        # ⚠️ **Ce lot-ci a été épargné par le calendrier, pas par le code.** Les numéros de
        # transaction le disent sans reconstitution : les 2 392 mises en garde ont été écrites
        # sous les xid 5378-5422, Darby est entrée en base à 5407, Ostervald à 5427, Martin à
        # 5451. La lecture des versets précède la première écriture — le modèle n'a donc vu que
        # la Segond, et rien n'est à refaire. C'est la relance suivante qui aurait servi du
        # français de 1744, et un `--purge` aurait retourné les 4 508 unités du corpus.
        #
        # C'est le même défaut que D5 avait déjà payé dans `urim_ecarts.py` : **ajouter une
        # traduction au corpus casse en silence tout ce qui lit les versets sans se nommer.**
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
        # Sans elle, `corps` serait vide sur chaque invite et le modèle rendrait des mises en
        # garde sur un passage qu'il n'a pas lu — une panne qui coûte un lot entier en silence.
        if not versets:
            raise SystemExit(f"  aucun verset en {VERSION_DE_CURATION} — corpus non chargé.")

    a_faire = [
        u for u in sorted(unites, key=lambda u: (u.book_id, u.start_ch, u.start_v))
        if u.id not in deja
        and u.id in pesees  # sans pesée, on n'a rien à montrer au modèle
        and (livre_voulu is None or par_rang.get(u.book_id, ("", ""))[0] == livre_voulu)
    ]
    if limite is not None:
        a_faire = a_faire[:limite]

    print(f"  {len(unites)} unites, {len(deja)} en portent deja")
    print(f"  {len(a_faire)} a curer — modele {reglages.mistral_model}\n")
    if not a_faire:
        return

    verrou = asyncio.Semaphore(CONCURRENCE)
    cadence = Cadence(INTERVALLE)
    taches = []
    references: dict[UUID, str] = {}
    for u in a_faire:
        nom = par_rang.get(u.book_id, ("", "?"))[1]
        reference = f"{nom} {u.start_ch}:{u.start_v}-{u.end_v}"
        references[u.id] = reference
        corps = "\n".join(
            f"{n}. {versets[(u.book_id, u.start_ch, n)]}"
            for n in range(u.start_v, u.end_v + 1)
            if (u.book_id, u.start_ch, n) in versets
        )
        lecture = "\n".join(
            f"- {axe} ({force}) : {motif}" for axe, force, motif in pesees[u.id]
        )
        invite = (
            f"{reference} — « {u.label or 'sans titre'} »\n\n{corps}\n\n"
            f"LECTURE DOCTRINALE DEJA ETABLIE :\n{lecture}"
        )
        loci_permis = {axe for axe, _, _ in pesees[u.id]}
        taches.append(_une_unite(ia, verrou, cadence, loci_permis, u.id, invite))

    faites = sautees = 0
    sans_garde = 0
    distribution = dict.fromkeys(_ESPECES, 0)
    maintenant = datetime.now(UTC)
    lot: list[CorpusDoctrinalCaveatModel | CorpusExaminationModel] = []

    for fini in asyncio.as_completed(taches):
        unite_id, gardes = await fini
        if gardes is None:
            # Une panne n'est pas un examen : l'unité doit revenir au prochain passage.
            sautees += 1
            continue
        faites += 1
        lot.append(CorpusExaminationModel(
            pericope_id=unite_id, dimension=_DIMENSION, found=len(gardes),
            examined_by=SIGNATAIRE_IA, examined_at=maintenant,
        ))
        if not gardes:
            sans_garde += 1
            continue
        for garde in gardes:
            distribution[garde["espece"]] += 1
            lot.append(CorpusDoctrinalCaveatModel(
                id=uuid4(), pericope_id=unite_id, axis_code=garde["locus"],
                body=garde["corps"], caveat_kind=garde["espece"],
                tradition_scope=garde["traditions"],
                source_ref=f"{references[unite_id]} (LSG 1910) — non relu",
                reviewed_by=SIGNATAIRE_IA, reviewed_at=maintenant,
            ))
        if len(lot) >= 400:
            await _ecrire(lot)
            lot = []
            print(f"  … {faites}/{len(taches)} unites")

    if lot:
        await _ecrire(lot)

    print(f"\n  {faites} unites curees, {sautees} sautees")
    print(f"  {sans_garde} sans aucune mise en garde "
          f"({100 * sans_garde / (faites or 1):.0f} %) — c'est une reponse juste")
    total = sum(distribution.values()) or 1
    print("  espece — si 'confessionnel' ecrase tout, l'invite prend parti :")
    for espece in _ESPECES:
        print(f"    {espece:14} {distribution[espece]:>6}  "
              f"{100 * distribution[espece] / total:5.1f} %")


async def _ecrire(lot: list[CorpusDoctrinalCaveatModel | CorpusExaminationModel]) -> None:
    async with async_session_factory() as s:
        s.add_all(lot)
        await s.commit()


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--livre", help="code OSIS, ex. Mal, Rom, John")
    analyseur.add_argument("--limite", type=int, help="nombre d'unites")
    analyseur.add_argument(
        "--purge", action="store_true",
        help="efface les mises en garde de l'IA (jamais celles relues a la main)",
    )
    arguments = analyseur.parse_args()
    asyncio.run(curer(arguments.livre, arguments.limite, arguments.purge))


if __name__ == "__main__":
    main()
