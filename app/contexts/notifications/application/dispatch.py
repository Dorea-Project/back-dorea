"""`OutboxScheduler` (planifie) + `DispatchDueNotifications` (exécute) — le fan-out asynchrone.

Un contexte **planifie** (`schedule`) un envoi (cible résolue + quand) ; le **dispatcher**
(`run`) — appelé par un cron externe via la route Plateforme — envoie ce qui est dû et le marque.
Best-effort côté envoi (via le `Notifier`) ; le job est marqué envoyé pour ne pas repartir.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.notifications.application.notifier import (
    NotificationScheduler,
    Notifier,
    PushNotification,
)
from app.contexts.notifications.domain.aggregates import ScheduledNotification
from app.contexts.notifications.domain.repositories import ScheduledNotificationRepository


class OutboxScheduler(NotificationScheduler):
    def __init__(self, jobs: ScheduledNotificationRepository, *, clock) -> None:
        self._jobs = jobs
        self._clock = clock

    async def schedule(self, account_ids, notification: PushNotification, *, at) -> None:
        targets = list(account_ids)
        if not targets:
            return  # rien à planifier
        await self._jobs.add(
            ScheduledNotification.schedule(
                id=uuid4(),
                account_ids=targets,
                title=notification.title,
                body=notification.body,
                data=notification.data,
                at=at,
                now=self._clock(),
            )
        )


class DispatchDueNotifications:
    def __init__(
        self, jobs: ScheduledNotificationRepository, notifier: Notifier, *, clock
    ) -> None:
        self._jobs = jobs
        self._notifier = notifier
        self._clock = clock

    async def run(self, *, limit: int = 100) -> int:
        now = self._clock()
        due = await self._jobs.list_due(now, limit=limit)
        for job in due:
            await self._notifier.notify(
                _as_uuids(job.account_ids),
                PushNotification(title=job.title, body=job.body, data=job.data),
            )
            job.mark_sent(now=now)
            await self._jobs.save(job)
        return len(due)


def _as_uuids(account_ids: list) -> list[UUID]:
    return [a if isinstance(a, UUID) else UUID(str(a)) for a in account_ids]
