"""Ce que le monde sait au moment où une échéance tombe.

Un interpreter est pur : il ne compte pas les rencontres tenues d'un groupe, il ne lit pas les
paramètres de l'église. Mais l'échéance qui tombe a besoin de ces nombres — sinon elle ne peut
rien conclure.

La réponse est la même que partout ailleurs dans ce moteur : **ce qui se lit se lit une fois, dans
la couche applicative, et voyage dans le fait**. Le worker interroge ce port au moment du tir,
joint le résultat au payload du `CHECK_FIRED`, et l'interpreter n'a plus qu'à comparer des nombres
qui sont désormais dans le journal.

Ce détour n'est pas de la cérémonie : c'est ce qui rend le temps **rejouable**. Un rejeu ne
recompte rien — il relit ce que le monde disait ce jour-là, et rend donc exactement ce que le
direct a rendu. Recompter aujourd'hui les rencontres d'il y a six mois donnerait un autre résultat
dès qu'une saisie tardive arrive, et l'invariant de déterminisme tomberait sans bruit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class CheckContext(ABC):
    """Le complément de payload à joindre à une échéance qui tombe."""

    @abstractmethod
    async def for_check(self, check) -> Mapping[str, Any]:
        """Ce qu'il faut savoir pour interpréter **cette** échéance-ci, ou rien.

        Un régime d'échéance inconnu de l'adaptateur renvoie un dictionnaire vide : il ne fait pas
        échouer la passe, et l'interpreter du tir décidera qu'il n'y a rien à dire."""
        ...
