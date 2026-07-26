"""Use case `ArchiveAnnouncement` (M8) — sortir une annonce du fil, à la main.

L'expiration (`expires_at`) sort une annonce du fil **toute seule** ; ceci est le geste **manuel**
(erreur, mobilisation terminée, événement passé). Même autorité que publier dans cette portée.
L'archive reste **consultable** (rien n'est détruit).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.announcements.domain.errors import AnnouncementNotFoundError
from app.contexts.announcements.domain.repositories import AnnouncementRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission


class ArchiveAnnouncement:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
    ) -> None:
        self._announcements = announcements
        self._groups = groups
        self._access = access

    async def execute(self, *, actor_account_id: UUID, announcement_id: UUID) -> None:
        announcement = await self._announcements.get(announcement_id)
        if announcement is None:
            raise AnnouncementNotFoundError(
                "Annonce introuvable.", details={"announcement_id": str(announcement_id)}
            )
        if announcement.tenant_id is None:
            # Une annonce Dorea ne s'archive pas depuis une église (souveraineté inverse).
            raise UnauthorizedGroupActionError(
                "Une annonce Dorea ne peut être archivée depuis une église.",
                details={"announcement_id": str(announcement_id)},
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
        announcement.archive()
        await self._announcements.save(announcement)
