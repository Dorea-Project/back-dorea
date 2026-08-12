"""Le détecteur d'écarts — **il ne dit pas ce qui est vrai, il dit ce qui est suspect**.

    python scripts/urim_ecarts.py                # les cinq balayages gratuits
    python scripts/urim_ecarts.py --detail 15    # les exemples, en entier
    python scripts/urim_ecarts.py --file         # la file d'attente du relecteur

Un humain ne relira jamais 4 561 unités. Il peut en relire deux cents — si quelque chose sait
lui dire **lesquelles**. C'est tout l'objet de ce script, et c'est ce qui transforme une
relecture infinie en relecture bornée.

⚠️ **Aucun de ces détecteurs ne sait si une pesée est théologiquement juste.** Ils savent
qu'elle est incohérente, formulaire, aberrante, ou qu'elle cite un texte qui n'existe pas.
C'est beaucoup, et ce n'est pas la même chose. Ce qu'ils produisent est une **file d'attente
ordonnée**, du plus douteux au moins ; le corpus n'est jamais « fini », il est traçable.

## Les cinq balayages, et pourquoi ils sont gratuits

**D1 — la contradiction interne.** Une mise en garde posée sur un locus que les pesées ont
marqué `absent`. Deux générations indépendantes sur la même unité *doivent* s'accorder ; quand
elles divergent, l'une des deux a tort et on ne sait pas laquelle. C'est le signal le plus fort
du lot, et il ne coûte rien parce que les deux couches existent déjà.

**D2 — le gabarit.** La Bible a mille tournures ; la curation ne devrait pas en avoir douze. Si
la même formule revient sur des centaines d'unités, ce n'est plus une lecture, c'est un moule.

**D3 — la forme interdite.** Manuscrit, apparat, autorité extérieure, et surtout la négation
d'une doctrine — *« ce passage ne présente pas la faute comme universelle »* borne un texte en
apparence et tranche une question de fond en réalité.

**D4 — l'aberration.** Une unité dont le profil s'écarte de ses semblables : neuf loci portants
quand la médiane est à deux, trois mises en garde là où 75 % n'en ont aucune.

**D5 — la citation fantôme.** Une ligne qui cite « … » des mots absents du passage. C'est le
seul détecteur qui attrape une invention pure, et il est exact : le texte est en base.

Le sixième — repasser la ligne au modèle en lui demandant de la **réfuter** — coûte un appel par
unité suspecte. Il ne se lance que sur ce que les cinq premiers ont laissé passer, et il n'est
pas dans ce script : on regarde d'abord ce que le gratuit trouve.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.urim.application.curation import (
    PORTEE_ENSEMBLE,
    SIGNATAIRE_IA,
    empreinte_de_curation,
)
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusPericopeModel,
    CorpusReviewModel,
    CorpusVerseModel,
)
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS

#: Une formule qui revient sur au moins tant d'unités n'est plus une lecture, c'est un moule.
#:
#: 🔴 **Premier réglage : 25, et D2 signalait 99,9 % du corpus.** Le détecteur avait tort, et
#: pour une raison qui valait d'être trouvée : les motifs d'`absent` sont formulaires **par
#: nature**. « L'Esprit de Dieu n'est pas présenté dans ce passage » revient 937 fois parce
#: que c'est vrai 937 fois. Une curation qui dit neuf fois sur dix qu'un locus est muet ne peut
#: pas le dire de neuf cents façons, et n'a aucune raison de le faire.
#:
#: D2 ne regarde donc plus que ce qui **affirme** quelque chose : les pesées portantes et les
#: mises en garde. Là, une formule partagée est un vrai symptôme.
_SEUIL_GABARIT = 60

#: Un moule ne se mesure pas à sa présence mais à sa **couverture** : une ligne qui contient
#: une tournure commune reste une lecture ; une ligne qui n'est *que* de la tournure commune
#: est un remplissage. C'est la part des mots de la ligne appartenant à un gabarit.
_COUVERTURE_GABARIT = 0.6

#: La longueur de l'empreinte de formule. Six mots : assez pour qu'une coïncidence soit
#: improbable, assez court pour attraper un gabarit dont la fin varie.
_EMPREINTE = 6

#: Au-delà, l'unité « porte » presque tous les loci — le modèle a voulu être serviable.
_LOCI_PORTANTS_MAX = 7

#: ⚠️ **Ce sont les règles de la MACHINE, pas celles du corpus.**
#:
#: 🔴 Le premier passage a signalé Romains 8:1-11 — l'une des six mises en garde posées **à la
#: main**, celle qui cite le Texte Reçu et la variante du v. 1. Elle est juste : un humain peut
#: consulter un apparat critique et en répondre. Le modèle, non — il inventera la variante et
#: personne ne le verra.
#:
#: Ces détecteurs ne s'appliquent donc qu'aux lignes signées par l'IA. Les appliquer à tout
#: aurait mis en tête de file la seule ligne du corpus dont on est sûr.
_FORMES_INTERDITES = (
    ("manuscrit", r"manuscrit|apparat|codex|texte re[çc]u|le[çc]on variante"),
    # 🔴 Deux faux positifs successifs sur ce seul motif, et ils disent la même chose : une
    # règle qui devine se trompe. « confession de foi » décrit ce qu'un passage EST
    # (Deutéronome 26 en est une) ; exiger une majuscule après « de » a ensuite attrapé
    # « confession de Jésus », qui est du français théologique ordinaire.
    #
    # Une confession citée est un **document**, et il y en a une poignée. On les nomme —
    # comme les loci, comme les intentions, comme les traditions. Une liste fermée ne devine
    # rien.
    ("autorité", r"selon (saint |la tradition|les p[èe]res)|commentateur|concile de |NA28|"
                 r"Nestle|Augsbourg|La Rochelle|Westminster|Helv[ée]tique|Belgica|"
                 r"cat[ée]chisme de "),
    # Resserré après le premier passage : « n'est pas un » attrapait du français ordinaire —
    # *« ce passage n'est pas un traité »* est une lecture, pas une négation de doctrine. Seule
    # la portée universelle est visée, parce que c'est là qu'un caveat borne un texte en
    # apparence et tranche une question de fond en réalité.
    ("négation de doctrine",
     r"n(e|')(est|sont) pas (un[e]? )?(universel|valable pour tous|applicable à tous|"
     r"une (loi|v[ée]rit[ée]|doctrine|r[èe]gle) (g[ée]n[ée]rale|universelle))|"
     r"ne (constitue|prouve|fonde|[ée]tablit) pas (une|le|la) (doctrine|dogme)"),
)

_MOTS = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœ]+", re.I)
_CITATIONS = re.compile(r"[«“]\s*([^»”]{4,120})\s*[»”]")


def _sans_accent(texte: str) -> str:
    plie = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in plie if unicodedata.category(c) != "Mn")


@dataclass
class Ecart:
    unite: UUID
    reference: str
    detecteur: str
    gravite: int
    detail: str


@dataclass
class Ligne:
    """Une ligne de curation, quelle que soit sa couche — c'est ce qu'on éprouve."""

    unite: UUID
    couche: str
    axe: str
    corps: str
    signee_ia: bool
    #: `absent` pour une pesée muette — exclue du détecteur de gabarit, voir `_SEUIL_GABARIT`.
    force: str = ""

    @property
    def affirme(self) -> bool:
        return self.force != "absent"


@dataclass
class Unite:
    reference: str
    libelle: str
    texte: str = ""
    lignes: list[Ligne] = field(default_factory=list)
    loci_portants: int = 0
    loci_absents: set[str] = field(default_factory=set)
    caveats: int = 0
    #: `{portée: empreinte jugée}` — un verdict humain déjà posé sur cette unité.
    verdicts: dict[str, str] = field(default_factory=dict)

    @property
    def empreinte(self) -> str:
        return empreinte_de_curation(
            (ligne.couche, ligne.axe, ligne.corps) for ligne in self.lignes
        )


async def _charger() -> dict[UUID, Unite]:
    par_rang = {rang: nom for rang, _osis, _t, nom, _a in BOOKS}
    unites: dict[UUID, Unite] = {}

    async with async_session_factory() as s:
        for p in (await s.execute(select(CorpusPericopeModel))).scalars():
            nom = par_rang.get(p.book_id, "?")
            unites[p.id] = Unite(
                reference=f"{nom} {p.start_ch}:{p.start_v}-{p.end_v}",
                libelle=p.label or "sans titre",
            )

        bornes: dict[UUID, tuple[int, int, int, int]] = {
            p.id: (p.book_id, p.start_ch, p.start_v, p.end_v)
            for p in (await s.execute(select(CorpusPericopeModel))).scalars()
        }
        versets: dict[tuple[int, int, int], str] = {}
        for rang, chapitre, verset, corps in await s.execute(
            select(
                CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                CorpusVerseModel.verse, CorpusVerseModel.body,
            )
        ):
            versets[(rang, chapitre, verset)] = corps
        for unite_id, (livre, chapitre, debut, fin) in bornes.items():
            unites[unite_id].texte = _sans_accent(" ".join(
                versets.get((livre, chapitre, n), "") for n in range(debut, fin + 1)
            ))

        for b in (await s.execute(select(CorpusDoctrinalBearingModel))).scalars():
            u = unites.get(b.pericope_id)
            if u is None:
                continue
            if b.strength == "absent":
                u.loci_absents.add(b.axis_code)
            else:
                u.loci_portants += 1
            u.lignes.append(Ligne(
                b.pericope_id, "pesée", b.axis_code, b.rationale,
                b.reviewed_by == SIGNATAIRE_IA, b.strength,
            ))

        for c in (await s.execute(select(CorpusDoctrinalCaveatModel))).scalars():
            u = unites.get(c.pericope_id)
            if u is None:
                continue
            u.caveats += 1
            u.lignes.append(Ligne(
                c.pericope_id, "mise en garde", c.axis_code, c.body,
                c.reviewed_by == SIGNATAIRE_IA,
            ))

        for r in (await s.execute(select(CorpusReviewModel))).scalars():
            u = unites.get(r.pericope_id)
            if u is not None:
                u.verdicts[r.scope] = r.judged_fingerprint

    return unites


def _deja_juge(unite: Unite, ecart: Ecart) -> bool:
    """Un écart déjà tranché par un humain **sur cette curation-là**.

    ⚠️ Deux portées jugent : celle du détecteur (`D4`) et celle de l'unité entière
    (`ensemble`). La seconde couvre la première — un relecteur qui a relu tout le passage n'a
    pas à revenir sur chaque signalement.

    Et la comparaison d'empreinte est ce qui empêche un verdict de protéger une curation qu'il
    n'a jamais vue : régénérez les pesées, le verdict se périme et l'unité revient."""
    empreinte = unite.empreinte
    code = ecart.detecteur.split()[0]
    return unite.verdicts.get(code) == empreinte or (
        unite.verdicts.get(PORTEE_ENSEMBLE) == empreinte
    )


def _d1_contradiction(unites: dict[UUID, Unite]) -> list[Ecart]:
    """Une mise en garde sur un locus que les pesées ont déclaré muet."""
    trouves = []
    for cle, u in unites.items():
        for ligne in u.lignes:
            if ligne.couche == "mise en garde" and ligne.axe in u.loci_absents:
                trouves.append(Ecart(
                    cle, u.reference, "D1 contradiction", 3,
                    f"mise en garde sur « {ligne.axe} », que les pesées disent absent",
                ))
    return trouves


def _d2_gabarit(
    unites: dict[UUID, Unite], moules_vus: list[tuple[int, str]]
) -> list[Ecart]:
    """Une ligne qui n'est **que** de la tournure commune — un remplissage, pas une lecture.

    ⚠️ Deux resserrages que le premier essai a imposés : on ignore les motifs d'`absent`, qui
    sont formulaires à bon droit, et on mesure la **couverture** de la ligne plutôt que la
    simple présence d'une tournure. Sans le second, toute phrase contenant « le passage ne
    mentionne pas » était signalée — c'est-à-dire à peu près tout le corpus."""
    porteuses: dict[tuple[str, ...], set[UUID]] = defaultdict(set)
    for cle, u in unites.items():
        for ligne in u.lignes:
            if not ligne.affirme:
                continue
            mots = _MOTS.findall(_sans_accent(ligne.corps))
            for i in range(len(mots) - _EMPREINTE + 1):
                porteuses[tuple(mots[i:i + _EMPREINTE])].add(cle)

    moules = {
        empreinte: len(qui) for empreinte, qui in porteuses.items()
        if len(qui) >= _SEUIL_GABARIT
    }
    moules_vus.extend(
        sorted(((n, " ".join(e)) for e, n in moules.items()), reverse=True)[:12]
    )
    if not moules:
        return []

    trouves = []
    for cle, u in unites.items():
        for ligne in u.lignes:
            if not ligne.affirme:
                continue
            mots = _MOTS.findall(_sans_accent(ligne.corps))
            if len(mots) < _EMPREINTE:
                continue
            couverts: set[int] = set()
            pire = (0, ())
            for i in range(len(mots) - _EMPREINTE + 1):
                empreinte = tuple(mots[i:i + _EMPREINTE])
                if empreinte in moules:
                    couverts.update(range(i, i + _EMPREINTE))
                    pire = max(pire, (moules[empreinte], empreinte))
            part = len(couverts) / len(mots)
            if part >= _COUVERTURE_GABARIT:
                trouves.append(Ecart(
                    cle, u.reference, "D2 gabarit", 1,
                    f"{part:.0%} de tournure commune — « {' '.join(pire[1])} » "
                    f"sur {pire[0]} unites",
                ))
    return trouves


def _d3_forme(unites: dict[UUID, Unite]) -> list[Ecart]:
    trouves = []
    for cle, u in unites.items():
        for ligne in u.lignes:
            if not ligne.signee_ia:
                continue  # un humain peut citer un apparat et en répondre
            for nom, motif in _FORMES_INTERDITES:
                touche = re.search(motif, ligne.corps, re.I)
                if touche:
                    trouves.append(Ecart(
                        cle, u.reference, f"D3 forme interdite ({nom})", 3,
                        f"{ligne.couche} : « …{touche.group(0)}… »",
                    ))
                    break
    return trouves


def _d4_aberration(unites: dict[UUID, Unite]) -> list[Ecart]:
    trouves = []
    for cle, u in unites.items():
        if u.loci_portants > _LOCI_PORTANTS_MAX:
            trouves.append(Ecart(
                cle, u.reference, "D4 aberration", 2,
                f"{u.loci_portants} loci portants sur 10 — le modele a voulu aider",
            ))
        if u.caveats >= 3:
            trouves.append(Ecart(
                cle, u.reference, "D4 aberration", 1,
                f"{u.caveats} mises en garde — le plafond, sur un texte quelconque",
            ))
    return trouves


def _d5_citation_fantome(unites: dict[UUID, Unite]) -> list[Ecart]:
    """Une ligne qui cite des mots absents du passage. **Le seul détecteur d'invention pure.**

    Exact, parce que le texte est en base : on ne compare pas à une idée du passage, on compare
    au passage. Les citations d'un seul mot sont ignorées — un mot isolé se retrouve trop
    souvent par hasard sous une autre forme fléchie."""
    trouves = []
    for cle, u in unites.items():
        for ligne in u.lignes:
            # Un relecteur humain peut citer une variante absente du texte servi — c'est même
            # tout l'objet de sa mise en garde.
            if not ligne.signee_ia:
                continue
            for citee in _CITATIONS.findall(ligne.corps):
                mots = _MOTS.findall(_sans_accent(citee))
                if len(mots) < 2:
                    continue
                if not all(m in u.texte for m in mots):
                    trouves.append(Ecart(
                        cle, u.reference, "D5 citation fantome", 3,
                        f"{ligne.couche} cite « {citee} » — absent du passage",
                    ))
    return trouves


def _rapport(unites: dict[UUID, Unite], ecarts: list[Ecart], detail: int, file: bool) -> None:
    lignes_totales = sum(len(u.lignes) for u in unites.values())
    print("=" * 72)
    print(f"  {len(unites)} unites, {lignes_totales} lignes de curation examinees")
    print("=" * 72)

    par_detecteur = Counter(e.detecteur.split(" (")[0] for e in ecarts)
    for nom in sorted(par_detecteur):
        touchees = len({e.unite for e in ecarts if e.detecteur.startswith(nom)})
        print(f"  {nom:<32} {par_detecteur[nom]:>6} lignes   {touchees:>5} unites")

    suspectes = {e.unite for e in ecarts}
    part = 100 * len(suspectes) / (len(unites) or 1)
    print(f"\n  {len(suspectes)} unites a relire sur {len(unites)}  ({part:.1f} %)")
    print("  c'est la file d'attente du relecteur — pas une liste d'erreurs")

    if detail:
        print("\n" + "=" * 72)
        print("  LES PLUS DOUTEUSES")
        print("=" * 72)
        poids: dict[UUID, int] = defaultdict(int)
        for e in ecarts:
            poids[e.unite] += e.gravite
        for unite, _ in sorted(poids.items(), key=lambda kv: -kv[1])[:detail]:
            u = unites[unite]
            print(f"\n  {u.reference} — « {u.libelle} »")
            for e in [x for x in ecarts if x.unite == unite][:4]:
                print(f"    [{e.detecteur}] {e.detail}")

    if file:
        chemin = Path("data/urim_file_relecture.txt")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        poids = defaultdict(int)
        for e in ecarts:
            poids[e.unite] += e.gravite
        with chemin.open("w", encoding="utf-8") as f:
            for unite, note in sorted(poids.items(), key=lambda kv: -kv[1]):
                u = unites[unite]
                f.write(f"{note:>3}  {u.reference:<28} {u.libelle}\n")
                for e in [x for x in ecarts if x.unite == unite]:
                    f.write(f"       [{e.detecteur}] {e.detail}\n")
        print(f"\n  file ecrite : {chemin}")


async def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--detail", type=int, default=0, help="montrer les N plus douteuses")
    analyseur.add_argument("--file", action="store_true", help="ecrire la file du relecteur")
    arguments = analyseur.parse_args()

    unites = await _charger()
    moules: list[tuple[int, str]] = []
    bruts = (
        _d1_contradiction(unites) + _d2_gabarit(unites, moules) + _d3_forme(unites)
        + _d4_aberration(unites) + _d5_citation_fantome(unites)
    )
    ecarts = [e for e in bruts if not _deja_juge(unites[e.unite], e)]

    juges = len(bruts) - len(ecarts)
    relues = sum(1 for u in unites.values() if u.verdicts.get(PORTEE_ENSEMBLE))
    print(f"  {relues} unites relues en entier par un humain, "
          f"{juges} signalements deja tranches\n")

    _rapport(unites, ecarts, arguments.detail, arguments.file)

    if moules:
        print("\n" + "=" * 72)
        print("  LES TOURNURES LES PLUS REPETEES  (hors motifs d'« absent »)")
        print("=" * 72)
        for combien, tournure in sorted(moules, reverse=True)[:10]:
            print(f"  {combien:>5} unites   « {tournure} »")


if __name__ == "__main__":
    asyncio.run(main())
