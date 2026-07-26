"""Objet-valeur : mot de passe **owner/backoffice** (≠ code secret PIN du membre)."""

from __future__ import annotations

from dataclasses import dataclass

from app._shared.domain.value_object import ValueObject
from app.contexts.auth.domain.errors import InvalidPasswordError

_MIN_LEN = 8


@dataclass(frozen=True)
class Password(ValueObject):
    """Mot de passe en clair le temps du hashage ; jamais stocké tel quel."""

    value: str

    def __post_init__(self) -> None:
        if len(self.value) < _MIN_LEN:
            raise InvalidPasswordError(
                f"Le mot de passe doit faire au moins {_MIN_LEN} caractères."
            )

    def __str__(self) -> str:  # évite toute fuite en log
        return "********"
