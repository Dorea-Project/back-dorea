"""Use cases **Accompagner** (M9-3) — le relais humain : un membre prend en charge un chercheur.

*L'humain garde la place essentielle.* Un chercheur a accepté (`accepted`) ; un membre **prend le
relais** (`accompanied`, on grave qui et quand), ou le parcours **se clôt sans jugement**
(`closed`). L'autorité est calquée sur `RevokeLink` : chercheur **personnel** → son inviteur ;
chercheur **de groupe** → un responsable du groupe qui l'a amené.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission
from app.contexts.mission.application.dtos import SeekerDTO
from app.contexts.mission.domain.aggregates import Seeker
from app.contexts.mission.domain.errors import SeekerNotFoundError
from app.contexts.mission.domain.repositories import SeekerRepository


def to_seeker_dto(seeker: Seeker) -> SeekerDTO:
    return SeekerDTO(
        id=seeker.id,
        name=seeker.name,
        status=seeker.status.value,
        created_at=seeker.created_at,
        accompanied_by=seeker.accompanied_by_account_id,
        accompanied_at=seeker.accompanied_at,
    )


async def _load_owned_seeker(
    seekers: SeekerRepository,
    groups: GroupRepository,
    access: GroupAccessPolicy,
    *,
    actor_account_id: UUID,
    seeker_id: UUID,
) -> Seeker:
    """Charge le chercheur et vérifie que l'acteur en est le **propriétaire** du suivi."""
    seeker = await seekers.get(seeker_id)
    if seeker is None:
        raise SeekerNotFoundError("Chercheur introuvable.", details={"seeker_id": str(seeker_id)})
    # Personnel → l'inviteur lui-même ; groupe → un responsable du groupe (comme RevokeLink).
    if seeker.inviter_account_id is not None:
        if seeker.inviter_account_id != actor_account_id:
            raise UnauthorizedGroupActionError(
                "Seul l'inviteur peut accompagner ce chercheur.",
                details={"seeker_id": str(seeker_id)},
            )
    else:
        group = await load_group_in_tenant(groups, seeker.inviter_group_id, seeker.tenant_id)
        await access.ensure_can(
            actor_account_id=actor_account_id, group=group, permission=Permission.MANAGE_GROUP
        )
    return seeker


class AccompanySeeker:
    def __init__(
        self,
        seekers: SeekerRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._seekers = seekers
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, seeker_id: UUID) -> SeekerDTO:
        seeker = await _load_owned_seeker(
            self._seekers, self._groups, self._access,
            actor_account_id=actor_account_id, seeker_id=seeker_id,
        )
        seeker.accompany(by_account_id=actor_account_id, now=self._clock())
        await self._seekers.save(seeker)
        return to_seeker_dto(seeker)


class CloseSeeker:
    def __init__(
        self,
        seekers: SeekerRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._seekers = seekers
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, seeker_id: UUID) -> SeekerDTO:
        seeker = await _load_owned_seeker(
            self._seekers, self._groups, self._access,
            actor_account_id=actor_account_id, seeker_id=seeker_id,
        )
        seeker.close(now=self._clock())
        await self._seekers.save(seeker)
        return to_seeker_dto(seeker)
