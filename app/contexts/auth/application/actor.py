"""Acteur — principal authentifié à l'origine d'une requête.

Produit par le contexte Auth (décodage du JWT) et consommé par tous les autres
contextes (IAM, présences…). Le domaine ne connaît que cette abstraction, jamais
le token lui-même.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Actor:
    account_id: UUID
