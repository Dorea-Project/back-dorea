"""Implémentation SQLAlchemy de `MemberTransferRepository`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.iam.domain.repositories import MemberTransferRepository
from app.contexts.iam.domain.transfer import MemberTransfer, TransferStatus
from app.contexts.iam.infrastructure.persistence.models import MemberTransferModel


def _to_domain(row: MemberTransferModel) -> MemberTransfer:
    return MemberTransfer(
        id=row.id,
        account_id=row.account_id,
        from_tenant_id=row.from_tenant_id,
        to_tenant_id=row.to_tenant_id,
        to_group_id=row.to_group_id,
        requested_by_account_id=row.requested_by_account_id,
        requested_at=row.requested_at,
        status=TransferStatus(row.status),
        resolved_by_account_id=row.resolved_by_account_id,
        resolved_at=row.resolved_at,
    )


class SqlMemberTransferRepository(MemberTransferRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, transfer: MemberTransfer) -> None:
        self._session.add(
            MemberTransferModel(
                id=transfer.id,
                account_id=transfer.account_id,
                from_tenant_id=transfer.from_tenant_id,
                to_tenant_id=transfer.to_tenant_id,
                to_group_id=transfer.to_group_id,
                status=transfer.status.value,
                requested_by_account_id=transfer.requested_by_account_id,
                requested_at=transfer.requested_at,
                resolved_by_account_id=transfer.resolved_by_account_id,
                resolved_at=transfer.resolved_at,
            )
        )
        await self._session.flush()

    async def get(self, transfer_id: UUID) -> MemberTransfer | None:
        row = await self._session.get(MemberTransferModel, transfer_id)
        return _to_domain(row) if row is not None else None

    async def save(self, transfer: MemberTransfer) -> None:
        row = await self._session.get(MemberTransferModel, transfer.id)
        if row is None:
            return
        row.status = transfer.status.value
        row.resolved_by_account_id = transfer.resolved_by_account_id
        row.resolved_at = transfer.resolved_at
        await self._session.flush()

    async def get_pending(
        self, account_id: UUID, from_tenant_id: UUID, to_tenant_id: UUID
    ) -> MemberTransfer | None:
        stmt = select(MemberTransferModel).where(
            MemberTransferModel.account_id == account_id,
            MemberTransferModel.from_tenant_id == from_tenant_id,
            MemberTransferModel.to_tenant_id == to_tenant_id,
            MemberTransferModel.status == TransferStatus.PENDING.value,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_domain(row) if row is not None else None

    async def list_involving_tenant(self, tenant_id: UUID) -> list[MemberTransfer]:
        stmt = select(MemberTransferModel).where(
            (MemberTransferModel.from_tenant_id == tenant_id)
            | (MemberTransferModel.to_tenant_id == tenant_id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]
