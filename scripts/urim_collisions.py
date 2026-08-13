"""Les collisions de sens — **là où deux traducteurs sérieux n'ont pas lu la même chose**.

    python scripts/urim_collisions.py                    # le rapport
    python scripts/urim_collisions.py --lire 15          # les prises, textes en regard
    python scripts/urim_collisions.py --paire MARTIN

Un menu « choisissez votre traduction » demanderait au pasteur de configurer. Urim signale,
partout ailleurs — et une divergence entre deux traductions du domaine public **est** un
signalement : elle marque un endroit où l'original est ambigu, où un mot porte plusieurs sens,
ou où les éditions ne portent pas le même texte.

C'est la seule approche honnête des variantes dont ce produit dispose. On n'affirme pas qu'un
manuscrit porte ceci — on montre que deux traducteurs ont lu autrement, et le pasteur vérifie
des deux yeux.

## Tous les versets diffèrent : trois artefacts avant le premier signal

Darby serre l'original, Segond arrondit, Martin écrit en 1744. Comparer des chaînes signalerait
les 31 000 versets. Chaque passage du détecteur a écarté une famille de faux signaux, et chacune
n'est apparue qu'après la précédente :

1. **La divergence maximale visait à l'envers.** Les dix premières étaient « 72 000 » contre
   « soixante-douze mille », « les Héviens » contre « le Hévien », et 1 Chroniques 6:4 où les
   deux textes ne sont pas le même verset. Toutes ne se recouvrent presque pas — alors qu'une
   collision de sens est l'inverse : deux rendus manifestement du même verset qui ne diffèrent
   que sur **un mot lourd**.
2. **La translittération.** *Diphat/Diphath*, *Léschem/Léshem*, *Kirjath/Kiriath*. Les mots
   rares de la Bible sont massivement des noms propres, et l'IDF les met tous au plafond.
3. **Le lexique amputait la comparaison.** En ne gardant que les mots connus de l'IDF — bâti
   sur la seule Segond — la graphie de Darby disparaissait avant d'être comparée, et celle de
   la Segond paraissait sans équivalent. Le filtre de translittération ne voyait rien à
   apparier. **Peser et comparer ne demandent pas le même ensemble de mots.**

⚠️ **La versification est appliquée.** Sans elle, le Psautier entier ressortirait, puisque
Martin ne numérote pas les suscriptions — le premier signal aurait été du bruit pur sur le livre
le plus prêché de la Bible.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusIdfModel,
    CorpusVerseModel,
    CorpusVersificationMapModel,
    CorpusVersionModel,
)
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS

REFERENCE = "LSG"

#: La preuve que c'est bien le même verset, exigée **avant** de peser quoi que ce soit.
RECOUVREMENT_MINIMUM = 0.5

#: Deux mots assez proches sont la même chose écrite autrement. On ne tient pas une liste de
#: noms propres : elle serait fausse le jour où un traducteur en ajoute un.
PROXIMITE_GRAPHIQUE = 0.8

#: La queue retenue. Un centile, pas un score : « les 1 % où le désaccord pèse le plus lourd »
#: se défend, « au-dessus de 0,6 » ne se défend pas.
CENTILE = 99.0

#: Un verset trop court n'a pas assez de mots pleins pour qu'une divergence veuille dire quoi
#: que ce soit — « Jésus pleura » diverge à 100 % ou à 0 %, jamais entre les deux.
MOTS_PLEINS_MINIMUM = 5

#: 🔴 **Le quatrième artefact : la reformulation.**
#:
#: Le poids seul ne discriminait plus rien — tout mot rare atteint le plafond de l'IDF, et
#: 2 650 versets s'y retrouvaient à égalité. Les prises l'ont montré : *« consacrèrent »* contre
#: *« sanctifièrent »* est **un mot pour un autre**, un choix de traducteur sur un verbe
#: théologique. Néhémie 10:34, où Darby refait la phrase entière, en aligne quatre ou cinq et
#: n'apprend rien.
#:
#: Une collision de sens est une **substitution** : deux mots d'écart, un de chaque côté. Ce
#: n'est pas un réglage de sensibilité, c'est la définition de ce qu'on cherche.
SUBSTITUTION_MAXIMUM = 2


@dataclass
class Collision:
    livre: int
    chapitre: int
    verset: int
    score: float
    gauche: str
    droite: str
    mots: tuple[str, ...]


def _apparie(mot: str, autres: set[str]) -> bool:
    """Le même mot sous une autre graphie.

    ⚠️ `autres` est le vocabulaire **entier** de l'autre rendu, jamais sa part connue du
    lexique. C'est le défaut qui a fait survivre les noms propres à leur propre filtre :
    l'IDF est bâti sur la Segond, « leshem » n'y figure pas, il disparaissait donc avant la
    comparaison et « léschem » ressortait comme un mot sans équivalent."""
    return any(SequenceMatcher(None, mot, autre).ratio() >= PROXIMITE_GRAPHIQUE
               for autre in autres)


def _divergence(
    a: str, b: str, poids: dict[str, float]
) -> tuple[float, tuple[str, ...]] | None:
    """Le poids du **mot le plus lourd** sur lequel deux rendus du même verset se séparent.

    Le maximum, et non la somme : une collision de sens tient dans un mot, et une phrase
    reformulée d'un bout à l'autre n'en est pas une."""
    tous_a, tous_b = set(a.split()), set(b.split())
    pesables_a = {m for m in tous_a if m in poids}
    pesables_b = {m for m in tous_b if m in poids}
    if len(pesables_a) < MOTS_PLEINS_MINIMUM or len(pesables_b) < MOTS_PLEINS_MINIMUM:
        return None

    commun, union = pesables_a & pesables_b, pesables_a | pesables_b
    if not union or len(commun) / len(union) < RECOUVREMENT_MINIMUM:
        return None

    ecart = {
        m for m in pesables_a ^ pesables_b
        if not _apparie(m, tous_b if m in pesables_a else tous_a)
    }
    if not ecart or len(ecart) > SUBSTITUTION_MAXIMUM:
        return None
    porteurs = tuple(sorted(ecart, key=lambda m: -poids[m]))
    return max(poids[m] for m in ecart), porteurs


async def detecter(paire: str, lire: int) -> None:
    par_rang = {rang: label for rang, _osis, _t, label, _a in BOOKS}

    async with async_session_factory() as s:
        versions = {
            v.code: v.id for v in (await s.execute(select(CorpusVersionModel))).scalars()
        }
        if paire not in versions:
            raise SystemExit(f"  version inconnue : {paire}")

        poids = {
            t: idf for t, idf in await s.execute(
                select(CorpusIdfModel.token, CorpusIdfModel.idf).where(
                    CorpusIdfModel.language == "fr"
                )
            )
        }

        renvoi = {
            (livre, dch, dv): (ach, av)
            for livre, dch, dv, ach, av in await s.execute(
                select(
                    CorpusVersificationMapModel.book_id,
                    CorpusVersificationMapModel.from_ch,
                    CorpusVersificationMapModel.from_v,
                    CorpusVersificationMapModel.to_ch,
                    CorpusVersificationMapModel.to_v,
                ).where(
                    CorpusVersificationMapModel.from_scheme == REFERENCE,
                    CorpusVersificationMapModel.to_scheme == paire,
                )
            )
        }

        textes: dict[str, dict[tuple[int, int, int], tuple[str, str]]] = {}
        for code in (REFERENCE, paire):
            textes[code] = {
                (livre, ch, v): (corps, norme)
                for livre, ch, v, corps, norme in await s.execute(
                    select(
                        CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                        CorpusVerseModel.verse, CorpusVerseModel.body,
                        CorpusVerseModel.body_norm,
                    ).where(CorpusVerseModel.version_id == versions[code])
                )
            }

    collisions: list[Collision] = []
    for (livre, ch, v), (corps_a, norme_a) in textes[REFERENCE].items():
        ach, av = renvoi.get((livre, ch, v), (ch, v))
        autre = textes[paire].get((livre, ach, av))
        if autre is None:
            continue
        lu = _divergence(norme_a, autre[1], poids)
        if lu is None:
            continue
        collisions.append(Collision(livre, ch, v, lu[0], corps_a, autre[0], lu[1]))

    if not collisions:
        print("  rien a comparer.")
        return

    scores = sorted(c.score for c in collisions)
    seuil = scores[min(len(scores) - 1, int(len(scores) * CENTILE / 100))]
    retenues = sorted((c for c in collisions if c.score >= seuil), key=lambda c: -c.score)

    print("=" * 78)
    print(f"  COLLISIONS  {REFERENCE} ↔ {paire}   —   {len(collisions)} versets comparables")
    print("=" * 78)
    for centile in (50, 75, 90, 99):
        valeur = scores[min(len(scores) - 1, int(len(scores) * centile / 100))]
        print(f"    {centile}ᵉ centile   {valeur:.3f}")
    print(f"\n  seuil retenu ({CENTILE}ᵉ centile) : {seuil:.3f}")
    print(f"  {len(retenues)} versets en collision")

    if not lire:
        print("\n  rapport seul — relancer avec --lire N pour voir les textes en regard.")
        return

    print("\n" + "=" * 78)
    print(f"  LES {min(lire, len(retenues))} PLUS FORTES, TEXTES EN REGARD")
    print("=" * 78)
    for c in retenues[:lire]:
        print(f"\n  {par_rang[c.livre]} {c.chapitre}:{c.verset}"
              f"   poids {c.score:.2f}   [{' · '.join(c.mots)}]")
        print(f"    {REFERENCE:<7} {c.gauche}")
        print(f"    {paire:<7} {c.droite}")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--paire", default="DARBY", help="la version comparee a la Segond")
    analyseur.add_argument(
        "--lire", type=int, default=0, help="afficher N collisions, textes en regard"
    )
    arguments = analyseur.parse_args()
    asyncio.run(detecter(arguments.paire.upper(), arguments.lire))


if __name__ == "__main__":
    main()
