"""Agrégat `Visitor` — un présent **hors roster** capturé au nom (M6-3).

L'entonnoir de croissance : un visage nouveau à une rencontre. Léger (nom + téléphone
facultatif), sans compte — la conversion en membre (compte + enrôlement) viendra plus tard.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot


class Visitor(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        gathering_id: UUID,
        tenant_id: UUID,
        name: str,
        phone: str | None,
        captured_by_account_id: UUID,
        captured_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.gathering_id = gathering_id
        self.tenant_id = tenant_id
        self.name = name
        self.phone = phone  # facultatif ; s'il revient, la conversion en membre s'appuiera dessus
        self.captured_by_account_id = captured_by_account_id
        self.captured_at = captured_at
