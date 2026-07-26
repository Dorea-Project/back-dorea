"""Objets-valeur — immuables, égalité structurelle."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Marqueur pour les objets-valeur.

    Un objet-valeur n'a pas d'identité : il est défini par ses attributs et est
    immuable. Les sous-classes se déclarent `@dataclass(frozen=True)` et
    valident leurs invariants dans `__post_init__`.
    """
