"""Agrégats du contexte Mission (M9) : `MissionLink`, `Seeker`, `MissionReaction`.

Le **lien d'invitation** porte une **carte** (image, texte, lieu, géoloc) et appartient à une
**personne** ou à un **groupe** (évangélisation collective). Le chercheur qui la reçoit peut
**réagir** (touché / édifié / Amen — léger, anonyme) ou **accepter** (laisser un contact → devient
un `Seeker` attribué à l'inviteur). Franchie par choix, jamais par pression.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.mission.domain.enums import (
    InviterKind,
    SeekerReaction,
    SeekerStatus,
)
from app.contexts.mission.domain.errors import (
    InvalidMissionLinkError,
)


class MissionLink(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        inviter_account_id: UUID | None,
        inviter_group_id: UUID | None,
        message: str,
        media_urls: list[str] | None,
        place_label: str | None,
        latitude: float | None,
        longitude: float | None,
        code: str,
        created_at: datetime,
        expires_at: datetime,
        revoked_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.inviter_account_id = inviter_account_id
        self.inviter_group_id = inviter_group_id
        self.message = message
        self.media_urls = media_urls or []
        self.place_label = place_label
        self.latitude = latitude
        self.longitude = longitude
        self.code = code
        self.created_at = created_at
        self.expires_at = expires_at
        self.revoked_at = revoked_at

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        inviter_account_id: UUID | None,
        inviter_group_id: UUID | None,
        message: str,
        code: str,
        now: datetime,
        expires_at: datetime,
        media_urls: list[str] | None = None,
        place_label: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> MissionLink:
        # Exactement un propriétaire : personne **ou** groupe.
        if (inviter_account_id is None) == (inviter_group_id is None):
            raise InvalidMissionLinkError(
                "Un lien appartient à une personne OU à un groupe (exactement un)."
            )
        # Une carte est du contenu libre : un **message** écrit (texte propre ou verset généré),
        # une **image** (photo uploadée ou carte-verset designée), ou les deux — au moins l'un.
        message = message.strip()
        if not message and not media_urls:
            raise InvalidMissionLinkError(
                "Une carte a besoin d'au moins un message ou une image."
            )
        # Géoloc : les deux coordonnées ou aucune.
        if (latitude is None) != (longitude is None):
            raise InvalidMissionLinkError("La géolocalisation exige latitude ET longitude.")
        return cls(
            id=id,
            tenant_id=tenant_id,
            inviter_account_id=inviter_account_id,
            inviter_group_id=inviter_group_id,
            message=message,
            media_urls=media_urls,
            place_label=place_label,
            latitude=latitude,
            longitude=longitude,
            code=code,
            created_at=now,
            expires_at=expires_at,
        )

    @property
    def inviter_kind(self) -> InviterKind:
        return InviterKind.PERSON if self.inviter_account_id is not None else InviterKind.GROUP

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at

    def revoke(self, *, now: datetime) -> None:
        if self.revoked_at is None:
            self.revoked_at = now


class Seeker(AggregateRoot):
    """Le chercheur — la personne **pré-compte** atteinte, attribuée à qui l'a invitée.

    Le frère digital du Visiteur (M6-3) : celui-ci est une présence *physique*, le Seeker un
    engagement *digital*. Les deux sont la bouche du tunnel d'intégration."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        link_id: UUID,
        inviter_account_id: UUID | None,
        inviter_group_id: UUID | None,
        name: str,
        phone: str | None,
        status: SeekerStatus,
        created_at: datetime,
        accompanied_by_account_id: UUID | None = None,
        accompanied_at: datetime | None = None,
        closed_at: datetime | None = None,
        person_account_id: UUID | None = None,
        integrated_account_id: UUID | None = None,
        integrated_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.link_id = link_id
        self.inviter_account_id = inviter_account_id
        self.inviter_group_id = inviter_group_id
        self.name = name
        self.phone = phone
        self.status = status
        self.created_at = created_at
        self.accompanied_by_account_id = accompanied_by_account_id
        self.accompanied_at = accompanied_at
        self.closed_at = closed_at
        # La personne existe **dès l'acceptation** : un contact laissé, c'est quelqu'un.
        self.person_account_id = person_account_id
        self.integrated_account_id = integrated_account_id
        self.integrated_at = integrated_at

    # **Aucun mutateur de statut.** `accompany`, `close` et `integrate` vivaient ici et
    # écrivaient `SeekerStatus` — une seconde machine à états suivant la même personne que le
    # `Signal` de veille. Les deux auraient divergé, et personne n'aurait su laquelle croire.
    #
    # Leur absence n'est pas un oubli : c'est ce qui rend la double écriture **impossible**
    # plutôt que déconseillée. Le geste existe toujours, aux mêmes URL ; il s'écrit désormais
    # sur le cas. Ce que cet agrégat garde est ce qu'il est seul à savoir — la **provenance** :
    # quel lien, quel inviteur, quand accepté, et quel compte il est devenu.


class MissionReaction(AggregateRoot):
    """Réaction légère **anonyme** à la carte (touché/édifié/Amen) — un signal, pas un score."""

    def __init__(
        self,
        *,
        id: UUID,
        link_id: UUID,
        kind: SeekerReaction,
        reacted_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.link_id = link_id
        self.kind = kind
        self.reacted_at = reacted_at
