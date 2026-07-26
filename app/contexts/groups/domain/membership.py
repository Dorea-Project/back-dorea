"""Agrégat `GroupMembership` — « X est dans le groupe G » (M4 §6, G-1).

**Distinct** de la Membership église (IAM). Minimal par choix : `active`/`left`, sans
statut pastoral par groupe (la progression visitor→confirmed vit sur la Membership église).
Un compte peut appartenir à 0..N groupes simultanément (axes différents : une cellule
**et** l'équipe louange).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app._shared.domain.entity import AggregateRoot


class GroupMembershipStatus(StrEnum):
    ACTIVE = "active"
    LEFT = "left"


class GroupMembership(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        group_id: UUID,
        account_id: UUID,
        tenant_id: UUID,
        status: GroupMembershipStatus,
        joined_at: datetime,
        joined_by_account_id: UUID,
        left_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.group_id = group_id
        self.account_id = account_id
        self.tenant_id = tenant_id  # dénormalisé (requêtes de portée)
        self.status = status
        self.joined_at = joined_at
        self.joined_by_account_id = joined_by_account_id
        self.left_at = left_at

    @classmethod
    def join(
        cls,
        *,
        id: UUID,
        group_id: UUID,
        account_id: UUID,
        tenant_id: UUID,
        now: datetime,
        joined_by_account_id: UUID,
    ) -> GroupMembership:
        return cls(
            id=id,
            group_id=group_id,
            account_id=account_id,
            tenant_id=tenant_id,
            status=GroupMembershipStatus.ACTIVE,
            joined_at=now,
            joined_by_account_id=joined_by_account_id,
        )

    @property
    def is_active(self) -> bool:
        return self.status is GroupMembershipStatus.ACTIVE

    def leave(self, *, now: datetime) -> None:
        self.status = GroupMembershipStatus.LEFT
        self.left_at = now
