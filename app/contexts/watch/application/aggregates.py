"""La lecture **non nominative** de la veille — des nombres, jamais des gens.

Un cas de veille est nominatif par nature : il porte un `subject_id`, parce qu'on ne prend soin
de personne en général. Mais d'autres surfaces ont besoin de savoir **combien**, sans jamais
savoir **qui** — un tableau de bord de dénomination, l'écran de préparation d'un prédicateur.

Ce module est la seule porte par laquelle un nombre sort de la veille. Il ne protège pas par
convention : **il protège par construction**.

- `TopicCount` **n'a aucun champ d'identité**. Une implémentation buggée, ou pressée, n'a nulle
  part où glisser un `subject_id` : le type ne le permet pas.
- Le seuil est appliqué **dans la requête** (`HAVING count >= 5`). Un groupe sous le seuil ne
  quitte jamais la base — il n'est pas filtré après coup, il n'est jamais lu.

Un agrégat de deux personnes désigne deux personnes : dans une cellule de huit, « deux malades »
se devine. C'est pourquoi le seuil n'est pas un réglage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

#: Sous ce seuil, un agrégat redevient nominatif par déduction. Ce n'est pas un paramètre.
#: (Le contexte `urim` porte la même valeur de son côté — les contextes ne partagent rien.)
CONFIDENTIALITY_THRESHOLD: int = 5


@dataclass(frozen=True, slots=True)
class TopicCount:
    """Un nombre, un sujet, une fenêtre. **Aucun identifiant — et aucune place pour en mettre.**"""

    topic: str  # l'origine du dire (`CasePriority`), jamais un nom
    headcount: int
    window_days: int


class AggregateReader(ABC):
    """Lecture agrégée de la veille — la seule porte de sortie non nominative."""

    @abstractmethod
    async def counts_by_origin(
        self, tenant_id: UUID, *, window_days: int
    ) -> tuple[TopicCount, ...]:
        """Cas ouverts sur la fenêtre, groupés par origine, **seuil appliqué en base**.

        Les origines qui comptent moins de `CONFIDENTIALITY_THRESHOLD` personnes ne sont pas
        rendues — elles ne sont pas non plus lues."""
        ...
