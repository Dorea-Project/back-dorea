"""Use case : rafraîchissement de session (refresh token → nouvelle paire).

Rotation systématique : chaque refresh émet un nouveau couple access/refresh.
"""

from __future__ import annotations

from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.application.ports import TokenService


class RefreshToken:
    def __init__(self, tokens: TokenService) -> None:
        self._tokens = tokens

    async def execute(self, *, refresh_token: str) -> TokenPair:
        account_id = self._tokens.decode_refresh(refresh_token)  # lève si invalide/expiré
        return self._tokens.issue_pair(account_id)
