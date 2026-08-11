"""Combien coûte **une ouverture d'étude** — mesuré, pas estimé.

On a raisonné longtemps sur un plafond sans connaître ce chiffre. Il décide pourtant de tout :
si une ouverture coûte un demi-centime, le plafond est une garde anti-abus et le modèle
économique doit venir d'ailleurs ; si elle coûte dix centimes, c'est un vrai poste.

**La mesure porte sur les saisies réelles du Pasteur X**, pas sur des exemples fabriqués. Une
invite se mesure sur ce qu'on lui envoie vraiment : un thème de deux lignes et une référence
sèche ne consomment pas la même chose, et c'est le mélange réel qui donne le coût réel.

Les tarifs sont en dur et datés : ils ne sont pas lisibles par l'API. À revérifier sur la page
de facturation avant de fonder une décision dessus.

    python scripts/urim_mesure_cout.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.contexts.urim.adapters.mistral import (
    _SYSTEME_AXES,
    _SYSTEME_PASSAGES,
    _SYSTEME_REFERENCE,
    _SYSTEME_RISQUE,
    MistralAssistant,
)
from app.core.config import get_settings

#: Tarif mistral-small, USD par million de jetons — relevé le 11/08/2026.
_USD_ENTREE = 0.20
_USD_SORTIE = 0.60
_USD_EUR = 0.92

#: Les saisies réelles, telles que le pasteur les a écrites.
_SAISIES = [
    ("conviction", "Dieu est l'auteur et le consommateur de notre foi, sur l'autel Divin"),
    ("conviction", "Celui qui maintient notre Foi jusqu'a l'ascension"),
    ("conviction", "l'amour fraternel n'existe plus dans l'eglise"),
    ("reference", "le fils prodigue rentre chez son pere"),
    ("reference", "Jn 14v28"),
]

#: Ce qu'une ouverture déclenche vraiment, par mode d'entrée (cf. study_service).
_APPELS = {
    "conviction": (("axes", _SYSTEME_AXES), ("risque", _SYSTEME_RISQUE),
                   ("passages", _SYSTEME_PASSAGES)),
    "reference": (("reference", _SYSTEME_REFERENCE),),
}


@dataclass
class Releve:
    mode: str
    saisie: str
    invite: str
    entree: int
    sortie: int

    @property
    def usd(self) -> float:
        return (self.entree * _USD_ENTREE + self.sortie * _USD_SORTIE) / 1_000_000


async def _mesurer(assistant: MistralAssistant) -> list[Releve]:
    releves: list[Releve] = []
    for mode, saisie in _SAISIES:
        for invite, systeme in _APPELS[mode]:
            reponse = await assistant._client.chat.complete_async(
                model=assistant._model,
                messages=[
                    {"role": "system", "content": systeme},
                    {"role": "user", "content": saisie},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            u = reponse.usage
            releves.append(
                Releve(mode, saisie, invite, u.prompt_tokens, u.completion_tokens)
            )
            print(f"  {mode:<11} {invite:<10} {u.prompt_tokens:>5} → {u.completion_tokens:>4}")
    return releves


def _rapport(releves: list[Releve]) -> None:
    print("\n" + "=" * 70)
    print("  COÛT PAR INVITE")
    print("=" * 70)
    for invite in ("axes", "risque", "passages", "reference"):
        lot = [r for r in releves if r.invite == invite]
        if not lot:
            continue
        e = sum(r.entree for r in lot) / len(lot)
        s = sum(r.sortie for r in lot) / len(lot)
        usd = sum(r.usd for r in lot) / len(lot)
        print(f"  {invite:<10} {e:>7.0f} entrée {s:>6.0f} sortie   {usd * 100:>7.4f} ¢")

    print("\n" + "=" * 70)
    print("  COÛT PAR OUVERTURE")
    print("=" * 70)
    for mode in ("conviction", "reference"):
        lot = [r for r in releves if r.mode == mode]
        if not lot:
            continue
        n = len({r.saisie for r in lot})
        usd = sum(r.usd for r in lot) / n
        print(
            f"  {mode:<11} {len(lot) // n} appel(s)   "
            f"{usd * 100:>7.4f} ¢ = {usd * _USD_EUR * 100:>7.4f} c€"
        )

    pire = max(
        sum(r.usd for r in releves if r.mode == m) / len({r.saisie for r in releves if r.mode == m})
        for m in ("conviction", "reference")
    )
    print("\n" + "=" * 70)
    print("  CE QUE ÇA DONNE À L'ÉCHELLE  (hypothèse la plus chère par ouverture)")
    print("=" * 70)
    for label, ouvertures in (
        ("1 pasteur, 20 ouvertures/mois", 20),
        ("100 pasteurs actifs / mois", 2_000),
        ("1 000 pasteurs actifs / mois", 20_000),
        ("10 000 pasteurs actifs / mois", 200_000),
    ):
        print(f"  {label:<32} {pire * ouvertures * _USD_EUR:>10.2f} €")


async def main() -> None:
    settings = get_settings()
    if not settings.mistral_api_key:
        print("MISTRAL_API_KEY absente — rien à mesurer.")
        return
    print(f"Modèle : {settings.mistral_model}\n")
    assistant = MistralAssistant(settings.mistral_api_key, settings.mistral_model)
    _rapport(await _mesurer(assistant))


if __name__ == "__main__":
    asyncio.run(main())
