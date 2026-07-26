"""DTO applicatifs du contexte Auth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # durée de vie de l'access token, en secondes
    token_type: str = "bearer"


@dataclass(frozen=True)
class MobileAuthOutcome:
    """Résultat du login mobile device-aware (M-4).

    Appareil de confiance → `tokens` présent. Appareil inconnu → un OTP SMS a été
    envoyé (`otp_required=True`), pas de jetons : l'appelant passe par `verify-device`.
    """

    tokens: TokenPair | None
    otp_required: bool
