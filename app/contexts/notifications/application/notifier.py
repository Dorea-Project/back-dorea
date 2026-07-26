"""Le port **`Notifier`** — ce que les autres contextes appellent pour prévenir des personnes.

Transverse : Event, Annonces, RDV importent ce port et reçoivent un adaptateur. La notification est
**best-effort** : elle ne casse jamais l'action qui la déclenche (voir `PushNotifier`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PushNotification:
    title: str
    body: str
    data: dict | None = None  # charge utile (ex. deep-link : type + id)


class Notifier(ABC):
    @abstractmethod
    async def notify(
        self, account_ids: list[UUID], notification: PushNotification
    ) -> None: ...


class NotificationScheduler(ABC):
    """Planifie un envoi **différé** (outbox) : cible déjà résolue + quand. Dispatché plus tard,
    hors du chemin de la requête (rappels de RDV, broadcasts asynchrones)."""

    @abstractmethod
    async def schedule(
        self, account_ids: list[UUID], notification: PushNotification, *, at: datetime
    ) -> None: ...
