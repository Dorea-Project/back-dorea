"""Agrégat `MemberTransfer` — le transfert de membre entre églises (acte gouverné).

Une **poignée de main** entre deux tenants souverains : l'église de **destination** demande à
recevoir un membre (autorité sur *sa* maison), l'église **source** accepte et le libère (autorité
sur *sa* maison). Le **Compte ne bouge jamais** (identité globale) — seules les appartenances
changent : la source clôture la sienne (`changed_church`, cascade des rôles), la destination en
ouvre / confirme une. On ne mute donc jamais les données d'une autre église sans son consentement.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.iam.domain.errors import TransferAlreadyResolvedError


class TransferStatus(StrEnum):
    PENDING = "pending"  # demandé par la destination, en attente de la source
    ACCEPTED = "accepted"  # la source a libéré → exécuté
    DECLINED = "declined"  # la source a refusé
    CANCELLED = "cancelled"  # la destination a retiré sa demande


class MemberTransfer(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        account_id: UUID,
        from_tenant_id: UUID,
        to_tenant_id: UUID,
        to_group_id: UUID | None,
        requested_by_account_id: UUID,
        requested_at: datetime,
        status: TransferStatus = TransferStatus.PENDING,
        resolved_by_account_id: UUID | None = None,
        resolved_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.account_id = account_id
        self.from_tenant_id = from_tenant_id
        self.to_tenant_id = to_tenant_id
        self.to_group_id = to_group_id
        self.requested_by_account_id = requested_by_account_id
        self.requested_at = requested_at
        self.status = status
        self.resolved_by_account_id = resolved_by_account_id
        self.resolved_at = resolved_at

    @property
    def is_pending(self) -> bool:
        return self.status is TransferStatus.PENDING

    def accept(self, *, by_account_id: UUID, now: datetime) -> None:
        """La source libère le membre (déclenche la saga côté use case)."""
        self._resolve(TransferStatus.ACCEPTED, by_account_id, now)

    def decline(self, *, by_account_id: UUID, now: datetime) -> None:
        """La source refuse la demande."""
        self._resolve(TransferStatus.DECLINED, by_account_id, now)

    def cancel(self, *, by_account_id: UUID, now: datetime) -> None:
        """La destination retire sa propre demande."""
        self._resolve(TransferStatus.CANCELLED, by_account_id, now)

    def _resolve(self, status: TransferStatus, by_account_id: UUID, now: datetime) -> None:
        if not self.is_pending:
            raise TransferAlreadyResolvedError(
                "Ce transfert est déjà résolu.",
                details={"transfer_id": str(self.id), "status": self.status.value},
            )
        self.status = status
        self.resolved_by_account_id = by_account_id
        self.resolved_at = now
