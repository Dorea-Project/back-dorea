"""L'anniversaire — **une date déclarée, affichée au bon moment, pour provoquer un geste humain**.

> *Dorea rappelle aux humains d'aimer ; il n'aime jamais à leur place.*

Rien d'autre. Pas de fait au ledger, pas de cas, pas d'entrée dans le plafond, pas de notification
poussée, pas de message automatique. Un encart qui attend qu'on ouvre l'application, et le bouton
d'appel standard — Dorea fait sortir, comme toujours.

Quatre décisions tiennent dans ce fichier :

- **Jour et mois suffisent.** L'année est optionnelle et **n'est jamais affichée nulle part** :
  l'âge de quelqu'un n'est pas une donnée d'église. Elle n'existe que si le membre la donne, pour
  d'éventuels usages pastoraux futurs explicitement consentis — aucun aujourd'hui.
- **La visibilité est un enum fermé**, choisi par le membre, et `HIDDEN` éteint **tout** : l'encart,
  la réponse de l'assistant, la vue du pasteur. Même mécanique que `DO_NOT_CONTACT` — le réglage du
  membre absorbe, et aucune bonne intention ne le lève.
- **Ne pas renseigner sa date équivaut à `HIDDEN`.** Le champ est optionnel ; l'absence est une
  réponse.
- **Le 29 février s'affiche le 28 les années non bissextiles.** C'est le détail qui vexe s'il
  manque, et celui qu'on oublie toujours.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.contexts.iam.domain.errors import IamError


class InvalidBirthdayError(IamError):
    """Une date qui n'existe pas — le 31 février n'est l'anniversaire de personne."""

    code = "IAM_INVALID_BIRTHDAY"
    http_status = 422


class BirthdayScope(StrEnum):
    """Qui voit l'encart. Choisi par le membre, jamais déduit."""

    # Le défaut : l'anniversaire est un rituel communautaire dans les églises cibles.
    GROUPS = "groups"
    REFERENT_ONLY = "referent_only"  # celui qui le connaît, et personne d'autre
    HIDDEN = "hidden"  # personne — absolu, y compris pour l'assistant et le pasteur


DEFAULT_SCOPE = BirthdayScope.GROUPS


@dataclass(frozen=True)
class Birthday:
    """Un jour et un mois. L'année vit ailleurs et ne sort jamais d'ici."""

    day: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise InvalidBirthdayError(
                "Ce mois n'existe pas.", details={"month": self.month}
            )
        # 29 février est **accepté** : c'est une vraie date de naissance. Le décalage se fait à
        # l'affichage, pas à la saisie — refuser la date de quelqu'un serait absurde.
        longest = 29 if self.month == 2 else calendar.monthrange(2001, self.month)[1]
        if not 1 <= self.day <= longest:
            raise InvalidBirthdayError(
                "Ce jour n'existe pas dans ce mois.",
                details={"day": self.day, "month": self.month},
            )

    def falls_on(self, moment: date) -> bool:
        """Est-ce l'anniversaire ce jour-là ?

        **Le 29 février se fête le 28 les années non bissextiles.** Sans ça, une personne née le
        29 n'aurait un anniversaire qu'une année sur quatre — et c'est exactement le genre de
        détail qui fait dire que le produit ne pense pas aux gens."""
        if (self.day, self.month) == (moment.day, moment.month):
            return True
        if (self.day, self.month) == (29, 2) and (moment.day, moment.month) == (28, 2):
            return not calendar.isleap(moment.year)
        return False
