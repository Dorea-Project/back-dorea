"""Le **digest** d'un sermon — le produit IA, généré en **un appel**, gelé après approbation.

C'est l'arbre que le compagnon déroulera au runtime (déterministe, zéro token) :
- `summary` — le résumé du sermon.
- `key_points` — les points essentiels (branche **« non »** : enseigner, rattraper).
- `capsules` — les pastilles publiées au fil (S-2).
- `questions` — le Q&R de consolidation (branche **« oui »** : approfondir ce qui a été reçu).

Objets de **valeur** immuables : l'IA rédige, le pasteur approuve, puis plus rien ne bouge.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capsule:
    """Une pastille courte, publiable au fil (comme une annonce)."""

    title: str
    body: str


@dataclass(frozen=True)
class CompanionQuestion:
    """Une question de réflexion + la **réponse préparée** qui emmène le membre à comprendre.

    Réflexion, pas examen : `guidance` console et approfondit, il ne note pas."""

    prompt: str
    guidance: str


@dataclass(frozen=True)
class SermonDigest:
    summary: str
    key_points: tuple[str, ...]
    capsules: tuple[Capsule, ...]
    questions: tuple[CompanionQuestion, ...]
