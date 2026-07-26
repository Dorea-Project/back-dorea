"""Verrou anti-brute-force du login (DOREA-004) — un compteur d'échecs par **identifiant**.

Le login PIN/mot de passe est un facteur à petit espace de clés ; sans frein, on le devine.
On compte les échecs par identifiant présenté (téléphone/e-mail) et, au-delà d'un seuil, on
**verrouille** avec un **backoff qui double** à chaque palier — le succès remet à zéro. Fenêtres
courtes (pas de verrou permanent) pour ne pas offrir un déni de service contre la victime.
"""

from __future__ import annotations

from datetime import datetime, timedelta

MAX_ATTEMPTS = 5  # au 5ᵉ échec, on verrouille
_BASE_LOCK = timedelta(seconds=60)  # 1ʳᵉ fenêtre de verrou
_MAX_LOCK = timedelta(minutes=30)  # plafond du backoff


class LoginAttempt:
    def __init__(
        self,
        *,
        identifier: str,
        failed_count: int = 0,
        locked_until: datetime | None,
        updated_at: datetime,
    ) -> None:
        self.identifier = identifier
        self.failed_count = failed_count
        self.locked_until = locked_until
        self.updated_at = updated_at

    @classmethod
    def fresh(cls, identifier: str, *, now: datetime) -> LoginAttempt:
        return cls(identifier=identifier, locked_until=None, updated_at=now)

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now

    def retry_after_seconds(self, now: datetime) -> int:
        if not self.is_locked(now):
            return 0
        return int((self.locked_until - now).total_seconds()) + 1

    def register_failure(self, *, now: datetime) -> None:
        """Compte un échec ; verrouille (backoff doublant) une fois le seuil franchi."""
        self.failed_count += 1
        self.updated_at = now
        if self.failed_count >= MAX_ATTEMPTS:
            over = self.failed_count - MAX_ATTEMPTS  # 0 au premier verrou
            self.locked_until = now + min(_BASE_LOCK * (2 ** min(over, 6)), _MAX_LOCK)

    def reset(self, *, now: datetime) -> None:
        """Succès (ou fenêtre purgée) → on repart de zéro."""
        self.failed_count = 0
        self.locked_until = None
        self.updated_at = now
