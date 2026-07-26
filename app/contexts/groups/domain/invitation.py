"""Agrégat `GroupInvitation` — lien/code d'invitation à un groupe (M4, G-1b).

Le **moteur de croissance** : un responsable génère un lien, le partage ; un membre (ou un
nouveau) l'utilise pour **rejoindre** le groupe. Réutilisable, avec **expiration**, et
**révocable**. Le code résout à lui seul le groupe (le join n'a que le code).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot


class GroupInvitation(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        group_id: UUID,
        tenant_id: UUID,
        code: str,
        created_by_account_id: UUID,
        created_at: datetime,
        expires_at: datetime,
        revoked_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.group_id = group_id
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
