"""Adaptateurs OTP : générateur de code sécurisé + envoi (dev = log).

Le port `OtpSender` est abstrait : en dev on **logge** le code (testable sans
fournisseur) ; en prod on branchera des adaptateurs email (Owner) et SMS (membre)
sans toucher au domaine.
"""

from __future__ import annotations

import secrets

from app.contexts.auth.application.ports import CodeGenerator, OtpSender
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.core.logging import get_logger

_logger = get_logger("auth.otp")


class SecureCodeGenerator(CodeGenerator):
    def __init__(self, length: int = 6) -> None:
        self._length = length

    def generate(self) -> str:
        # Code numérique à `length` chiffres, tiré cryptographiquement.
        return f"{secrets.randbelow(10**self._length):0{self._length}d}"


class LoggingOtpSender(OtpSender):
    """Dev-only : écrit le code dans les logs (⚠️ jamais en production)."""

    async def send(
        self, *, channel: OtpChannel, target: str, code: str, purpose: OtpPurpose
    ) -> None:
        _logger.info(
            "otp_issued_dev",
            channel=channel.value,
            target=target,
            purpose=purpose.value,
            code=code,  # DEV UNIQUEMENT
        )
