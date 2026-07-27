"""Adaptateurs : ce que le moteur demande à Groupes, IAM et Mission.

Le référent est **résolu**, jamais stocké. Ces trois adaptateurs sont les seules lectures dont
la résolution a besoin — et la plus importante est `active_leader_of` : un pointeur calculé, qui
fait que remplacer un responsable change le référent de tout son groupe sans une seule écriture.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.groups.domain.membership import GroupMembershipStatus
from app.contexts.groups.infrastructure.persistence.models import (
    GroupMembershipModel,
    GroupModel,
)
from app.contexts.iam.domain.enums import AccountStatus, MembershipStatus, RoleCode
from app.contexts.iam.infrastructure.persistence.models import (
    AccountModel,
    MembershipModel,
    RoleAssignmentModel,
)
from app.contexts.mission.infrastructure.persistence.models import SeekerModel
from app.contexts.watch.application.referent_ports import (
    GroupDirectory,
    InviterDirectory,
    PeopleDirectory,
)
from app.contexts.watch.domain.referent import MembershipCandidate


class SqlGroupDirectory(GroupDirectory):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_memberships(
        self, account_id: UUID, tenant_id: UUID
    ) -> list[MembershipCandidate]:
        stmt = (
            select(GroupMembershipModel, GroupModel.type)
            .join(GroupModel, GroupModel.id == GroupMembershipModel.group_id)
            .where(
                GroupMembershipModel.account_id == account_id,
                GroupMembershipModel.tenant_id == tenant_id,
                GroupMembershipModel.status == GroupMembershipStatus.ACTIVE.value,
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            MembershipCandidate(
                group_id=m.group_id, group_type=group_type, joined_at=m.joined_at
            )
            for m, group_type in rows
        ]

    async def active_leader_of(self, group_id: UUID, tenant_id: UUID) -> UUID | None:
        """Le responsable actif d'un groupe. **Rien n'est stocké côté référent.**

        S'il y en a plusieurs, le plus anciennement assigné : c'est celui qui connaît le
        groupe depuis le plus longtemps, et ça reste déterministe au rejeu."""
        stmt = (
            select(MembershipModel.account_id)
            .join(RoleAssignmentModel, RoleAssignmentModel.membership_id == MembershipModel.id)
            .where(
                RoleAssignmentModel.tenant_id == tenant_id,
                RoleAssignmentModel.group_id == group_id,
                RoleAssignmentModel.role == RoleCode.GROUP_LEADER.value,
                RoleAssignmentModel.revoked_at.is_(None),
                MembershipModel.status != MembershipStatus.CLOSED.value,
            )
            .order_by(RoleAssignmentModel.assigned_at, MembershipModel.account_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()


    async def pastor_of_branch(self, group_id: UUID, tenant_id: UUID) -> UUID | None:
        """Remonte le chemin matérialisé jusqu'au premier ancêtre-ou-soi doté d'un pasteur.

        Le `path` porte déjà la lignée : on n'a pas besoin de remonter l'arbre en boucle. On lit
        du plus proche au plus lointain, pour que le pasteur d'annexe l'emporte sur celui de
        l'église."""
        group = await self._session.get(GroupModel, group_id)
        if group is None:
            return None

        # `path` a la forme `/{racine}/…/{self}/` — la lignée s'y lit directement.
        lineage = [UUID(part) for part in (group.path or "").split("/") if part]
        if group_id not in lineage:
            lineage.append(group_id)

        for candidate in reversed(lineage):  # du plus proche au plus lointain
            stmt = (
                select(MembershipModel.account_id)
                .join(
                    RoleAssignmentModel,
                    RoleAssignmentModel.membership_id == MembershipModel.id,
                )
                .where(
                    RoleAssignmentModel.tenant_id == tenant_id,
                    RoleAssignmentModel.group_id == candidate,
                    RoleAssignmentModel.role == RoleCode.PASTOR.value,
                    RoleAssignmentModel.revoked_at.is_(None),
                    MembershipModel.status != MembershipStatus.CLOSED.value,
                )
                .order_by(RoleAssignmentModel.assigned_at, MembershipModel.account_id)
                .limit(1)
            )
            found = (await self._session.execute(stmt)).scalars().first()
            if found is not None:
                return found
        return None


class SqlPeopleDirectory(PeopleDirectory):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_eligible(self, account_id: UUID, tenant_id: UUID) -> bool:
        """Compte actif **et** appartenance vivante. Un référent inéligible ne bloque pas :
        la cascade continue sous lui, et s'il n'y a rien dessous, c'est un trou."""
        stmt = (
            select(MembershipModel.id)
            .join(AccountModel, AccountModel.id == MembershipModel.account_id)
            .where(
                MembershipModel.account_id == account_id,
                MembershipModel.tenant_id == tenant_id,
                MembershipModel.status != MembershipStatus.CLOSED.value,
                AccountModel.status == AccountStatus.ACTIVE.value,
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def member_since(self, account_id: UUID, tenant_id: UUID) -> datetime | None:
        stmt = (
            select(MembershipModel.created_at)
            .where(
                MembershipModel.account_id == account_id,
                MembershipModel.tenant_id == tenant_id,
            )
            .order_by(MembershipModel.created_at)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def church_admin(self, tenant_id: UUID) -> UUID | None:
        return await self._holder_of(RoleCode.ADMIN, tenant_id)

    async def pastor(self, tenant_id: UUID) -> UUID | None:
        return await self._holder_of(RoleCode.PASTOR, tenant_id)

    async def _holder_of(self, role: RoleCode, tenant_id: UUID) -> UUID | None:
        stmt = (
            select(MembershipModel.account_id)
            .join(RoleAssignmentModel, RoleAssignmentModel.membership_id == MembershipModel.id)
            .where(
                RoleAssignmentModel.tenant_id == tenant_id,
                RoleAssignmentModel.role == role.value,
                RoleAssignmentModel.revoked_at.is_(None),
                MembershipModel.status != MembershipStatus.CLOSED.value,
            )
            .order_by(RoleAssignmentModel.assigned_at, MembershipModel.account_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()


class SqlInviterDirectory(InviterDirectory):
    """Qui a fait entrer cette personne — le lien qui précède toute appartenance."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def inviter_of(self, account_id: UUID, tenant_id: UUID) -> UUID | None:
        stmt = (
            select(SeekerModel.inviter_account_id)
            .where(
                SeekerModel.integrated_account_id == account_id,
                SeekerModel.tenant_id == tenant_id,
                SeekerModel.inviter_account_id.isnot(None),
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()
