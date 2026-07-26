"""Générateur de codes de lien d'invitation missionnaire — token URL-safe imprévisible."""

from __future__ import annotations

import secrets

from app.contexts.mission.application.ports import InvitationCodeGenerator


class SecureInvitationCodeGenerator(InvitationCodeGenerator):
    def generate(self) -> str:
        return secrets.token_urlsafe(9)  # ~12 caractères, source cryptographique
