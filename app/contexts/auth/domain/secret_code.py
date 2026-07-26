"""Objet-valeur : le « code secret » du fidèle (PIN)."""

from __future__ import annotations

from dataclasses import dataclass

from app._shared.domain.value_object import ValueObject
from app.contexts.auth.domain.errors import InvalidSecretCodeFormatError

_MIN_LEN = 4
_MAX_LEN = 6


@dataclass(frozen=True)
class SecretCode(ValueObject):
    """PIN numérique de 4 à 6 chiffres.

    Représente le secret *en clair* le temps de la vérification/du hashage ; il
    n'est jamais stocké tel quel (seul son hash argon2id l'est, côté `accounts`).
    """

    value: str

    def __post_init__(self) -> None:
        v = self.value.strip()
        if not (v.isdigit() and _MIN_LEN <= len(v) <= _MAX_LEN):
            raise InvalidSecretCodeFormatError(
                f"Le code secret doit être un nombre de {_MIN_LEN} à {_MAX_LEN} chiffres.",
            )
        object.__setattr__(self, "value", v)

    def __str__(self) -> str:  # évite toute fuite accidentelle en log
        return "******"
