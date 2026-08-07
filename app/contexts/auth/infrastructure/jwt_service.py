"""Émission/décodage des JWT mobiles (pyjwt).

Le jeton ne porte que l'**identité** (`sub` = account_id) et son type, jamais les
rôles : l'autorisation reste dynamique (IAM `CheckPermission`), pour qu'une
rétrogradation prenne effet sans attendre l'expiration du jeton.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.application.ports import TokenClaims, TokenService
from app.contexts.auth.domain.errors import InvalidTokenError

_ACCESS = "access"
_REFRESH = "refresh"
_SESSION = "session"


class JwtTokenService(TokenService):
    def __init__(
        self,
        *,
        secret: str,
        algorithm: str,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
        session_ttl_seconds: int,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds
        self._session_ttl = session_ttl_seconds

    def issue_pair(self, account_id: UUID, device_id: str) -> TokenPair:
        return TokenPair(
            access_token=self._encode(account_id, device_id, _ACCESS, self._access_ttl),
            refresh_token=self._encode(account_id, device_id, _REFRESH, self._refresh_ttl),
            expires_in=self._access_ttl,
        )

    def decode_access(self, token: str) -> TokenClaims:
        return self._decode(token, _ACCESS)

    def decode_refresh(self, token: str) -> TokenClaims:
        return self._decode(token, _REFRESH)

    def issue_session(self, account_id: UUID, device_id: str) -> str:
        return self._encode(account_id, device_id, _SESSION, self._session_ttl)

    def decode_session(self, token: str) -> TokenClaims:
        return self._decode(token, _SESSION)

    # --- interne ---

    def _encode(self, account_id: UUID, device_id: str, token_type: str, ttl: int) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(account_id),
            "did": device_id,  # DOREA-016 — l'appareil, pour pouvoir révoquer
            "type": token_type,
            "iat": now,
            "exp": now + timedelta(seconds=ttl),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def _decode(self, token: str, expected_type: str) -> TokenClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("Jeton invalide ou expiré.") from exc

        if payload.get("type") != expected_type:
            raise InvalidTokenError("Type de jeton inattendu.")
        # Un jeton **sans appareil** est un jeton d'avant DOREA-016 : il ne peut pas être
        # révoqué, donc il n'est plus accepté. Refuser est le seul choix sûr.
        device_id = payload.get("did")
        if not isinstance(device_id, str) or not device_id:
            raise InvalidTokenError("Jeton sans appareil — non révocable.")
        try:
            return TokenClaims(account_id=UUID(payload["sub"]), device_id=device_id)
        except (KeyError, ValueError) as exc:
            raise InvalidTokenError("Jeton malformé.") from exc
