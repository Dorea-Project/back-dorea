"""Service OTP — émission et vérification d'un code à usage unique.

Génère un code, en stocke le **hash** (jamais le clair), l'envoie via `OtpSender`,
puis le vérifie : non expiré, non consommé, non verrouillé (anti brute-force), et
correspondant. Un succès **consomme** le défi (usage unique).
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from app.contexts.auth.application.ports import CodeGenerator, OtpSender, PasswordHasher
from app.contexts.auth.domain.errors import (
    OtpExpiredError,
    OtpInvalidError,
    OtpNotFoundError,
    OtpTooManyAttemptsError,
)
from app.contexts.auth.domain.otp import OtpChallenge, OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import OtpChallengeRepository


class OtpService:
    def __init__(
        self,
        challenges: OtpChallengeRepository,
        sender: OtpSender,
        hasher: PasswordHasher,
        codes: CodeGenerator,
        *,
        clock,
        ttl_seconds: int,
    ) -> None:
        self._challenges = challenges
        self._sender = sender
        self._hasher = hasher
        self._codes = codes
        self._clock = clock
        self._ttl_seconds = ttl_seconds

    async def issue(
        self,
        *,
        purpose: OtpPurpose,
        channel: OtpChannel,
        target: str,
        account_id: UUID | None = None,
        device_id: str | None = None,
    ) -> None:
        code = self._codes.generate()
        now = self._clock()
        challenge = OtpChallenge(
            id=uuid4(),
            purpose=purpose,
            channel=channel,
            target=target,
            code_hash=self._hasher.hash(code),
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            account_id=account_id,
            device_id=device_id,
        )
        await self._challenges.add(challenge)
        await self._sender.send(channel=channel, target=target, code=code, purpose=purpose)

    async def verify(self, *, purpose: OtpPurpose, target: str, code: str) -> OtpChallenge:
        """Retourne le défi consommé si le code est valide, sinon lève."""
        now = self._clock()
        challenge = await self._challenges.get_active(purpose, target, now)
        if challenge is None:
            raise OtpNotFoundError("Aucun code en attente pour ce contact.")
        if challenge.is_locked:
            raise OtpTooManyAttemptsError("Trop de tentatives — demandez un nouveau code.")
        if challenge.is_expired(now):
            raise OtpExpiredError("Ce code a expiré.")

        if not self._hasher.verify(challenge.code_hash, code):
            await self._challenges.increment_attempts(challenge.id)
            raise OtpInvalidError("Code invalide.")

        await self._challenges.mark_consumed(challenge.id, now)
        return challenge
