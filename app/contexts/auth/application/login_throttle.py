"""Frein de login (DOREA-004) — enveloppe la vérification de credentials.

Avant de vérifier, on refuse si l'identifiant est **verrouillé** (429) ; on **compte** chaque
échec ; on **remet à zéro** au succès. Le verrou masque aussi l'oracle « bon/mauvais secret »
pendant qu'il est actif. Best-effort DI : `None` côté appelant = pas de frein (tests hérités).
"""

from __future__ import annotations

from app.contexts.auth.domain.errors import TooManyLoginAttemptsError
from app.contexts.auth.domain.login_attempt import LoginAttempt
from app.contexts.auth.domain.repositories import LoginAttemptRepository


class LoginThrottle:
    def __init__(self, attempts: LoginAttemptRepository, *, clock) -> None:
        self._attempts = attempts
        self._clock = clock

    async def ensure_not_locked(self, identifier: str) -> None:
        now = self._clock()
        att = await self._attempts.get(identifier)
        if att is not None and att.is_locked(now):
            raise TooManyLoginAttemptsError(
                "Trop d'essais de connexion. Réessayez plus tard.",
                details={"retry_after_seconds": att.retry_after_seconds(now)},
            )

    async def record_failure(self, identifier: str) -> None:
        now = self._clock()
        att = await self._attempts.get(identifier) or LoginAttempt.fresh(identifier, now=now)
        att.register_failure(now=now)
        await self._attempts.save(att)

    async def clear(self, identifier: str) -> None:
        att = await self._attempts.get(identifier)
        if att is not None and (att.failed_count or att.locked_until is not None):
            att.reset(now=self._clock())
            await self._attempts.save(att)
