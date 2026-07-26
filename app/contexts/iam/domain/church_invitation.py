"""Agrégat `ChurchInvitation` — lien/code pour **rejoindre une église** (M-5).

Le pendant *église-niveau* de l'invitation de groupe (G-1b) : l'accueil / l'Admin génère un lien,
le partage ; un compte l'utilise pour entrer dans l'église en `invited` — **sans forcer une
cellule** (≠ le lien de groupe, qui atterrit dans un groupe précis). Réutilisable, avec
**expiration**, et **révocable**. Le code résout à lui seul l'église.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot


class ChurchInvitation(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        code: str,
        created_by_account_id: UUID,
        created_at: datetime,
        expires_at: datetime,
        revoked_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.code = code
        self.created_by_account_id = created_by_account_id
        self.created_at = created_at
        self.expires_at = expires_at
        self.revoked_at = revoked_at

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at

    def revoke(self, *, now: datetime) -> None:
        if self.revoked_at is None:
            self.revoked_at = now
