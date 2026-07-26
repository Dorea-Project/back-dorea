"""Générateur de code de séance — court, lisible, imprévisible (M6-1)."""

from __future__ import annotations

import secrets

from app.contexts.attendance.application.ports import SessionCodeGenerator

# Alphabet sans caractères ambigus (pas de 0/O/1/I) — facile à lire et à taper.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_LENGTH = 6


class SecureSessionCodeGenerator(SessionCodeGenerator):
    def generate(self) -> str:
        return "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))
