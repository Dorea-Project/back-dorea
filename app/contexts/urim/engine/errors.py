"""Les erreurs du moteur — des **bugs**, pas des issues métier.

Une résolution ambiguë, un couple homilétique impossible, un bornage contesté ne sont
pas des erreurs : ce sont des `Outcome` (`AWAIT`, `REFUSE`). Ce module ne contient donc
que ce qui signale un moteur mal construit — un étage qui rend un résultat sans motif,
un étage qui travaille sur un état incomplet. Cela ne se rattrape pas : cela se corrige.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base des défauts de construction du moteur."""


class EngineInvariantError(EngineError):
    """Un invariant du contrat est rompu (motif absent, `AWAIT` sans options)."""


class StagePrerequisiteError(EngineError):
    """Un étage s'exécute alors que ses prérequis manquent — l'ordre a été violé."""
