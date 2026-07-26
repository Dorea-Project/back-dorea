"""Use cases de **génération de liens d'invitation** (M9-0) — personne ou groupe.

- `CreateMyLink` — un membre génère **son** lien personnel (idempotent : un par membre et église) ;
  attribution individuelle. Il faut être membre actif de l'église.
- `CreateGroupLink` — un responsable génère le lien **de son groupe** (campagne collective) ;
  autorité `ensure_can_manage` (l'arbre M4). Attribution au groupe.
- `RevokeLink` — coupe un lien (le propriétaire : l'inviteur lui-même ou un responsable du groupe).
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.mission.application.dtos import MissionLinkDTO
from app.contexts.mission.application.ports import InvitationCodeGenerator
from app.contexts.mission.domain.aggregates import MissionLink
from app.contexts.mission.domain.errors import (
    MissionLinkNotFoundError,
    NotAChurchMemberError,
)
from app.contexts.mission.domain.repositories import MissionLinkRepository

LINK_TTL_DAYS = 90  # une campagne missionnaire vit longtemps


def to_link_dto(link: MissionLink) -> MissionLinkDTO:
    return MissionLinkDTO(
        id=link.id,
        code=link.code,
        inviter_kind=link.inviter_kind.value,
        message=link.message,
        media_urls=list(link.media_urls),
        place_label=link.place_label,
        latitude=link.latitude,
        longitude=link.longitude,
        expires_at=link.expires_at,
        revoked=link.revoked_at is not None,
    )


class CreateMyLink:
    def __init__(
        self,
        links: MissionLinkRepository,
        memberships: MembershipRepository,
        codes: InvitationCodeGenerator,
        *,
        clock,
    ) -> None:
        self._links = links
        self._memberships = memberships
        self._codes = codes
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        message: str = "",
        media_urls: list[str] | None = None,
        place_label: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> MissionLinkDTO:
        if await self._memberships.get_active(actor_account_id, tenant_id) is None:
            raise NotAChurchMemberError(
                "Rejoignez d'abord cette église pour évangéliser en son nom.",
                details={"tenant_id": str(tenant_id)},
            )
        now = self._clock()
        existing = await self._links.get_active_personal(actor_account_id, tenant_id)
        if existing is not None and existing.is_active(now):
            return to_link_dto(existing)  # idempotent : un lien personnel par membre

        link = MissionLink.create(
            id=uuid4(),
            tenant_id=tenant_id,
            inviter_account_id=actor_account_id,
            inviter_group_id=None,
            message=message,
            code=self._codes.generate(),
            now=now,
            expires_at=now + timedelta(days=LINK_TTL_DAYS),
            media_urls=media_urls,
            place_label=place_label,
            latitude=latitude,
            longitude=longitude,
        )
        await self._links.add(link)
        return to_link_dto(link)


class CreateGroupLink:
    def __init__(
        self,
        links: MissionLinkRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        codes: InvitationCodeGenerator,
        *,
        clock,
    ) -> None:
        self._links = links
        self._groups = groups
        self._access = access
        self._codes = codes
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        message: str = "",
        media_urls: list[str] | None = None,
        place_label: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> MissionLinkDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can_manage(actor_account_id=actor_account_id, group=group)

        now = self._clock()
        existing = await self._links.get_active_group(group_id)
        if existing is not None and existing.is_active(now):
            return to_link_dto(existing)

        link = MissionLink.create(
            id=uuid4(),
            tenant_id=tenant_id,
            inviter_account_id=None,
            inviter_group_id=group_id,
            message=message,
            code=self._codes.generate(),
            now=now,
            expires_at=now + timedelta(days=LINK_TTL_DAYS),
            media_urls=media_urls,
            place_label=place_label,
            latitude=latitude,
            longitude=longitude,
        )
        await self._links.add(link)
        return to_link_dto(link)


class RevokeLink:
    def __init__(
        self,
        links: MissionLinkRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._links = links
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, link_id: UUID
    ) -> MissionLinkDTO:
        link = await self._links.get(link_id)
        if link is None:
            raise MissionLinkNotFoundError(
                "Lien introuvable.", details={"link_id": str(link_id)}
            )
        # Le propriétaire coupe : l'inviteur lui-même, ou un responsable du groupe.
        if link.inviter_account_id is not None:
            if link.inviter_account_id != actor_account_id:
                raise UnauthorizedGroupActionError(
                    "Seul l'auteur du lien peut le couper.",
                    details={"link_id": str(link_id)},
                )
        else:
            group = await load_group_in_tenant(
                self._groups, link.inviter_group_id, link.tenant_id
            )
            await self._access.ensure_can(
                actor_account_id=actor_account_id,
                group=group,
                permission=Permission.MANAGE_GROUP,
            )
        link.revoke(now=self._clock())
        await self._links.save(link)
        return to_link_dto(link)
