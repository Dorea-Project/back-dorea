"""Objets-valeur du contexte Tenant."""

from __future__ import annotations

from dataclasses import dataclass

from app._shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class Location(ValueObject):
    """Localisation d'une église — regroupée pour être manipulée d'un bloc.

    Tous les champs sont optionnels : une localisation partiellement connue reste
    valide (au provisionnement on a souvent le pays/la ville, rarement lat/long).
    Réutilisable telle quelle pour les annexes (chacune a sa propre localisation).
    """

    country: str | None = None  # code ou nom du pays (ex. "CI")
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None
