"""Objets-valeur du domaine IAM."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app._shared.domain.value_object import ValueObject
from app.contexts.iam.domain.errors import InvalidPhoneNumberError

# Format E.164 simplifié : « + » puis 8 à 15 chiffres.
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


@dataclass(frozen=True)
class PhoneNumber(ValueObject):
    """Clé d'identité globale du `Account` (spec métier §5.1).

    Normalisé en E.164. Le partage d'un numéro par un couple (faiblesse R3) n'est
    pas résolu ici : l'unicité par téléphone reste un invariant assumé.
    """

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().replace(" ", "")
        if not _E164.match(normalized):
            raise InvalidPhoneNumberError(
                "Numéro de téléphone invalide (format E.164 attendu, ex : +2250700000000).",
                details={"value": self.value},
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
