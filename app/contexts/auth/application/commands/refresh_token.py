"""Use case : rafraîchissement de session (refresh token → nouvelle paire).

Rotation systématique : chaque refresh émet un nouveau couple access/refresh.

**DOREA-016** — c'est ici que la révocation compte le plus. L'access token est court
(1 h) et finit par mourir seul ; le refresh vit **trente jours**. Sans cette
vérification, un appareil déconnecté (ou volé) continuait à se re-délivrer des jetons
neufs pendant un mois : la déconnexion n'était qu'une politesse côté client.
"""

from __future__ import annotations

from app.contexts.auth.application.dtos import TokenPair
from app.contexts.auth.application.ports import TokenService
from app.contexts.auth.domain.errors import InvalidTokenError
from app.contexts.auth.domain.repositories import DeviceRepository


class RefreshToken:
    def __init__(self, tokens: TokenService, devices: DeviceRepository) -> None:
        self._tokens = tokens
        self._devices = devices

    async def execute(self, *, refresh_token: str) -> TokenPair:
        claims = self._tokens.decode_refresh(refresh_token)  # lève si invalide/expiré
        if not await self._devices.is_trusted(claims.account_id, claims.device_id):
            raise InvalidTokenError("Appareil révoqué — reconnectez-vous.")
        return self._tokens.issue_pair(claims.account_id, claims.device_id)
