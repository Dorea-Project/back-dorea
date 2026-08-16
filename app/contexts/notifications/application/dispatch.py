"""`OutboxScheduler` (planifie) + `DispatchDueNotifications` (exécute) — le fan-out asynchrone.

Un contexte **planifie** (`schedule`) un envoi (cible résolue + quand) ; le **dispatcher**
(`run`) — appelé par un cron externe via la route Plateforme — envoie ce qui est dû et le marque.
Best-effort côté envoi (via le `Notifier`) ; le job est marqué envoyé pour ne pas repartir.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app._shared.messages import Message
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
        if notification.key is None:
            # Le champ `rendered` n'existe que pour relire les lignes d'avant le bilingue ; on
            # n'en écrit jamais de nouvelles. Sans clé, il n'y aurait rien à traduire au dispatch.
            raise ValueError("une notification planifiée porte une clé du catalogue")
        await self._jobs.add(
            ScheduledNotification.schedule(
                id=uuid4(),
                account_ids=targets,
                key=notification.key,
                params=dict(notification.params),
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
            await self._notifier.notify(_as_uuids(job.account_ids), _as_notification(job))
            job.mark_sent(now=now)
            await self._jobs.save(job)
        return len(due)


def _as_notification(job: ScheduledNotification) -> PushNotification:
    if job.key is not None:
        return PushNotification(key=job.key, params=job.params, data=job.data)
    # Ligne d'avant le bilingue : le texte est déjà rendu, il part tel quel plutôt que d'être
    # deviné depuis sa phrase. Ce chemin s'éteint tout seul quand la file s'est drainée.
    return PushNotification(
        rendered=Message(title=job.legacy_title or "", body=job.legacy_body or ""),
        data=job.data,
    )


def _as_uuids(account_ids: list) -> list[UUID]:
    return [a if isinstance(a, UUID) else UUID(str(a)) for a in account_ids]
