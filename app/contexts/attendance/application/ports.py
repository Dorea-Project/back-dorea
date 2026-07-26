"""Ports du contexte Présence."""

from abc import ABC, abstractmethod


class SessionCodeGenerator(ABC):
    """Génère un **code de séance** court et lisible (le membre le tape, M6-1)."""

    @abstractmethod
    def generate(self) -> str: ...
