"""Requête `ListTransfers` — les transferts d'une église (backoffice).

Sépare **entrants** (on est la source : demandes à accepter/refuser) et **sortants** (on est la
destination : demandes émises, en attente de l'autre église). Autorité `TRANSFER_MEMBER`.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.commands.transfer_member import to_transfer_dto
from app.contexts.iam.application.dtos import TransferListDTO
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MemberTransferRepository


class ListTransfers:
    def __init__(
        self, transfers: MemberTransferRepository, access: AccessControl
    ) -> None:
        self._transfers = transfers
        self._access = access

    async def execute(self, *, actor_account_id: UUID, tenant_id: UUID) -> TransferListDTO:
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.TRANSFER_MEMBER,
        )
        involving = await self._transfers.list_involving_tenant(tenant_id)
        return TransferListDTO(
            tenant_id=tenant_id,
            incoming=[to_transfer_dto(t) for t in involving if t.from_tenant_id == tenant_id],
            outgoing=[to_transfer_dto(t) for t in involving if t.to_tenant_id == tenant_id],
        )
