"""Requêtes du module Sermon — la vue du gardien (pasteur / admin).

Voir les sermons de l'église et en ouvrir un pour le relire est un acte de gardien
(`PUBLISH_SERMON`, église-entière). Le membre, lui, verra plus tard les **capsules** publiées
dans le fil (S-2), jamais ce texte brut.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission
from app.contexts.sermon.application.dtos import SermonDTO
from app.contexts.sermon.application.mapping import to_sermon_dto
from app.contexts.sermon.domain.errors import SermonNotFoundError
from app.contexts.sermon.domain.repositories import SermonRepository


class ListTenantSermons:
    def __init__(self, sermons: SermonRepository, access: GroupAccessPolicy) -> None:
        self._sermons = sermons
        self._access = access

    async def execute(
        self, *, actor_account_id: UUID, tenant_id: UUID
    ) -> list[SermonDTO]:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.PUBLISH_SERMON,
        )
        sermons = await self._sermons.list_by_tenant(tenant_id)
        return [to_sermon_dto(s) for s in sermons]


class GetSermon:
    def __init__(self, sermons: SermonRepository, access: GroupAccessPolicy) -> None:
        self._sermons = sermons
        self._access = access

    async def execute(self, *, actor_account_id: UUID, sermon_id: UUID) -> SermonDTO:
        sermon = await self._sermons.get(sermon_id)
        if sermon is None:
            raise SermonNotFoundError(
                "Sermon introuvable.", details={"sermon_id": str(sermon_id)}
            )
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=sermon.tenant_id,
            permission=Permission.PUBLISH_SERMON,
        )
        return to_sermon_dto(sermon)
