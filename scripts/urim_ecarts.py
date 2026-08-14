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
    verifier_forme_machine,
)
from app.contexts.urim.domain.errors import CurationInvalideError
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusPericopeModel,
    CorpusReviewModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS

#: La version **contre laquelle la curation est écrite**. Le corpus porte quatre traductions —
#: Segond, Darby, Ostervald, Martin 1744 — qui partagent la clé (livre, chapitre, verset).
#:
#: Ce que ce nom doit à D5 : comparer une citation à la mauvaise traduction revient à accuser
#: d'invention un verset recopié mot pour mot. Ce que les quatre lots de curation lui doivent
#: depuis : **écrire** la curation contre la mauvaise traduction, ce qui ne se rattrape plus
#: par un détecteur. La constante vit ici parce qu'elle y est née ; elle appartient aux deux.
VERSION_DE_CURATION = "LSG"

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

#: ⚠️ **Ce que D3 signale ENCORE, une fois les règles certaines parties au validateur.**
#:
#: `manuscrit` et `autorité` ne sont plus ici : `curation.py` les refuse à l'écriture, aux deux
#: endroits qui écrivent du corpus. Les garder en double aurait produit deux définitions qui
#: divergent le jour où l'une est corrigée. Le détecteur les importe pour continuer à mesurer
#: ce qui serait entré **avant** le validateur.
#:
#: 🔴 La *négation de doctrine* reste ici, et j'allais la déplacer avec les autres. Les neuf
#: lignes prises, lues en entier, l'ont interdit : **huit étaient justes** — la rétribution de
#: Bildad n'est pas une doctrine, « ne pardonne pas leur iniquité » est une supplication et non
#: un énoncé sur le pardon divin, le cantique d'Ézéchias guéri n'est pas une promesse générale.
#: La neuvième restreignait Jean 14:2-3 aux disciples du premier siècle, et aucune expression
#: régulière ne l'aurait distinguée : la différence est théologique. **Un refus aurait payé
#: cette prise de huit bonnes lignes.**
_FORMES_INTERDITES = (
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
    #: ⚠️ **La ligne entière, parce qu'un fragment de regex ne se juge pas.**
    #:
    #: 🔴 D3 signalait « …ne constitue pas une doctrine… » sur Jérémie 14 et Job 16 — impossible
    #: de dire, sur ce bout, si la règle attrapait une faute ou la meilleure mise en garde du
    #: corpus. Un détecteur dont on ne peut pas relire les prises fait arbitrer sur sa parole.
    corps: str = ""


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
        # 🔴 **Le filtre de version, dont l'absence a produit treize fausses accusations.**
        #
        # Ce dictionnaire est indexé sur (livre, chapitre, verset) sans la version. Tant qu'il
        # n'y avait que la Segond, c'était juste. Le jour où Darby et Martin sont entrées en
        # base, chaque clé s'est mise à porter le texte de la dernière version chargée — et D5
        # a comparé des citations de la Segond au français de 1744.
        #
        # Genèse 40:8 cite « N'est-ce pas à Dieu qu'appartiennent les explications ? », qui est
        # le verset **mot pour mot**. Le détecteur l'a déclaré inventé.
        #
        # ⚠️ La leçon dépasse cette ligne : **ajouter une donnée au corpus a cassé un instrument
        # de qualité, en silence.** La curation est écrite contre la Segond ; tout ce qui la
        # vérifie doit le dire explicitement.
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
            # Ce que le validateur refuse désormais à l'écriture — mesuré ici parce que le
            # corpus contient des lignes écrites avant lui.
            try:
                verifier_forme_machine(ligne.corps, SIGNATAIRE_IA)
            except CurationInvalideError as refus:
                trouves.append(Ecart(
                    cle, u.reference, "D3 forme interdite (antérieure au validateur)", 3,
                    str(refus)[:90], ligne.corps,
                ))
                continue
            for nom, motif in _FORMES_INTERDITES:
                touche = re.search(motif, ligne.corps, re.I)
                if touche:
                    trouves.append(Ecart(
                        cle, u.reference, f"D3 forme interdite ({nom})", 3,
                        f"{ligne.couche} : « …{touche.group(0)}… »", ligne.corps,
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
    return trouves


# 🔴 **La règle qui comptait les mises en garde a été retirée, et c'était une règle circulaire.**
#
# Elle signalait `caveats >= 3`, c'est-à-dire le plafond de l'invite. Elle a donc signalé
# 1 083 unités — un quart du corpus — pour dire une seule chose : que le plafond était à trois.
# Un maximum atteint souvent n'est pas une aberration, c'est un maximum mal choisi.
#
# Le bon instrument est la **distribution**, pas un drapeau par unité : sur 4 449 unités,
# 48 % à zéro, 12 unités à une, 27 % à deux, 25 % à trois — un trou à un qui trahissait un
# quota rempli, et qu'aucun signalement unitaire ne pouvait montrer. Le plafond est passé à
# deux, réglé sur les six mises en garde faites à la main.
#
# Si une règle de comptage revient ici, elle devra tirer son seuil de la distribution observée,
# jamais d'un chiffre écrit dans une invite.


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
                        f"{ligne.couche} cite « {citee} » — absent du passage", ligne.corps,
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
    analyseur.add_argument("--corps", help="lire en entier les lignes prises par un detecteur")
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

    if arguments.corps:
        pris = [
            e for e in ecarts
            if e.detecteur.upper().startswith(arguments.corps.upper()) and e.corps
        ]
        print("=" * 74)
        print(f"  LES {len(pris)} LIGNES PRISES PAR {arguments.corps.upper()}, EN ENTIER")
        print("=" * 74)
        for e in pris:
            print(f"\n  {e.reference}   [{e.detecteur}]")
            print(f"    {e.corps}")
        return

    _rapport(unites, ecarts, arguments.detail, arguments.file)

    if moules:
        print("\n" + "=" * 72)
        print("  LES TOURNURES LES PLUS REPETEES  (hors motifs d'« absent »)")
        print("=" * 72)
        for combien, tournure in sorted(moules, reverse=True)[:10]:
            print(f"  {combien:>5} unites   « {tournure} »")


if __name__ == "__main__":
    asyncio.run(main())
