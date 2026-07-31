"""Requête `ListResponders` (M8) — l'engagement rendu visible à l'auteur.

L'auteur (ou un responsable de la portée) voit **qui** s'est engagé : ses volontaires (mobiliser),
qui vient (convoquer), qui porte (prier).

Le compte, lui, n'est public **que s'il a un dénominateur** : une mobilisation plafonnée affiche
« n / places », ce qui est de la capacité et permet au membre de décider. Partout ailleurs il reste
tu — « 32 portent » est un nombre nu, donc comparable d'une annonce à l'autre, donc un score. Sur
une annonce de décès, ce nombre a d'ailleurs déjà son destinataire légitime : la famille, par
`GetConsolation`.

Les **noms**, eux, restent réservés à l'auteur et aux responsables de la portée, quelle que soit
l'intention (choix figé).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.announcements.application.dtos import ResponderDTO, ResponderListDTO
from app.contexts.announcements.domain.errors import AnnouncementNotFoundError
from app.contexts.announcements.domain.repositories import (
    AnnouncementEngagementRepository,
    AnnouncementRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission


class ListResponders:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        engagements: AnnouncementEngagementRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
    ) -> None:
        self._announcements = announcements
        self._engagements = engagements
        self._groups = groups
        self._access = access

    async def execute(
        self, *, actor_account_id: UUID, announcement_id: UUID
    ) -> ResponderListDTO:
        announcement = await self._announcements.get(announcement_id)
        if announcement is None:
            raise AnnouncementNotFoundError(
                "Annonce introuvable.", details={"announcement_id": str(announcement_id)}
            )
        # L'auteur voit toujours ; sinon il faut l'autorité de publication sur la portée.
        if actor_account_id != announcement.author_account_id:
            await self._ensure_scope_authority(announcement, actor_account_id)

        responders = await self._engagements.list_for(announcement_id)
        return ResponderListDTO(
            announcement_id=announcement_id,
            count=len(responders),
            responders=[
                ResponderDTO(account_id=r.account_id, responded_at=r.responded_at)
                for r in responders
            ],
        )

    async def _ensure_scope_authority(self, announcement, actor_account_id: UUID) -> None:
        if announcement.tenant_id is None:
            raise UnauthorizedGroupActionError(
                "Les engagements d'une annonce Dorea ne sont pas exposés aux églises.",
                details={"announcement_id": str(announcement.id)},
            )
        if announcement.scope_group_id is None:
            await self._access.ensure_church_wide(
                actor_account_id=actor_account_id,
                tenant_id=announcement.tenant_id,
                permission=Permission.PUBLISH_ANNOUNCEMENT,
            )
        else:
            group = await load_group_in_tenant(
                self._groups, announcement.scope_group_id, announcement.tenant_id
            )
            await self._access.ensure_can(
                actor_account_id=actor_account_id,
                group=group,
                permission=Permission.PUBLISH_ANNOUNCEMENT,
            )
