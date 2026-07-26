"""Générateur de codes d'invitation église — token URL-safe imprévisible (M-5)."""

from __future__ import annotations

import secrets

from app.contexts.iam.application.ports import InvitationCodeGenerator


class SecureInvitationCodeGenerator(InvitationCodeGenerator):
    def generate(self) -> str:
        # ~16 caractères URL-safe, tirés d'une source cryptographique.
        return secrets.token_urlsafe(12)
