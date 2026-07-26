"""Événements de domaine — faits métier révolus.

⚠️ Spec §14 : « les 6 alertes sont des non-événements », aucun broker. Ces
objets servent à exprimer des faits dans le modèle et à les journaliser ; ils
ne sont pas publiés sur un bus.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainEvent:
    """Marqueur pour un fait métier révolu (immuable)."""
