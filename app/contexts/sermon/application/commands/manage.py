"""Use cases **du pasteur** — approuver puis publier un sermon.

Même autorité que le dépôt (`PUBLISH_SERMON`, église-entière), déduite du tenant du sermon.
L'approbation est le moment où le pasteur met son **onction** (et relira le digest IA dès S-1) ;
la publication n'est possible **qu'après** approbation — rien de non relu n'atteint le membre.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission
from app.contexts.sermon.application.dtos import SermonDTO
from app.contexts.sermon.application.mapping import to_sermon_dto
from app.contexts.sermon.application.ports import CapsuleFeedPort
from app.contexts.sermon.domain.aggregates import Sermon
from app.contexts.sermon.domain.errors import SermonNotFoundError
from app.contexts.sermon.domain.repositories import SermonRepository


async def _load_for_publisher(
    sermons: SermonRepository,
    access: GroupAccessPolicy,
    *,
    actor_account_id: UUID,
    sermon_id: UUID,
) -> Sermon:
    sermon = await sermons.get(sermon_id)
    if sermon is None:
        raise SermonNotFoundError(
            "Sermon introuvable.", details={"sermon_id": str(sermon_id)}
        )
    await access.ensure_church_wide(
        actor_account_id=actor_account_id,
        tenant_id=sermon.tenant_id,
        permission=Permission.PUBLISH_SERMON,
    )
    return sermon


class ApproveSermon:
    def __init__(
        self, sermons: SermonRepository, access: GroupAccessPolicy, *, clock
    ) -> None:
        self._sermons = sermons
        self._access = access
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, sermon_id: UUID) -> SermonDTO:
        sermon = await _load_for_publisher(
            self._sermons, self._access,
            actor_account_id=actor_account_id, sermon_id=sermon_id,
        )
        sermon.approve(now=self._clock())
        await self._sermons.save(sermon)
        return to_sermon_dto(sermon)


class PublishSermon:
    def __init__(
        self,
        sermons: SermonRepository,
        access: GroupAccessPolicy,
        feed: CapsuleFeedPort | None = None,
        *,
        clock,
    ) -> None:
        self._sermons = sermons
        self._access = access
        self._feed = feed
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, sermon_id: UUID) -> SermonDTO:
        sermon = await _load_for_publisher(
            self._sermons, self._access,
            actor_account_id=actor_account_id, sermon_id=sermon_id,
        )
        sermon.publish(now=self._clock())
        await self._sermons.save(sermon)
        # Les capsules entrent dans le fil (une seule fois : publier ne peut se faire qu'à partir
        # de l'état approuvé).
        if self._feed is not None and sermon.digest is not None and sermon.digest.capsules:
            await self._feed.publish_capsules(
                tenant_id=sermon.tenant_id,
                author_account_id=sermon.author_account_id,
                capsules=sermon.digest.capsules,
            )
        return to_sermon_dto(sermon)
