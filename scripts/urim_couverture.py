"""**Le corpus est-il prêt à accueillir n'importe quel message ?**

Pas « répond-il bien sur Romains 12 » — celui-là on l'a regardé cent fois. La question est la
couverture : sur les 4 561 unités, combien portent une pesée, une faisabilité, une note de
contexte, une mise en garde ? Et les chemins d'accès — sujet, source de plan, IDF — sont-ils
remplis, ou vides ?

⚠️ **Une couverture partielle ne laisse pas seulement des trous : elle détruit le sens des
trous.** Le produit distingue `absent` — *quelqu'un a regardé et le texte n'en dit rien* — de
l'absence de ligne — *personne n'a regardé*. Cette distinction ne vaut que si la curation a
balayé **tout** le corpus. Curée à 0,2 %, l'absence de ligne ne dit plus rien du tout.

    python scripts/urim_couverture.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

#: Les dimensions de la curation, mesurées **en unités couvertes**, pas en lignes : mille
#: pesées sur dix péricopes ne couvrent pas le corpus, elles couvrent dix textes.
_COUVERTURE = (
    ("pesées doctrinales", "urim_corpus_doctrinal_bearing"),
    ("faisabilité homilétique", "urim_corpus_homiletic_feasibility"),
    ("notes de contexte", "urim_corpus_context_note"),
    ("mises en garde", "urim_corpus_doctrinal_caveat"),
)

#: ⚠️ **Ce qui a été EXAMINÉ, et non ce qui porte une trouvaille.**
#:
#: 🔴 Ce script a annoncé « mises en garde : 41,2 % » le jour où 96 % du corpus avait été
#: examiné — parce qu'il comptait les unités qui portaient une ligne, et que 2 525 unités
#: n'en appelaient légitimement aucune. Compter la trouvaille fait passer un travail fini
#: pour un travail à moitié fait, et pousse à le refaire.
_EXAMEN = (
    ("mises en garde", "caveat"),
    ("notes de contexte", "context_note"),
)

#: Les chemins par lesquels un message peut atteindre un texte. Vides, le corpus n'est
#: joignable que par la lettre et par le modèle.
_ACCES = (
    ("sujets traités", "SELECT count(*) FROM urim_corpus_subject_matter"),
    ("sources de plan", "SELECT count(*) FROM urim_corpus_plan_source"),
    ("IDF (lemmes pesés)", "SELECT count(*) FROM urim_corpus_idf"),
    ("lemmes français", "SELECT count(*) FROM urim_corpus_lemma WHERE language = 'fr'"),
    ("lemmes grecs", "SELECT count(*) FROM urim_corpus_lemma WHERE language = 'grc'"),
    ("lemmes hébreux", "SELECT count(*) FROM urim_corpus_lemma WHERE language = 'hbo'"),
    ("variantes textuelles", "SELECT count(*) FROM urim_corpus_textual_variant"),
    ("versions", "SELECT count(*) FROM urim_corpus_version"),
)

#: ⚠️ **La question qui compte n'est pas « combien de mots », c'est « sur combien de versets le
#: pasteur obtient-il un original ? ».** 137 554 mots grecs sonnent bien et ne couvrent qu'un
#: quart du corpus : l'Ancien Testament fait les trois quarts des unités.
_ORIGINAL = (
    ("Ancien Testament", "book_id <= 39"),
    ("Nouveau Testament", "book_id > 39"),
)

#: La version contre laquelle tout le corpus curé a été écrit.
_VERSION_DE_CURATION = "LSG"


async def main() -> None:
    moteur = create_async_engine(str(get_settings().database_url))
    async with moteur.connect() as cnx:

        async def un(q: str) -> int:
            return (await cnx.execute(text(q))).scalar() or 0

        total = await un("SELECT count(*) FROM urim_corpus_pericope")
        at = await un("SELECT count(*) FROM urim_corpus_pericope WHERE book_id <= 39")

        print("=" * 66)
        print(f"  COUVERTURE DE LA CURATION   —   {total} unités")
        print(f"  Ancien Testament {at} ({100 * at / total:.0f} %)"
              f"   ·   Nouveau Testament {total - at}")
        print("=" * 66)
        for nom, table in _COUVERTURE:
            couvertes = await un(
                f"SELECT count(DISTINCT pericope_id) FROM {table}"
            )
            part = 100 * couvertes / total if total else 0
            barre = "#" * int(part / 4) + "." * (25 - int(part / 4))
            print(f"  {nom:<26} {couvertes:>6} / {total}  {barre} {part:5.1f} %")

        print("\n" + "=" * 66)
        print("  L'EXAMEN  —  unités regardées, trouvaille ou non")
        print("=" * 66)
        for nom, dimension in _EXAMEN:
            examinees = await un(
                "SELECT count(*) FROM urim_corpus_examination "
                f"WHERE dimension = '{dimension}'"
            )
            vides = await un(
                "SELECT count(*) FROM urim_corpus_examination "
                f"WHERE dimension = '{dimension}' AND found = 0"
            )
            part = 100 * examinees / total if total else 0
            barre = "#" * int(part / 4) + "." * (25 - int(part / 4))
            print(f"  {nom:<26} {examinees:>6} / {total}  {barre} {part:5.1f} %")
            if examinees:
                print(f"  {'dont sans trouvaille':<26} {vides:>6}"
                      f"          ({100 * vides / examinees:.0f} % — reponse juste)")

        print("\n" + "=" * 66)
        print("  LA LANGUE D'ORIGINE  —  versets où le pasteur en obtient une")
        print("=" * 66)
        for nom, filtre in _ORIGINAL:
            # ⚠️ **Nommer la version, sinon on compte trois Bibles.** Le corpus en porte
            # désormais trois : sans ce filtre, l'Ancien Testament compterait 69 000 versets et
            # la couverture serait divisée par trois.
            #
            # 🔴 Corrigé ici *avant* d'avoir menti, parce que le même oubli venait d'être
            # trouvé dans le détecteur d'écarts, où il avait accusé d'invention treize citations
            # parfaitement exactes. Le semis de Darby et de Martin a cassé un instrument de
            # qualité en silence ; c'est la classe de défaut qu'il fallait aller chercher
            # ailleurs plutôt qu'attendre.
            versets = await un(
                "SELECT count(*) FROM urim_corpus_verse v"
                " JOIN urim_corpus_version x ON x.id = v.version_id"
                f" WHERE x.code = '{_VERSION_DE_CURATION}' AND v.{filtre}"
            )
            avec = await un(
                "SELECT count(DISTINCT v.id) FROM urim_corpus_verse v"
                " JOIN urim_corpus_version x ON x.id = v.version_id"
                " JOIN urim_corpus_token t ON t.verse_id = v.id"
                f" WHERE x.code = '{_VERSION_DE_CURATION}' AND v.{filtre}"
            )
            part = 100 * avec / versets if versets else 0
            barre = "#" * int(part / 4) + "." * (25 - int(part / 4))
            print(f"  {nom:<26} {avec:>6} / {versets}  {barre} {part:5.1f} %")

        print("\n" + "=" * 66)
        print("  CHEMINS D'ACCÈS  —  par où un message atteint un texte")
        print("=" * 66)
        for nom, q in _ACCES:
            n = await un(q)
            print(f"  {nom:<26} {n:>8}    {'VIDE' if n == 0 else ''}")

    await moteur.dispose()


if __name__ == "__main__":
    asyncio.run(main())
