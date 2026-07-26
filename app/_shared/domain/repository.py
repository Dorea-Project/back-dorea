"""Port de persistance générique.

Un dépôt expose la collection d'un agrégat au domaine sans en révéler le
stockage. Les interfaces concrètes se déclarent dans chaque contexte
(`<contexte>/domain/repositories.py`) ; les implémentations vivent en
infrastructure. Rappel spec §14 : l'infrastructure lit/écrit la base partagée ;
le schéma est la propriété de ce backend, qui le fait évoluer.
"""

from abc import ABC


class Repository(ABC):  # noqa: B024 — marqueur ; les méthodes abstraites sont déclarées par contexte
    """Marqueur de port de dépôt. Les méthodes concrètes sont déclarées par contexte."""
