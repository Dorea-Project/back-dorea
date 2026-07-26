"""Adaptateur `ChurchRoleStore` — écrit un rôle IAM scopé (table `role_assignments`).

Vit côté Groupes (dépendance groups → iam autorisée) : le contexte Groupes pose le
leadership de groupe, matérialisé comme attribution de rôle IAM lue par l'autorisation.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.groups.application.ports import ChurchRoleStore
from app.contexts.iam.domain.enums import RevocationReason
from app.contexts.iam.infrastructure.persistence.models import RoleAssignmentModel


class SqlChurchRoleStore(ChurchRoleStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_group_role(
        self,
        *,
        membership_id: UUID,
        tenant_id: UUID,
        role: str,
        group_id: UUID,
        assigned_by_account_id: UUID,
        now: datetime,
    ) -> UUID:
        assignment_id = uuid4()
        self._session.add(
            RoleAssignmentModel(
                id=assignment_id,
                membership_id=membership_id,
                tenant_id=tenant_id,
                role=role,
                group_id=group_id,
                assigned_at=now,
                assigned_by_account_id=assigned_by_account_id,
            )
        )
        await self._session.flush()
        return assignment_id

    async def revoke_group_role(
        self, *, membership_id: UUID, role: str, group_id: UUID, now: datetime
    ) -> int:
        result = await self._session.execute(
            update(RoleAssignmentModel)
            .where(
                RoleAssignmentModel.membership_id == membership_id,
                RoleAssignmentModel.role == role,
                RoleAssignmentModel.group_id == group_id,
                RoleAssignmentModel.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoked_reason=RevocationReason.ADMIN_ACTION.value)
        )
        return result.rowcount

    async def revoke_all_group_roles(self, *, group_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(RoleAssignmentModel)
            .where(
                RoleAssignmentModel.group_id == group_id,
                RoleAssignmentModel.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoked_reason=RevocationReason.DEMOTION_CASCADE.value)
        )
