"""Traduire le lexique — **le second geste, et le seul qui produise du texte**.

L'acquisition (`urim_seed_lexique.py`) a rempli `gloss_source` depuis TBESG. Celui-ci remplit
`gloss` en français, et il est séparé pour une raison de fond : **ce qui est acquis et ce qui
est produit ne se mélangent pas.** L'un se rejoue sans refaire l'autre, et on sait toujours
lequel des deux est en cause quand une glose surprend.

## La règle que ce script ne franchit pas

> **On traduit une source publiée. On n'écrit pas une définition.**

C'est la décision L1, et elle ne tient qu'à trois conditions, toutes vérifiables dans la base :

1. `gloss_source` reste **à côté** de la traduction, mot pour mot ;
2. `gloss_source_ref` dit d'où elle vient, `strong_code` la rend traçable ;
3. **rien n'est traduit qui ne soit sourcé** — un lemme sans `gloss_source` reste sans glose,
   et ce script ne le regarde même pas.

⚠️ **Pas de périphrase.** « sandal » se traduit « sandale », jamais « ce qu'on porte sous le
pied » : la seconde formule est une *définition*, et le lexique ne la donne pas. Le sens
descriptif que cherche le pasteur vient de la **concordance** — les trois versets où le mot
paraît — qui, elle, ne peut rien inventer.

Usage :
    python scripts/urim_traduire_lexique.py --limite 40          # essai
    python scripts/urim_traduire_lexique.py --tout               # la passe complète
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.core.config import Settings

#: Combien de gloses par appel. Assez pour que le coût soit raisonnable, assez peu pour qu'une
#: réponse mal formée ne coûte que son lot.
LOT = 25

_SYSTEME = (
    "Tu traduis en français des gloses d'un lexique biblique grec (Abbott-Smith). "
    "Chaque entrée est une définition TRÈS BRÈVE — un ou quelques mots. "
    "Ta tâche est de la TRADUIRE, pas de l'expliquer ni de la développer. "
    "RÈGLES ABSOLUES : "
    "(1) n'ajoute AUCUN sens que l'anglais ne porte pas ; "
    "(2) garde la même longueur — une glose de deux mots reste une glose de deux mots ; "
    "(3) garde les séparateurs tels quels : 'spirit/breath: spirit' devient "
    "'esprit/souffle : esprit' ; "
    "(4) pour un nom propre (personne, ville, peuple), donne la forme française usuelle ; "
    "(5) aucune note, aucune parenthèse explicative, aucune majuscule ajoutée. "
    "Réponds par un objet JSON : {\"gloses\": [{\"id\": <entier>, \"fr\": \"...\"}]} — "
    "une entrée par identifiant reçu, dans le même ordre."
)


async def principal(limite: int | None, lemmes: list[str]) -> None:
    reglages = Settings()
    if not reglages.mistral_api_key:
        print("aucune clé Mistral : rien à faire.")
        return
    modele = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)
    moteur = create_async_engine(str(reglages.database_url))

    condition = "gloss_source IS NOT NULL AND gloss IS NULL"
    if lemmes:
        condition = "gloss_source IS NOT NULL AND lemma = ANY(:lemmes)"
    async with moteur.connect() as cx:
        rangs = (await cx.execute(
            text(
                f"SELECT id, lemma, gloss_source FROM urim_corpus_lemma WHERE {condition}"
                " ORDER BY id" + (f" LIMIT {int(limite)}" if limite else "")
            ),
            {"lemmes": lemmes} if lemmes else {},
        )).all()

    print(f"à traduire : {len(rangs)}")
    traduits = 0
    for depart in range(0, len(rangs), LOT):
        lot = rangs[depart:depart + LOT]
        demande = json.dumps(
            [{"id": i, "en": g} for i, _l, g in lot], ensure_ascii=False
        )
        contenu = await modele.demander(_SYSTEME, demande, etiquette="lexique")
        if not contenu:
            print(f"  lot {depart // LOT + 1} : aucune réponse, passé")
            continue
        try:
            rendus = json.loads(contenu).get("gloses", [])
        except json.JSONDecodeError:
            print(f"  lot {depart // LOT + 1} : réponse illisible, passé")
            continue

        async with moteur.begin() as cx:
            for rendu in rendus:
                francais = (rendu.get("fr") or "").strip()
                if not francais:
                    # ⚠️ Une glose vide n'est pas une traduction : on préfère le silence.
                    continue
                await cx.execute(
                    text(
                        "UPDATE urim_corpus_lemma SET gloss = :fr, gloss_model = :m"
                        " WHERE id = :id AND gloss_source IS NOT NULL"
                    ),
                    {"fr": francais, "m": reglages.mistral_model, "id": rendu.get("id")},
                )
                traduits += 1
        print(f"  lot {depart // LOT + 1} : {len(rendus)} rendus")

    await moteur.dispose()
    print(f"traduits : {traduits}")


if __name__ == "__main__":
    args = sys.argv[1:]
    limite = None if "--tout" in args else 40
    if "--limite" in args:
        limite = int(args[args.index("--limite") + 1])
    choisis = args[args.index("--lemmes") + 1].split(",") if "--lemmes" in args else []
    asyncio.run(principal(limite, choisis))
