"""Les correspondances de numérotation — **alignées sur le texte, jamais sur l'arithmétique**.

    python scripts/urim_versification.py --version MARTIN            # rapport seul
    python scripts/urim_versification.py --version MARTIN --ecrire   # écrit la table
    python scripts/urim_versification.py --version DARBY --ecrire

Les traductions ne numérotent pas pareil. Martin ne compte pas les suscriptions de psaumes —
*« Psaume de David, lorsque… »* — que l'hébreu et la Segond comptent comme verset. D'où un
décalage d'un verset sur des dizaines de psaumes, et **66 versets d'écart sur le Psautier**.

Sans cette table, « Psaume 51:12 » servi en Martin affiche le verset 11. Une référence juste,
un texte faux : c'est pire que ne rien afficher, parce que rien ne le signale.

## Pourquoi on ne déduit pas le décalage du compte de versets

Un chapitre qui a un verset de moins peut l'avoir perdu **au début** (la suscription), **à la
fin**, ou **au milieu** (deux versets fondus en un). Les trois donnent le même compte et trois
correspondances différentes. Deviner, c'est écrire une table qui a l'air juste et qui décale
tout un psaume.

**On aligne donc sur le texte.** Deux traductions françaises du même verset partagent une bonne
part de leurs mots pleins ; deux versets différents beaucoup moins. Pour chaque décalage
candidat, on mesure l'accord lexical moyen sur tout le chapitre, et on retient celui qui gagne
franchement. La méthode est vérifiable — le score s'imprime, et il se relit.

## Un chapitre juste au début et faux à la fin

Les deux premiers passages raisonnent par chapitre : ils l'expliquent en entier, ou pas du tout.
Exode 7 leur échappait donc doublement — vingt-cinq versets parfaitement numérotés, quatre qui
débordent dans le chapitre suivant, et un décalage 0 qui gagne franchement. Classé « bien
numéroté », il n'écrivait rien, et « Exode 7:26 » n'affichait rien non plus.

Le troisième passage part donc du **verset** et non du chapitre : tout verset de la Segond sans
cible ni correspondance est cherché en tête du chapitre suivant. Ce sont 193 références sur les
trois traductions, dont Nombres 16:36-50 et 1 Rois 4:21-34.

## Ce que le script refuse de faire

**Il n'écrit rien qu'il n'ait pu confirmer.** Un chapitre dont aucun décalage ne convainc — un
verset fondu au milieu, un découpage propre à une traduction — est **signalé, pas rempli**. Une
correspondance inventée serait exactement le genre d'erreur qu'on ne découvre qu'en chaire.

Et `--ecrire` est explicite : remplir cette table est une décision, pas l'effet de bord d'un
rapport qu'on lance pour voir.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, insert, select

from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusVerseModel,
    CorpusVersificationMapModel,
    CorpusVersionModel,
)
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS

#: Le schéma de référence — celui que le pasteur écrit, et que tout le produit tient.
REFERENCE = "LSG"

#: Les décalages cherchés. Au-delà de deux versets, ce n'est plus une convention de
#: numérotation, c'est un autre découpage : il appartient à un humain, pas à un script.
CANDIDATS = (0, 1, -1, 2, -2)

#: 🔴 **Le seuil se calibre sur la traduction, il ne se décrète pas.**
#:
#: Fixé à 0,45, il retenait 15 chapitres sur 55 pour Darby et **5 sur 111 pour Martin**. La
#: différence n'est pas que Martin diverge plus : c'est qu'elle écrit le français de 1744.
#: « Icelui », les graphies anciennes, une autre ponctuation — l'accord lexical avec la Segond
#: y est structurellement plus bas, et un seuil unique condamnait la plus ancienne des trois.
#:
#: On mesure donc d'abord l'accord **de référence** : la moyenne, sur les chapitres dont le
#: compte de versets est identique, où l'alignement est certain. C'est l'étalon propre à chaque
#: paire de traductions. Un décalage n'est retenu que s'il atteint cette proportion-là de
#: l'étalon.
PART_DE_L_ETALON = 0.8

#: Et il ne suffit pas d'être bon : il faut être **nettement meilleur** que le suivant. Un
#: chapitre où deux décalages se valent est un chapitre qu'on n'a pas compris.
AVANCE_MINIMUM = 0.10

#: 🔴 **Le débordement ne se juge pas comme un alignement, et il faut dire pourquoi.**
#:
#: Partout ailleurs, le texte *choisit* : plusieurs décalages sont possibles, plusieurs positions
#: dans le livre sont possibles, et l'accord lexical départage. Il doit donc être exigeant.
#:
#: Un débordement, lui, n'a rien à départager. On exige que les versets sans cible soient la
#: **queue** de leur chapitre, et qu'ils remplissent **exactement** la tête libre du chapitre
#: suivant — même compte, contiguë, ancrée au premier verset. Quand ces trois conditions
#: tiennent, il n'existe aucune autre place où les mettre : la structure a déjà décidé, et
#: l'accord n'est plus le juge mais le **garde-fou** — il ne sert qu'à refuser d'accoler la fin
#: d'un chapitre à un texte sans rapport.
#:
#: Le prix de l'ancienne exigence était réel : Lévitique 5:20-26 accorde à 0,49 pour un seuil à
#: 0,51, et c'est pourtant mot pour mot le même passage (« L'Éternel parla aussi à Moïse »).
#: Deux traductions françaises séparées de deux siècles partagent peu de mots pleins sur une
#: page de droit sacrificiel — c'est une propriété de la paire, pas un doute sur la place.
#:
#: Le plancher reste loin du bruit : deux versets sans rapport accordent autour de 0,10.
PART_DE_L_ETALON_DEBORDEMENT = 0.55


@dataclass
class Alignement:
    livre: int
    chapitre: int
    decalage: int
    accord: float
    avance: float
    versets: int


@dataclass
class Glissement:
    """Un chapitre qui atterrit **ailleurs** dans l'autre traduction — parfois un autre chapitre.

    🔴 Le détecteur de collisions a montré le trou : 1 Chroniques 6:4 rendait « Éléazar engendra
    Phinées » d'un côté et « Les fils de Merari » de l'autre. Deux textes sans rapport sous la
    même référence.

    La cause n'est pas un décalage de numérotation, c'est une **tradition** : Darby suit le
    découpage hébreu, où 1 Chroniques 6 commence quinze versets plus loin que dans le découpage
    anglais et latin que la Segond a repris. Le début du chapitre est même dans le chapitre
    PRÉCÉDENT.

    Aucune fenêtre de ±2 ne pouvait le voir, et l'élargir n'aurait pas suffi : il fallait
    accepter que la cible change de chapitre. On cherche donc, pour tout chapitre que le
    décalage simple n'explique pas, **où sa suite de versets se retrouve dans le livre**."""

    livre: int
    chapitre: int
    accord: float
    #: `(verset source) → (chapitre cible, verset cible)`
    renvois: dict[int, tuple[int, int]]


@dataclass
class Debordement:
    """La queue d'un chapitre que l'autre traduction a poussée dans le chapitre **suivant**.

    🔴 Le trou que le rapport au chapitre a rendu visible. Exode 7 compte 29 versets dans la
    Segond et 25 dans Ostervald : le décalage 0 gagne — il est juste pour les 25 premiers — et
    le chapitre part donc dans « bien numérotés malgré le compte », qui n'écrit rien. Les quatre
    versets qui débordent n'avaient aucune correspondance, et « Exode 7:26 » n'affichait rien.

    Rien n'y était faux, et c'est pour cela que ça a tenu si longtemps : la panne était du bon
    côté. Mais 193 références sur les trois traductions étaient simplement inatteignables,
    dont Nombres 16:36-50 et 1 Rois 4:21-34 — quinze et quatorze versets d'un coup.

    On ne les déduit pas de l'arithmétique, même règle que tout le reste : on va lire en tête du
    chapitre suivant, et on n'écrit que si le texte est d'accord."""

    livre: int
    chapitre: int
    accord: float
    #: `(verset source) → (chapitre cible, verset cible)`
    renvois: dict[int, tuple[int, int]]


def _accord(a: str, b: str) -> float:
    """Jaccard sur les mots — la mesure la plus bête qui distingue deux traductions
    d'un même verset de deux versets différents."""
    mots_a, mots_b = set(a.split()), set(b.split())
    if not mots_a or not mots_b:
        return 0.0
    return len(mots_a & mots_b) / len(mots_a | mots_b)


def _aligner(
    reference: dict[int, str], autre: dict[int, str], livre: int, chapitre: int
) -> Alignement | None:
    """Le décalage qui explique le chapitre, ou rien."""
    scores: list[tuple[float, int, int]] = []
    for decalage in CANDIDATS:
        paires = [
            (reference[v], autre[v - decalage])
            for v in reference
            if (v - decalage) in autre
        ]
        if len(paires) < max(3, len(reference) // 2):
            continue
        moyen = sum(_accord(x, y) for x, y in paires) / len(paires)
        scores.append((moyen, decalage, len(paires)))

    if not scores:
        return None
    scores.sort(reverse=True)
    meilleur, decalage, couverts = scores[0]
    suivant = scores[1][0] if len(scores) > 1 else 0.0
    return Alignement(livre, chapitre, decalage, meilleur, meilleur - suivant, couverts)


def _chercher_dans_le_livre(
    chapitre_source: dict[int, str],
    livre_cible: list[tuple[int, int, str]],
    seuil: float,
) -> tuple[float, dict[int, tuple[int, int]]] | None:
    """Où la suite de versets d'un chapitre se retrouve dans le livre entier.

    On fait glisser le chapitre le long du livre cible et on garde la position qui accorde le
    mieux. Les versets se lisent **dans l'ordre** : c'est ce qui distingue un vrai glissement
    d'une coïncidence de vocabulaire entre deux généalogies voisines."""
    versets = [chapitre_source[v] for v in sorted(chapitre_source)]
    numeros = sorted(chapitre_source)
    if len(versets) < 4 or len(livre_cible) < len(versets):
        return None

    meilleur = (0.0, 0)
    for depart in range(len(livre_cible) - len(versets) + 1):
        total = sum(
            _accord(versets[i], livre_cible[depart + i][2]) for i in range(len(versets))
        )
        moyen = total / len(versets)
        if moyen > meilleur[0]:
            meilleur = (moyen, depart)

    accord, depart = meilleur
    if accord < seuil:
        return None
    return accord, {
        numeros[i]: (livre_cible[depart + i][0], livre_cible[depart + i][1])
        for i in range(len(versets))
    }


def _deborder(
    orphelins: list[int],
    reference: dict[int, str],
    suivant: dict[int, str],
    promis: set[int],
    chapitre_suivant: int,
    seuil: float,
) -> tuple[float, dict[int, tuple[int, int]]] | None:
    """Les versets sans cible, cherchés en tête du chapitre suivant.

    Deux exigences de forme, avant même de regarder le texte. **En queue** : un débordement est
    la fin d'un chapitre, pas un verset pris au milieu. **Pile la tête libre du suivant** : même
    compte, contiguë, ancrée au premier verset du chapitre.

    C'est la seconde qui fait tout le travail, et c'est elle qui distingue une frontière déplacée
    d'un verset fondu. Luc 10:42 n'a pas de cible et Luc 11 est libre en entier : cinquante-quatre
    places pour un verset, donc aucune raison de choisir la première — le verset est en réalité
    fondu dans Luc 10:41, et il est refusé. Lévitique 5:20-26 déborde sur sept places libres,
    exactement sept : il n'y a pas d'autre réponse à donner."""
    fin = max(reference)
    if orphelins != list(range(fin - len(orphelins) + 1, fin + 1)):
        return None

    # ⚠️ `libres` ENTIER, pas ses premiers éléments : s'il reste de la place après le
    # débordement, c'est qu'on avait le choix — et dès qu'on a le choix, ce n'est plus ici que
    # ça se décide.
    tete = sorted(v for v in suivant if v not in promis)
    debut = min(suivant)
    if tete != list(range(debut, debut + len(orphelins))):
        return None

    paires = [
        (reference[source], suivant[cible])
        for source, cible in zip(orphelins, tete, strict=True)
    ]
    accord = sum(_accord(a, b) for a, b in paires) / len(paires)
    if accord < seuil:
        return None
    return accord, {
        source: (chapitre_suivant, cible)
        for source, cible in zip(orphelins, tete, strict=True)
    }


async def cartographier(code: str, ecrire: bool) -> None:
    par_rang = {rang: label for rang, _osis, _t, label, _a in BOOKS}

    async with async_session_factory() as s:
        versions = {
            v.code: v.id for v in (await s.execute(select(CorpusVersionModel))).scalars()
        }
        if code not in versions or REFERENCE not in versions:
            raise SystemExit(f"  version inconnue : {code}")

        textes: dict[str, dict[tuple[int, int], dict[int, str]]] = {REFERENCE: {}, code: {}}
        for nom in (REFERENCE, code):
            for livre, chapitre, verset, norme in await s.execute(
                select(
                    CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                    CorpusVerseModel.verse, CorpusVerseModel.body_norm,
                ).where(CorpusVerseModel.version_id == versions[nom])
            ):
                textes[nom].setdefault((livre, chapitre), {})[verset] = norme

    # L'étalon : les chapitres au compte identique sont alignés à coup sûr, et disent donc ce
    # que « bien aligné » veut dire *pour cette traduction-là*.
    surs = [
        cle for cle, versets in textes[REFERENCE].items()
        if len(textes[code].get(cle, {})) == len(versets) and versets
    ]
    accords_surs = [
        sum(_accord(textes[REFERENCE][cle][v], textes[code][cle][v])
            for v in textes[REFERENCE][cle] if v in textes[code][cle])
        / max(1, len(textes[REFERENCE][cle]))
        for cle in surs
    ]
    etalon = sum(accords_surs) / len(accords_surs) if accords_surs else 0.5
    seuil = etalon * PART_DE_L_ETALON
    seuil_debordement = etalon * PART_DE_L_ETALON_DEBORDEMENT
    print(f"  etalon {REFERENCE}↔{code} : accord {etalon:.2f} sur {len(surs)} chapitres surs")
    print(f"  seuil retenu : {seuil:.2f}   (debordement : {seuil_debordement:.2f})\n")

    #: On ne regarde que les chapitres qui **diffèrent en compte** : ailleurs, la numérotation
    #: est la même et une correspondance identité n'apprendrait rien à personne.
    suspects = [
        cle for cle, versets in textes[REFERENCE].items()
        if len(textes[code].get(cle, {})) != len(versets)
    ]

    etablis: list[Alignement] = []
    #: ⚠️ **Un compte différent n'est pas un décalage.** Un chapitre où le décalage 0 gagne
    #: franchement est un chapitre bien numéroté dont un verset a été fondu ou scindé
    #: localement : rien à cartographier, et surtout rien à signaler à un humain. Les mêler aux
    #: vrais problèmes noyait les seconds — 106 « à la main » dont l'immense majorité allait
    #: parfaitement bien.
    locaux: list[Alignement] = []
    douteux: list[tuple[int, int, Alignement | None]] = []
    for livre, chapitre in sorted(suspects):
        autre = textes[code].get((livre, chapitre))
        if not autre:
            douteux.append((livre, chapitre, None))
            continue
        lu = _aligner(textes[REFERENCE][(livre, chapitre)], autre, livre, chapitre)
        if lu is None or lu.accord < seuil or lu.avance < AVANCE_MINIMUM:
            douteux.append((livre, chapitre, lu))
        elif lu.decalage == 0:
            locaux.append(lu)
        else:
            etablis.append(lu)

    # Second passage : ce qu'aucun décalage simple n'explique atterrit peut-être ailleurs dans
    # le livre — c'est le cas de 1 Chroniques 6, que le détecteur de collisions a révélé.
    par_livre: dict[int, list[tuple[int, int, str]]] = {}
    for (livre, chapitre), versets in textes[code].items():
        par_livre.setdefault(livre, []).extend(
            (chapitre, v, texte) for v, texte in versets.items()
        )
    for suite in par_livre.values():
        suite.sort()

    glissements: list[Glissement] = []
    restants: list[tuple[int, int, Alignement | None]] = []
    for livre, chapitre, lu in douteux:
        trouve = _chercher_dans_le_livre(
            textes[REFERENCE][(livre, chapitre)], par_livre.get(livre, []), seuil
        )
        if trouve is None:
            restants.append((livre, chapitre, lu))
            continue
        accord, renvois = trouve
        # Un glissement qui rend chacun sur lui-même n'est pas un glissement.
        if all(cible == (chapitre, source) for source, cible in renvois.items()):
            restants.append((livre, chapitre, lu))
        else:
            glissements.append(Glissement(livre, chapitre, accord, renvois))
    douteux = restants

    # Troisième passage : les versets qu'aucune correspondance ne couvre. Les deux premiers
    # raisonnent par CHAPITRE — ils cartographient un chapitre entier ou rien. Un chapitre juste
    # sur ses vingt-cinq premiers versets et débordant sur les quatre derniers leur échappait
    # tout entier, parce qu'il n'avait pas l'air d'un problème.
    couvert: set[tuple[int, int, int]] = set()
    promis: dict[tuple[int, int], set[int]] = {}
    for a in etablis:
        for verset in textes[REFERENCE][(a.livre, a.chapitre)]:
            if (verset - a.decalage) in textes[code][(a.livre, a.chapitre)]:
                couvert.add((a.livre, a.chapitre, verset))
                promis.setdefault((a.livre, a.chapitre), set()).add(verset - a.decalage)
    for g in glissements:
        for source, (cible_ch, cible_v) in g.renvois.items():
            couvert.add((g.livre, g.chapitre, source))
            # Une cible déjà promise ne peut pas être réclamée deux fois : deux références qui
            # rendent le même verset, c'est la faute que la table est censée empêcher.
            promis.setdefault((g.livre, cible_ch), set()).add(cible_v)

    debordements: list[Debordement] = []
    orphelins: list[tuple[int, int, list[int]]] = []
    for (livre, chapitre), versets in sorted(textes[REFERENCE].items()):
        sans_cible = sorted(
            v for v in versets
            if v not in textes[code].get((livre, chapitre), {})
            and (livre, chapitre, v) not in couvert
        )
        if not sans_cible:
            continue
        suivant = textes[code].get((livre, chapitre + 1))
        trouve = _deborder(
            sans_cible, versets, suivant,
            promis.get((livre, chapitre + 1), set()), chapitre + 1, seuil_debordement,
        ) if suivant else None
        if trouve is None:
            orphelins.append((livre, chapitre, sans_cible))
        else:
            debordements.append(Debordement(livre, chapitre, trouve[0], trouve[1]))

    print(f"  {len(suspects)} chapitres au compte different entre {REFERENCE} et {code}")
    print(f"  {len(etablis)} decalages a cartographier")
    print(f"  {len(glissements)} chapitres GLISSES (retrouves ailleurs dans le livre)")
    print(f"  {len(debordements)} chapitres qui DEBORDENT sur le suivant")
    print(f"  {len(locaux)} bien numerotes malgre le compte (un verset fondu ou scinde)")
    print(f"  {len(douteux)} a la main\n")

    for d in sorted(debordements, key=lambda x: (x.livre, x.chapitre)):
        premier = min(d.renvois)
        cible = d.renvois[premier]
        print(f"    {par_rang[d.livre]:<16} ch. {d.chapitre}:{premier} → {cible[0]}:{cible[1]}"
              f"   accord {d.accord:.2f}   {len(d.renvois)} versets")

    for g in sorted(glissements, key=lambda x: (x.livre, x.chapitre)):
        premier = min(g.renvois)
        cible = g.renvois[premier]
        print(f"    {par_rang[g.livre]:<16} ch. {g.chapitre:<4} → {cible[0]}:{cible[1]}"
              f"   accord {g.accord:.2f}   {len(g.renvois)} versets")

    for a in sorted(etablis, key=lambda x: (x.livre, x.chapitre))[:12]:
        print(f"    {par_rang[a.livre]:<16} ch. {a.chapitre:<4} decalage {a.decalage:+}"
              f"   accord {a.accord:.2f}  avance {a.avance:.2f}")
    if len(etablis) > 12:
        print(f"    … et {len(etablis) - 12} autres")

    if douteux:
        print(f"\n  ⚠️ {len(douteux)} chapitres qu'aucun decalage n'explique — un verset fondu,")
        print("     un decoupage propre a la traduction. Ils appartiennent a un humain :\n")
        for livre, chapitre, lu in douteux[:10]:
            detail = (
                f"meilleur {lu.decalage:+} a {lu.accord:.2f} (avance {lu.avance:.2f})"
                if lu else "aucun chapitre correspondant"
            )
            print(f"    {par_rang[livre]:<16} ch. {chapitre:<4} {detail}")
        if len(douteux) > 10:
            print(f"    … et {len(douteux) - 10} autres")

    if orphelins:
        n = sum(len(versets) for _l, _c, versets in orphelins)
        print(f"\n  ⚠️ {n} versets restent sans cible — ni a leur propre reference, ni en tete")
        print("     du chapitre suivant. Un verset fondu dans son voisin, le plus souvent :")
        print("     rien ne s'affichera pour eux, et c'est la panne du bon cote.\n")
        for livre, chapitre, versets in orphelins[:10]:
            etendue = (
                f"{min(versets)}-{max(versets)}" if len(versets) > 1 else f"{versets[0]}"
            )
            print(f"    {par_rang[livre]:<16} {chapitre}:{etendue}")
        if len(orphelins) > 10:
            print(f"    … et {len(orphelins) - 10} autres chapitres")

    if not ecrire:
        print("\n  rapport seul — relancer avec --ecrire pour remplir la table.")
        return

    lignes = []
    for a in etablis:
        for verset in textes[REFERENCE][(a.livre, a.chapitre)]:
            if (verset - a.decalage) in textes[code][(a.livre, a.chapitre)]:
                lignes.append({
                    "from_scheme": REFERENCE, "to_scheme": code, "book_id": a.livre,
                    "from_ch": a.chapitre, "from_v": verset,
                    "to_ch": a.chapitre, "to_v": verset - a.decalage,
                })
    for renvoyeur in (*glissements, *debordements):
        for source, (cible_ch, cible_v) in renvoyeur.renvois.items():
            lignes.append({
                "from_scheme": REFERENCE, "to_scheme": code, "book_id": renvoyeur.livre,
                "from_ch": renvoyeur.chapitre, "from_v": source,
                "to_ch": cible_ch, "to_v": cible_v,
            })

    async with async_session_factory() as s:
        await s.execute(
            delete(CorpusVersificationMapModel).where(
                CorpusVersificationMapModel.from_scheme == REFERENCE,
                CorpusVersificationMapModel.to_scheme == code,
            )
        )
        if lignes:
            await s.execute(insert(CorpusVersificationMapModel), lignes)
        await s.commit()
    print(f"\n  {len(lignes)} correspondances ecrites {REFERENCE} → {code}")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--version", required=True, help="DARBY, MARTIN…")
    analyseur.add_argument(
        "--ecrire", action="store_true", help="remplir la table (sinon rapport seul)"
    )
    arguments = analyseur.parse_args()
    asyncio.run(cartographier(arguments.version.upper(), arguments.ecrire))


if __name__ == "__main__":
    main()
