"""Agrégat `Ownership` — la **propriété** d'un tenant (le siège Owner), M0.

La gouvernance est modélisée comme une **relation de premier rang** entre un
`Account` (qui gouverne) et un `Tenant` (quoi), distincte des rôles fonctionnels.
« L'Owner, c'est les clés ; l'Admin, c'est les mains. » Posséder n'est pas un rôle.

Un tenant a **exactement une** Ownership `active` à un instant donné, et un
historique (les propriétés `ended`). L'Owner peut gouverner **sans** être membre
(ex. un responsable de dénomination).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.tenant.domain.enums import OwnershipMode, OwnershipStatus


class Ownership(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        account_id: UUID,
        tenant_id: UUID,
        mode: OwnershipMode,
        started_at: datetime,
        status: OwnershipStatus = OwnershipStatus.ACTIVE,
        ended_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.account_id = account_id
        self.tenant_id = tenant_id
        self.mode = mode
        self.started_at = started_at
        self.status = status
        self.ended_at = ended_at

    @property
    def is_active(self) -> bool:
        return self.status is OwnershipStatus.ACTIVE
