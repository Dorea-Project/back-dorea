"""Use cases **publics** de la carte (M9-0) — la voix du chercheur, sans compte.

- `ReactToCard` — réaction légère **anonyme** (touché / édifié / Amen) : un signal, aucun contact.
- `AcceptInvitation` — l'engagement : le chercheur laisse un **contact** → devient un `Seeker`
  attribué à l'inviteur (personne ou groupe). Franchi par choix, jamais par pression.

Le **code EST l'entrée** : pas d'authentification (le chercheur n'est pas encore membre).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.mission.domain.aggregates import MissionLink, MissionReaction, Seeker
from app.contexts.mission.domain.enums import SeekerReaction, SeekerStatus
from app.contexts.mission.domain.errors import (
    MissionLinkInactiveError,
    MissionLinkNotFoundError,
    SeekerContactRequiredError,
)
from app.contexts.mission.domain.repositories import (
    MissionLinkRepository,
    MissionReactionRepository,
    SeekerRepository,
)
from app.contexts.notifications.application.notifier import Notifier, PushNotification


async def _load_active(links: MissionLinkRepository, code: str, now) -> MissionLink:
    link = await links.get_by_code(code)
    if link is None:
        raise MissionLinkNotFoundError("Code d'invitation inconnu.")
    if not link.is_active(now):
        raise MissionLinkInactiveError("Cette invitation a expiré ou a été clôturée.")
    return link


class ReactToCard:
    def __init__(
        self,
        links: MissionLinkRepository,
        reactions: MissionReactionRepository,
        *,
        clock,
    ) -> None:
        self._links = links
        self._reactions = reactions
        self._clock = clock

    async def execute(self, *, code: str, kind: SeekerReaction) -> None:
        now = self._clock()
        link = await _load_active(self._links, code, now)
        await self._reactions.add(
            MissionReaction(id=uuid4(), link_id=link.id, kind=kind, reacted_at=now)
        )


class AcceptInvitation:
    def __init__(
        self,
        links: MissionLinkRepository,
        seekers: SeekerRepository,
        notifier: Notifier | None = None,
        *,
        clock,
    ) -> None:
        self._links = links
        self._seekers = seekers
        self._notifier = notifier
        self._clock = clock

    async def execute(
        self, *, code: str, name: str, phone: str | None = None
    ) -> UUID:
        now = self._clock()
        link = await _load_active(self._links, code, now)
        if not name.strip():
            raise SeekerContactRequiredError("Un nom est requis pour être accompagné.")

        seeker = Seeker(
            id=uuid4(),
            tenant_id=link.tenant_id,
            link_id=link.id,
            inviter_account_id=link.inviter_account_id,  # l'attribution suit le lien
            inviter_group_id=link.inviter_group_id,
            name=name.strip(),
            phone=phone,
            status=SeekerStatus.ACCEPTED,
            created_at=now,
        )
        await self._seekers.add(seeker)
        # La joie de la main tendue : prévenir l'inviteur (lien personnel) — best-effort.
        if self._notifier is not None and link.inviter_account_id is not None:
            await self._notifier.notify(
                [link.inviter_account_id],
                PushNotification(
                    title="Une invitation acceptée",
                    body=f"{seeker.name} a répondu à ton invitation.",
                    data={"type": "seeker", "id": str(seeker.id)},
                ),
            )
        return seeker.id
