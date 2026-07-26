"""Générateur de codes d'invitation — token URL-safe imprévisible (G-1b)."""

from __future__ import annotations

import secrets

from app.contexts.groups.application.ports import InvitationCodeGenerator


class SecureInvitationCodeGenerator(InvitationCodeGenerator):
    def generate(self) -> str:
        # ~16 caractères URL-safe, tirés d'une source cryptographique.
        return secrets.token_urlsafe(12)
