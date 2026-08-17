"""Agrégat `Device` — l'appareil d'une personne, cible d'une notification push.

Une personne peut avoir plusieurs appareils. Le **jeton** (FCM / APNs) est fourni par le client
mobile ; on pousse vers lui. Ré-enregistrer le même jeton le rafraîchit (pas de doublon).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app._shared.messages import MessageKey
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
    dispatcher — hors du chemin de la requête.

    ⚠️ **Ce qui est mis en file est la clé, jamais la phrase.** Un rappel de rendez-vous se pose
    des semaines à l'avance — et surtout *avant* qu'on sache dans quelle langue il sera lu. Une
    phrase écrite ici se figerait dans la langue du jour où elle a été planifiée, et un membre
    anglophone recevrait en français un rappel posé pendant qu'il était encore rattaché à une
    église francophone. `title`/`body` ne subsistent que pour les lignes d'avant le bilingue.
    """

    def __init__(
        self,
        *,
        id: UUID,
        account_ids: list[UUID],
        key: MessageKey | None,
        params: dict,
        data: dict | None,
        scheduled_for: datetime,
        status: ScheduledStatus,
        created_at: datetime,
        sent_at: datetime | None,
        legacy_title: str | None = None,
        legacy_body: str | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.account_ids = account_ids
        self.key = key
        self.params = params
        self.data = data
        self.scheduled_for = scheduled_for
        self.status = status
        self.created_at = created_at
        self.sent_at = sent_at
        # Transitoire : le texte déjà rendu des lignes posées avant le catalogue.
        self.legacy_title = legacy_title
        self.legacy_body = legacy_body

    @classmethod
    def schedule(
        cls,
        *,
        id: UUID,
        account_ids: list[UUID],
        key: MessageKey,
        params: dict,
        data: dict | None,
        at: datetime,
        now: datetime,
    ) -> ScheduledNotification:
        """Rien de neuf n'entre en file sans clé — d'où `key` obligatoire ici, là où le
        constructeur l'accepte encore nulle (relecture d'une ligne ancienne)."""
        return cls(
            id=id,
            account_ids=account_ids,
            key=key,
            params=params,
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
