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


@dataclass
class Alignement:
    livre: int
    chapitre: int
    decalage: int
    accord: float
    avance: float
    versets: int


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
    print(f"  etalon {REFERENCE}↔{code} : accord {etalon:.2f} sur {len(surs)} chapitres surs")
    print(f"  seuil retenu : {seuil:.2f}\n")

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

    print(f"  {len(suspects)} chapitres au compte different entre {REFERENCE} et {code}")
    print(f"  {len(etablis)} decalages a cartographier")
    print(f"  {len(locaux)} bien numerotes malgre le compte (un verset fondu ou scinde)")
    print(f"  {len(douteux)} a la main\n")

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
