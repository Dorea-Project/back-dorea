"""Domaine OTP — code à usage unique pour vérifier un contact ou un nouvel appareil.

L'OTP est une **preuve de possession** (d'un email, d'un numéro, d'un appareil),
appelée à des instants sensibles : activation à l'onboarding (Owner), connexion
depuis un **nouvel appareil**, et changements sensibles côté membre (numéro / code
secret). Le code en clair n'est jamais stocké — seul son hash l'est.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app._shared.domain.entity import Entity

MAX_ATTEMPTS = 5  # au-delà, le défi est verrouillé (anti brute-force)


class OtpChannel(StrEnum):
    EMAIL = "email"  # Owner / backoffice
    SMS = "sms"  # Membre / mobile


class OtpPurpose(StrEnum):
    ONBOARDING_EMAIL = "onboarding_email"  # activer le compte Owner à l'inscription
    MOBILE_REGISTRATION = "mobile_registration"  # membre — auto-inscription mobile (M-1)
    NEW_DEVICE = "new_device"  # connexion depuis un appareil inconnu
    CHANGE_PHONE = "change_phone"  # membre — changement de numéro
    CHANGE_PASSWORD = "change_password"  # membre — changement de code secret
    #: ⚠️ **Distinct de `CHANGE_PASSWORD`, et ce n'est pas un détail.** Celui-ci s'obtient
    #: SANS être connecté — c'est tout son objet. Réutiliser le même motif laisserait rejouer
    #: dans un contexte anonyme un code émis pour un porteur déjà authentifié : le motif est
    #: précisément ce qui empêche un OTP de voyager d'une porte à l'autre.
    RESET_SECRET_CODE = "reset_secret_code"  # membre — code secret oublié


class OtpChallenge(Entity):
    """Un défi OTP émis vers un `target` (email ou numéro) dans un `purpose` donné."""

    def __init__(
        self,
        *,
        id: UUID,
        purpose: OtpPurpose,
        channel: OtpChannel,
        target: str,
        code_hash: str,
        created_at: datetime,
        expires_at: datetime,
        account_id: UUID | None = None,
        device_id: str | None = None,
        consumed_at: datetime | None = None,
        attempts: int = 0,
    ) -> None:
        self.id = id
        self.purpose = purpose
        self.channel = channel
        self.target = target
        self.code_hash = code_hash
        self.created_at = created_at
        self.expires_at = expires_at
        self.account_id = account_id
        self.device_id = device_id
        self.consumed_at = consumed_at
        self.attempts = attempts

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_locked(self) -> bool:
        return self.attempts >= MAX_ATTEMPTS
