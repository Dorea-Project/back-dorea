"""Le banc de l'aiguilleur — **est-ce qu'il lit le pasteur, ou est-ce qu'il me lit moi ?**

On ne branche pas un aiguilleur pour voir. On mesure d'abord son taux de bon aiguillage sur des
saisies étiquetées, et on décide ensuite si le vocabulaire tient.

## La colonne qui rend ce banc honnête : `provenance`

⚠️ **Nous n'avons presque aucune saisie réelle de deuxième tour.** Tout ce que le Pasteur X a
écrit, ce sont des *ouvertures* — et l'aiguilleur ne voit jamais l'ouverture. Les cas marqués
`construit` sont donc les miens, et un banc qui mélangerait les deux mesurerait surtout si le
modèle est d'accord avec moi.

Le score est donc rendu **séparément**. Un banc moins capable que le réel fait passer un test
pour une preuve ; un banc plus complaisant que le réel fait la même chose, en pire — il donne
un chiffre.

## Ce que le banc ne mesure pas

Les **liaisons**. « Ecclésiologie », « L'unité », « Expositif » sont résolues par comparaison de
chaînes avant tout appel, et l'aiguilleur ne les voit jamais. Les mettre ici mesurerait une
erreur qui n'arrive pas en production.

    python scripts/urim_banc_aiguillage.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.contexts.urim.adapters.mistral import INTENTIONS_CONNUES, MistralAssistant
from app.core.config import get_settings

#: `reel` = écrit par un vrai pasteur, attesté dans le dépôt ou dans une capture de session.
#: `construit` = écrit par moi. Tout le reste du banc en dépend.
REEL, CONSTRUIT = "reel", "construit"


@dataclass(frozen=True)
class Cas:
    texte: str
    attendu: str
    provenance: str
    note: str = ""


_BANC: tuple[Cas, ...] = (
    # ---------------------------------------------------------------- interroger_travail
    Cas("Quel plan je peux tenir sur ce texte ?", "interroger_travail", REEL,
        "maquette urim_conversation.html, tour 5"),
    Cas("qu'est-ce qui resiste a mon axe ?", "interroger_travail", CONSTRUIT,
        "AMBIGU : porte sur le texte autant que sur l'evaluation"),
    Cas("j'ai choisi quoi deja ?", "interroger_travail", CONSTRUIT),
    Cas("est-ce que je peux faire un plan thematique la-dessus", "interroger_travail", CONSTRUIT),
    Cas("ou j'en suis", "interroger_travail", CONSTRUIT),
    Cas("y a un risque de proof texting sur ce que je fais ?", "interroger_travail", CONSTRUIT),

    # ---------------------------------------------------------------- interroger_texte
    Cas("pourquoi le pere fait mettre des souliers a ses pieds ?", "interroger_texte", CONSTRUIT,
        "scenario du 12/08, tire de la predication reelle sur le fils prodigue"),
    Cas("chez les hebreux les esclaves ne portaient pas de chaussures, c'est ca ?",
        "interroger_texte", CONSTRUIT,
        "LE CAS CENTRAL : fait historique non source — le repondeur doit refuser sans ecarter"),
    Cas("que veut dire upodema", "interroger_texte", CONSTRUIT),
    Cas("pourquoi le bloc se ferme au verset 16 ?", "interroger_texte", CONSTRUIT),
    Cas("c'est quoi le mot grec pour amour ici", "interroger_texte", CONSTRUIT),
    Cas("qui etait Zorobabel", "interroger_texte", CONSTRUIT),
    Cas("le verbe est a quel temps", "interroger_texte", CONSTRUIT),
    Cas("ce passage se passe quand par rapport a l'exil", "interroger_texte", CONSTRUIT),

    # ---------------------------------------------------------------- demander_production
    Cas("Propose-moi un theme.", "demander_production", REEL,
        "maquette urim_conversation.html, tour 6"),
    Cas("mets moi ca en powerpoint", "demander_production", CONSTRUIT),
    Cas("fais moi une fiche pour la chaire", "demander_production", CONSTRUIT),
    Cas("donne moi un titre", "demander_production", CONSTRUIT,
        "PIEGE : Urim propose un theme, jamais un titre — mais l'intention reste production"),

    # ---------------------------------------------------------------- preciser
    Cas("ce n'est pas ca", "preciser", REEL, "option `origin: entree` du produit"),
    Cas("non c'est une citation pas un sujet", "preciser", CONSTRUIT),
    Cas("je parlais du chapitre entier", "preciser", CONSTRUIT),
    Cas("tu as mal lu, c'est Jean pas Jean-Baptiste", "preciser", CONSTRUIT),

    # ---------------------------------------------------------------- changer_de_sujet
    Cas("en fait je vais precher sur autre chose", "changer_de_sujet", CONSTRUIT),
    Cas("laisse tomber, dimanche je fais la reconnaissance", "changer_de_sujet", CONSTRUIT),
    Cas("on reprend depuis le debut avec un autre texte", "changer_de_sujet", CONSTRUIT),

    # ---------------------------------------------------------------- hors_champ
    Cas("comment je dis ca a des jeunes qui ont quitte l'eglise ?", "hors_champ", CONSTRUIT,
        "scenario du 12/08"),
    Cas("un de mes diacres ne vient plus, je fais quoi", "hors_champ", CONSTRUIT),
    Cas("comment annoncer ca a une assemblee en deuil", "hors_champ", CONSTRUIT),
    Cas("est-ce que je dois etre plus dur avec eux", "hors_champ", CONSTRUIT),
    Cas("prie pour moi", "hors_champ", CONSTRUIT,
        "TROUVE PAR LE BANC : partait en indechiffrable. Un message clair qu'on ne sait pas "
        "satisfaire n'est pas du bruit — repondre « je n'ai pas su lire » a un pasteur seul "
        "un samedi soir traiterait une adresse reelle comme un parasite"),
    Cas("tu penses quoi de moi", "hors_champ", CONSTRUIT),
    Cas("t'es qui toi exactement", "hors_champ", CONSTRUIT),

    # ---------------------------------------------------------------- indechiffrable
    Cas("Ma voiture 406, a besoin de reparation , jefgf Paradis", "indechiffrable", REEL,
        "documente dans engine/state.py — le micro reste ouvert (S36)"),
    Cas("attends deux minutes je arrive euh le fils la le retour bon", "indechiffrable",
        CONSTRUIT, "dictee en marchant"),
    Cas("oui", "indechiffrable", CONSTRUIT, "TROU CONNU : un acquiescement n'a pas de code"),
    Cas("ok", "indechiffrable", CONSTRUIT, "idem"),
    Cas("mmmh", "indechiffrable", CONSTRUIT),
    Cas("...", "indechiffrable", CONSTRUIT),
)


@dataclass
class Verdict:
    cas: Cas
    obtenu: str | None

    @property
    def juste(self) -> bool:
        return self.obtenu == self.cas.attendu


async def _passer(assistant: MistralAssistant) -> list[Verdict]:
    verdicts: list[Verdict] = []
    for cas in _BANC:
        obtenu = await assistant.aiguiller(cas.texte)
        verdicts.append(Verdict(cas, obtenu))
        marque = "OK " if obtenu == cas.attendu else "NON"
        print(f"  {marque}  {cas.attendu:<20} -> {obtenu!s:<20} {cas.texte[:44]}")
    return verdicts


def _taux(verdicts: list[Verdict]) -> str:
    if not verdicts:
        return "—"
    justes = sum(1 for v in verdicts if v.juste)
    return f"{justes}/{len(verdicts)}  ({100 * justes / len(verdicts):.0f} %)"


def _rapport(verdicts: list[Verdict]) -> None:
    print("\n" + "=" * 78)
    print("  TAUX DE BON AIGUILLAGE")
    print("=" * 78)
    print(f"  ensemble du banc        {_taux(verdicts)}")
    print(f"  saisies REELLES         {_taux([v for v in verdicts if v.cas.provenance == REEL])}")
    print(f"  saisies construites     "
          f"{_taux([v for v in verdicts if v.cas.provenance == CONSTRUIT])}")
    print("\n  ⚠️  Le second chiffre est le seul qui parle du pasteur. Le troisieme dit")
    print("      surtout si le modele est d'accord avec moi.")

    print("\n" + "=" * 78)
    print("  PAR INTENTION")
    print("=" * 78)
    for intention in sorted(INTENTIONS_CONNUES):
        lot = [v for v in verdicts if v.cas.attendu == intention]
        if lot:
            print(f"  {intention:<22} {_taux(lot)}")

    confusions = Counter(
        (v.cas.attendu, v.obtenu) for v in verdicts if not v.juste
    )
    if confusions:
        print("\n" + "=" * 78)
        print("  OU IL SE TROMPE  (attendu -> obtenu)")
        print("=" * 78)
        for (attendu, obtenu), n in confusions.most_common():
            print(f"  {n} x  {attendu:<22} -> {obtenu}")

    rates = [v for v in verdicts if not v.juste]
    if rates:
        print("\n" + "=" * 78)
        print("  LES CAS RATES, EN ENTIER")
        print("=" * 78)
        for v in rates:
            print(f"\n  « {v.cas.texte} »")
            print(f"    attendu {v.cas.attendu}, obtenu {v.obtenu}  [{v.cas.provenance}]")
            if v.cas.note:
                print(f"    note : {v.cas.note}")


async def main() -> None:
    settings = get_settings()
    if not settings.mistral_api_key:
        print("MISTRAL_API_KEY absente — rien a mesurer.")
        return
    print(f"Modele : {settings.mistral_model}   —   {len(_BANC)} cas\n")
    assistant = MistralAssistant(settings.mistral_api_key, settings.mistral_model)
    _rapport(await _passer(assistant))


if __name__ == "__main__":
    asyncio.run(main())
