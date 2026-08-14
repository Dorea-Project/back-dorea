"""Rendre au corpus la normalisation que le normaliseur sait faire — **sans le re-semer**.

    python scripts/urim_renormaliser.py --rapport      # mesurer, ne rien ecrire
    python scripts/urim_renormaliser.py --appliquer    # ecrire

## Pourquoi ce script existe alors que `seed_urim_corpus.py` sait déjà tout écrire

Parce que semer et **rattraper** ne sont pas le même geste, et que le confondre coûte le corpus.

`seed_urim_corpus.py --purge` efface les péricopes et toute la curation qui pend dessous —
81 943 couples de faisabilité, 45 557 pesées, 4 825 notes de contexte, 2 403 mises en garde,
dont plus de 134 000 lignes signées `ia-mistral`. C'est le bon geste pour repartir de zéro et le
mauvais pour corriger une colonne dérivée. *(Il ne s'exécuterait d'ailleurs pas en l'état : les
clés étrangères de `urim_corpus_examination` et `urim_corpus_token` sont en `NO ACTION`, et la
purge tombe dessus avant d'écrire quoi que ce soit.)*

Or `body_norm` et `urim_corpus_idf` ne sont **pas des données** : ce sont deux projections de
`body`, recalculables à tout instant par la fonction qui les a produites. Le seul texte que
personne ne réécrit — celui des traducteurs — est intact dans `body` et n'est jamais lu ici en
écriture. C'est ce qui autorise ce script à exister dans un dépôt qui se méfie de ce qui écrit.

## Les trois règles qu'il tient

**1. Les quatre témoins ensemble, ou aucun.** Martin écrit `coeur` en toutes lettres là où la
Segond, Darby et Ostervald écrivent `cœur`. Renormaliser une version et pas les autres
recréerait exactement le désaccord qu'on vient corriger — et `urim_collisions.py`, qui compare
deux `body_norm`, se mettrait à voir des divergences là où deux traducteurs ont écrit le même
mot. Le script ne prend donc **pas** de `--version` : ce serait offrir le moyen de casser
l'invariant.

**2. `body_norm` et l'idf dans la même transaction.** L'index du moteur est bâti sur les deux :
`load_corpus_index` découpe `body_norm` en tokens et les pèse avec l'idf. Des versets
renormalisés pesés par un lexique périmé, c'est la panne la plus discrète possible — le mot
`coeur` existerait dans le texte et vaudrait zéro dans la balance, donc n'ancrerait plus rien.
Une seule validation, ou rien.

**3. L'idf est refaite, pas rapiécée.** `idf = log((n + 1) / df)` : corriger quelques tokens
demanderait de connaître le `df` de tous. On recompte donc la Segond entière — comme le semis,
avec le même lissage — et on remet à `0.0` les mots du français courant que le texte ne porte
pas. Ces deux populations dans une seule table sont voulues (S34) : `known_words` les compte
toutes, `_ancres` ne retient que `idf > 0.0`. Perdre les secondes ferait taire le détecteur
d'entrée sur tout ce qui n'est pas biblique.

## Ce que le rapport dit et que rien ne corrige

`corpus_snapshot` est bâti sur des **comptages** — versions, versets, péricopes, pesées, date de
dernière relecture. Une renormalisation n'en change aucun. Les préparations déjà menées seront
donc rejouées contre un corpus qui répond autrement, avec `corpus_drifted` à faux. Le rapport le
dit avec son chiffre ; le réparer serait toucher à la clé du déterminisme, et c'est une décision.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, insert, select, update

from app.contexts.urim.engine.normalizer import normalize as normalise
from app.contexts.urim.infrastructure.corpus.index import SCHEMA_DE_REFERENCE
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusIdfModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.contexts.urim.infrastructure.persistence.models import UrimPreparationModel
from app.core.database import async_session_factory
from scripts.urim_seed_curation import LEXIQUE_FR

#: La seule langue que l'idf porte, et la seule que ce script touche. Le grec et l'hébreu ne
#: passent pas par le normaliseur : ils vivent dans `urim_corpus_token`, lemmatisés.
LANGUE = "fr"

#: ⚠️ Importé de l'index plutôt que redéclaré. L'idf est celle de la **Segond seule** : c'est
#: contre elle que la curation est écrite, et mélanger quatre traductions ferait compter quatre
#: fois le même verset — un mot présent partout deviendrait quatre fois plus banal qu'il n'est.
VERSION_DE_L_IDF = SCHEMA_DE_REFERENCE

#: Combien de versets réécrits on montre **par version**. Par version, et non en tout : les
#: 146 lignes de Martin se noieraient sous les 1 665 de Darby, et ce sont précisément celles
#: qu'il faut voir — c'est le témoin qui écrit déjà `coeur`, donc celui qu'on oublierait.
MONTRE_PAR_VERSION = 2

#: La largeur de l'extrait montré. Assez pour lire le mot dans sa phrase : hors contexte,
#: `c ur` a l'air d'une coquille de saisie plutôt que d'un mot coupé par l'outil.
FENETRE = 62


@dataclass
class Rattrapage:
    """Ce que le rapport a mesuré — et **exactement** ce que `--appliquer` écrira.

    Le même objet sert aux deux modes : le rapport ne peut donc pas décrire autre chose que ce
    qui sera écrit, ce qui est la seule façon honnête de faire relire une écriture en base."""

    #: `{"id", "body_norm"}` — **seulement les lignes qui changent.** Réécrire les 124 000
    #: versets rendrait le même résultat et rendrait le rapport illisible : « 4 994 lignes »
    #: se vérifie, « tout » ne se vérifie pas.
    versets: list[dict] = field(default_factory=list)
    par_version: dict[str, list[int]] = field(default_factory=dict)
    exemples: list[tuple[str, str, str]] = field(default_factory=list)

    #: La table `fr` entière, recalculée — remplaçante, pas complément.
    idf: list[dict] = field(default_factory=list)
    idf_avant: dict[str, float] = field(default_factory=dict)
    idf_apres: dict[str, float] = field(default_factory=dict)
    lexique_avant: int = 0

    preparations: int = 0

    @property
    def a_faire(self) -> bool:
        return bool(self.versets) or self.idf_avant != self.idf_apres


async def mesurer(s) -> Rattrapage:
    """Tout lire, tout recalculer, **ne rien écrire**. Le mode rapport s'arrête ici."""
    r = Rattrapage()

    codes = {
        v.id: v.code
        for v in (await s.execute(select(CorpusVersionModel))).scalars()
    }
    documents: list[list[str]] = []

    lignes = await s.stream(
        select(
            CorpusVerseModel.id, CorpusVerseModel.version_id,
            CorpusVerseModel.body, CorpusVerseModel.body_norm,
        )
    )
    async for identifiant, version_id, corps, ancienne in lignes:
        code = codes.get(version_id, "?")
        compte = r.par_version.setdefault(code, [0, 0])
        compte[1] += 1
        nouvelle = normalise(corps)
        if code == VERSION_DE_L_IDF:
            documents.append(nouvelle.split())
        if nouvelle == ancienne:
            continue
        compte[0] += 1
        r.versets.append({"id": identifiant, "body_norm": nouvelle})
        if sum(1 for e in r.exemples if e[0] == code) < MONTRE_PAR_VERSION:
            r.exemples.append((code, ancienne, nouvelle))

    # --- l'idf, recomptée exactement comme au semis --------------------------------
    df = Counter()
    for document in documents:
        df.update(set(document))
    n = len(documents)
    if not n:
        raise SystemExit(
            f"  aucune version « {VERSION_DE_L_IDF} » en base — il n'y a pas de corpus a "
            "rattraper. Semer avec : python scripts/seed_urim_corpus.py"
        )

    r.idf_apres = {token: math.log((n + 1) / freq) for token, freq in df.items()}
    r.idf = [
        {"language": LANGUE, "token": token, "idf": valeur}
        for token, valeur in r.idf_apres.items()
    ]
    # Les mots de la LANGUE, à idf nul. Re-dérivés de `LEXIQUE_FR` et non relus en base : la
    # table peut porter la trace de l'ancien normaliseur, et la recopier la perpétuerait.
    r.idf += [
        {"language": LANGUE, "token": mot, "idf": 0.0}
        for mot in {normalise(m) for m in LEXIQUE_FR}
        if mot and mot not in df
    ]

    for token, valeur in await s.execute(
        select(CorpusIdfModel.token, CorpusIdfModel.idf).where(
            CorpusIdfModel.language == LANGUE
        )
    ):
        if valeur > 0.0:
            r.idf_avant[token] = valeur
        else:
            r.lexique_avant += 1
    r.preparations = await s.scalar(
        select(func.count()).select_from(UrimPreparationModel).where(
            UrimPreparationModel.corpus_snapshot.is_not(None)
        )
    ) or 0
    return r


def _extraits(avant: str, apres: str) -> tuple[str, str]:
    """Les deux versions **cadrées sur l'endroit où elles divergent**.

    🔴 Tronquer à gauche ne marche pas : sur un verset dont le mot rendu tombe au caractère 90,
    les deux lignes affichées sont identiques et le rapport a l'air de mentir. Un contrôle qui
    montre parfois la preuve et parfois rien n'est pas un contrôle."""
    rupture = next(
        (i for i, (a, b) in enumerate(zip(avant, apres, strict=False)) if a != b),
        min(len(avant), len(apres)),
    )
    debut = max(0, rupture - FENETRE // 3)

    def coupe(texte: str) -> str:
        return (
            ("..." if debut else "")
            + texte[debut : debut + FENETRE]
            + ("..." if debut + FENETRE < len(texte) else "")
        )

    return coupe(avant), coupe(apres)


def rapporter(r: Rattrapage) -> None:
    """Le rapport — **le mot rendu, pas seulement le compte**.

    Un nombre de lignes ne se relit pas : personne ne sait dire si 4 994 est juste. Un verset
    montré avant/après se relit en une seconde, et c'est le seul contrôle qui vaut avant une
    écriture sur le corpus."""
    print("=" * 78)
    print("  RENORMALISATION DU CORPUS  —  body_norm + urim_corpus_idf")
    print("=" * 78)

    total = sum(c[0] for c in r.par_version.values())
    for code in sorted(r.par_version):
        change, tout = r.par_version[code]
        print(f"    {code:<10} {change:>6} / {tout:<7} versets a reecrire")
    print(f"    {'TOTAL':<10} {total:>6} lignes\n")

    if r.exemples:
        print("  ce que la reecriture rend :")
        for code, avant, apres in sorted(r.exemples):
            vu_avant, vu_apres = _extraits(avant, apres)
            print(f"    {code:<8} - {vu_avant}")
            print(f"    {'':<8} + {vu_apres}")
        print()

    disparus = sorted(r.idf_avant.keys() - r.idf_apres.keys())
    apparus = sorted(r.idf_apres.keys() - r.idf_avant.keys())
    bouges = sorted(
        (t for t in r.idf_avant.keys() & r.idf_apres.keys()
         if abs(r.idf_avant[t] - r.idf_apres[t]) > 1e-9),
        key=lambda t: -abs(r.idf_avant[t] - r.idf_apres[t]),
    )
    lexique = sum(1 for e in r.idf if e["idf"] == 0.0)

    print(f"  ancres du texte (idf > 0) : {len(r.idf_avant)} -> {len(r.idf_apres)}")
    print(f"    {len(disparus):>5} disparaissent   {' '.join(disparus[:14])}")
    print(f"    {len(apparus):>5} apparaissent    {' '.join(apparus[:10])}")
    print(f"    {len(bouges):>5} changent de poids")
    for token in bouges[:8]:
        print(f"          {token:<14} idf {r.idf_avant[token]:6.3f} -> "
              f"{r.idf_apres[token]:6.3f}")
    # Un mot du lexique qui **quitte** le lexique n'est pas une perte : c'est un mot que le
    # texte portait déjà et que la coupure rendait invisible. `soeur` était connu de la langue
    # et pesait zéro ; il pèse maintenant ce que la Segond en fait.
    print(f"  mots de la langue (idf 0) : {r.lexique_avant} -> {lexique}"
          f"   — les mots que le texte porte enfin passent du cote pesable")
    print()

    if not r.a_faire:
        print("  rien a faire — le corpus est deja normalise par la fonction en vigueur.")
        return

    # 🔴 Ce que le rapport doit dire et que l'écriture ne réparera pas.
    print("  " + "-" * 74)
    print(f"  ⚠️ {r.preparations} preparations portent un corpus_snapshot. Il est bati sur des")
    print("     COMPTAGES (versions, versets, pericopes, pesees) : renormaliser n'en change")
    print("     aucun. Ces preparations seront rejouees contre un corpus qui repond")
    print("     autrement, avec corpus_drifted a FAUX. Le signaler est tout ce que ce")
    print("     script peut faire — l'empreinte est la cle du determinisme.")
    print("  " + "-" * 74)


async def appliquer(s, r: Rattrapage) -> None:
    """Les deux écritures, **une seule validation**.

    Si la seconde échoue, la première ne doit pas survivre : un corpus renormalisé pesé par le
    lexique d'hier est plus faux que le corpus cassé d'avant — celui-là, au moins, était
    d'accord avec lui-même."""
    if r.versets:
        # Mise à jour en masse **par clé primaire** : un `UPDATE` par ligne coûterait quelques
        # minutes pour un résultat identique.
        await s.execute(update(CorpusVerseModel), r.versets)
    await s.execute(delete(CorpusIdfModel).where(CorpusIdfModel.language == LANGUE))
    await s.execute(insert(CorpusIdfModel), r.idf)
    await s.commit()
    print(f"  {len(r.versets)} versets reecrits, {len(r.idf)} entrees d'idf refaites.")
    print("  relancer avec --rapport doit maintenant dire « rien a faire ».")


async def executer(ecrire: bool) -> None:
    async with async_session_factory() as s:
        r = await mesurer(s)
        rapporter(r)
        if not ecrire:
            if r.a_faire:
                print("\n  rapport seul — relancer avec --appliquer pour ecrire.")
            return
        if not r.a_faire:
            return
        print()
        await appliquer(s, r)


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    # `--rapport` est le défaut **explicite** : une invocation nue ne doit pas écrire dans le
    # corpus, et une invocation nue ne doit pas non plus refuser de rendre service.
    analyseur.add_argument(
        "--rapport", action="store_true", help="mesurer sans rien ecrire (defaut)"
    )
    analyseur.add_argument(
        "--appliquer", action="store_true", help="ecrire body_norm et refaire l'idf"
    )
    arguments = analyseur.parse_args()
    if arguments.rapport and arguments.appliquer:
        raise SystemExit("  --rapport et --appliquer s'excluent : choisir.")
    asyncio.run(executer(ecrire=arguments.appliquer))


if __name__ == "__main__":
    main()
