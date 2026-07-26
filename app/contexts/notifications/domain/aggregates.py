"""Agrégat `Device` — l'appareil d'une personne, cible d'une notification push.

Une personne peut avoir plusieurs appareils. Le **jeton** (FCM / APNs) est fourni par le client
mobile ; on pousse vers lui. Ré-enregistrer le même jeton le rafraîchit (pas de doublon).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.notifications.domain.enums import DevicePlatform, ScheduledStatus
from app.contexts.notifications.domain.errors import DeviceTokenRequiredError


class Device(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        account_id: UUID,
        token: str,
        platform: DevicePlatform,
        created_at: datetime,
        last_seen_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.account_id = account_id
        self.token = token
        self.platform = platform
        self.created_at = created_at
        self.last_seen_at = last_seen_at

    @classmethod
    def register(
        cls,
        *,
        id: UUID,
        account_id: UUID,
        token: str,
        platform: DevicePlatform,
        now: datetime,
    ) -> Device:
        token = token.strip()
        if not token:
            raise DeviceTokenRequiredError("Le jeton de l'appareil est requis.")
        return cls(
            id=id,
            account_id=account_id,
            token=token,
            platform=platform,
            created_at=now,
            last_seen_at=now,
        )

    def touch(self, *, account_id: UUID, platform: DevicePlatform, now: datetime) -> None:
        """Rafraîchit un appareil déjà connu (même jeton) : propriétaire, plateforme, vu-le."""
        self.account_id = account_id
        self.platform = platform
        self.last_seen_at = now


class ScheduledNotification(AggregateRoot):
    """Une notification **planifiée** (outbox) : cible déjà résolue + quand l'envoyer.

    Enqueue par un contexte (rappel de RDV, broadcast différé), dispatch plus tard par le
    dispatcher — hors du chemin de la requête."""

    def __init__(
        self,
        *,
        id: UUID,
        account_ids: list[UUID],
        title: str,
        body: str,
        data: dict | None,
        scheduled_for: datetime,
        status: ScheduledStatus,
        created_at: datetime,
        sent_at: datetime | None,
    ) -> None:
        super().__init__()
        self.id = id
        self.account_ids = account_ids
        self.title = title
        self.body = body
        self.data = data
        self.scheduled_for = scheduled_for
        self.status = status
        self.created_at = created_at
        self.sent_at = sent_at

    @classmethod
    def schedule(
        cls,
        *,
        id: UUID,
        account_ids: list[UUID],
        title: str,
        body: str,
        data: dict | None,
        at: datetime,
        now: datetime,
    ) -> ScheduledNotification:
        return cls(
            id=id,
            account_ids=account_ids,
            title=title,
            body=body,
            data=data,
            scheduled_for=at,
            status=ScheduledStatus.PENDING,
            created_at=now,
            sent_at=None,
        )

    @property
    def is_pending(self) -> bool:
        return self.status is ScheduledStatus.PENDING

    def mark_sent(self, *, now: datetime) -> None:
        self.status = ScheduledStatus.SENT
        self.sent_at = now
