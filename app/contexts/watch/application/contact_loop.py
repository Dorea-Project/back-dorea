"""La **boucle boomerang** — trois parades, indissociables.

Dorea n'héberge pas le contact. On sort vers WhatsApp ou le téléphone, et **on ne revient pas**.
Le signal reste ouvert, le taux d'ignorés explose — non parce que personne n'a appelé, mais
parce que personne n'est revenu le dire. Le système conclut alors que la veille ne fonctionne
pas, alors que le contact humain a bien eu lieu.

C'est le pire des faux négatifs : celui qui invalide un succès réel, et qui fait abandonner un
outil qui marchait.

| | Parade | Où |
|---|---|---|
| **P1** | l'intention s'écrit **au départ**, avant que l'app perde la main | `StartContact` |
| **P2** | rappel de retour, réponse **sans ouvrir l'app** | `ScheduleReturnPrompt` |
| **P3** | reprise au premier plan, **une seule** invite par session | `PendingAttempts` |

Les trois ensemble, ou aucune : P1 seule laisse des tentatives éternellement en attente, P2 seule
n'a rien à rappeler, P3 seule arrive trop tard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.contexts.notifications.application.notifier import (
    NotificationScheduler,
    PushNotification,
)
from app.contexts.watch.application.ports import ContactAttemptStore, SignalStore
from app.contexts.watch.domain.contact import (
    HARD_EXPIRY_ATTEMPTS,
    ContactAttempt,
    ContactChannel,
    ContactResult,
)
from app.contexts.watch.domain.effects import CasePriority, ExtinguishCause

# Trop court, ça agace ; trop long, on a perdu le contexte de l'appel.
RETURN_PROMPT_DELAY = timedelta(hours=3)
# Au-delà, l'invite au premier plan n'a plus de sens : la conversation est loin.
FOREGROUND_WINDOW = timedelta(minutes=60)


@dataclass(frozen=True)
class StartedContact:
    attempt_id: UUID
    prompt_at: datetime


class StartContact:
    """P1 — **écrire l'effort avant de perdre la main.**

    Appelée au tap sur « appeler » ou « WhatsApp », *avant* d'ouvrir l'application externe. Si le
    responsable ne revient jamais, on saura au moins qu'il a essayé — et `first_contact_at`, la
    métrique reine du pilote, sera juste."""

    def __init__(
        self,
        attempts: ContactAttemptStore,
        signals: SignalStore,
        scheduler: NotificationScheduler | None = None,
        *,
        clock,
        id_factory=uuid4,
    ) -> None:
        self._attempts = attempts
        self._signals = signals
        self._scheduler = scheduler
        self._clock = clock
        self._new_id = id_factory

    async def execute(
        self,
        *,
        signal_id: UUID,
        tenant_id: UUID,
        by_account_id: UUID,
        channel: ContactChannel,
        person_label: str,
    ) -> StartedContact:
        now = self._clock()
        attempt = ContactAttempt(
            id=self._new_id(),
            tenant_id=tenant_id,
            signal_id=signal_id,
            by_account_id=by_account_id,
            channel=channel,
            attempted_at=now,
            result=ContactResult.PENDING,  # l'état normal au départ, pas une anomalie
        )
        await self._attempts.add(attempt)
        await self._signals.mark_contact_started(
            signal_id=signal_id, tenant_id=tenant_id, at=now
        )

        prompt_at = now + RETURN_PROMPT_DELAY
        await self._schedule_return(attempt, by_account_id, person_label, prompt_at)
        return StartedContact(attempt_id=attempt.id, prompt_at=prompt_at)

    async def _schedule_return(
        self, attempt: ContactAttempt, owner: UUID, label: str, at: datetime
    ) -> None:
        """P2 — la **seule** notification du produit autorisée à insister.

        Les réponses sont dans la notification : on répond sans ouvrir l'application. Exiger un
        détour par l'app, c'est perdre les trois quarts des retours."""
        if self._scheduler is None:
            return
        await self._scheduler.schedule(
            [owner],
            PushNotification(
                title="Un retour ?",
                body=f"As-tu pu joindre {label} ?",
                data={
                    "type": "contact_return",
                    "attempt_id": str(attempt.id),
                    "actions": "reached,not_reached,postponed",
                },
            ),
            at=at,
        )


class AnswerContact:
    """P2/P3 — le responsable dit ce qui s'est passé. **Une fois.**

    Une tentative déjà résolue ne se réécrit pas : on n'insiste pas, et on ne laisse pas une
    correction tardive brouiller la métrique."""

    def __init__(
        self,
        attempts: ContactAttemptStore,
        signals: SignalStore,
        *,
        clock,
    ) -> None:
        self._attempts = attempts
        self._signals = signals
        self._clock = clock

    async def execute(
        self, *, attempt_id: UUID, result: ContactResult
    ) -> ContactAttempt | None:
        attempt = await self._attempts.get(attempt_id)
        if attempt is None or not attempt.awaits_answer:
            return attempt

        now = self._clock()
        attempt.resolve(result=result, at=now)
        await self._attempts.save(attempt)

        if result is ContactResult.NOT_REACHED:
            await self._maybe_expire(attempt, now)
        return attempt

    async def _maybe_expire(self, attempt: ContactAttempt, now: datetime) -> None:
        """La **péremption dure** — seconde et dernière clôture système.

        Trois tentatives sans réponse sur un régime d'échéance : le cas sort de la file. Ce
        n'est pas un renoncement, c'est une question de volume — sans elle, un module
        d'évangélisation qui fonctionne noie son propre inviteur en trois semaines. La personne
        reste en base ; elle sort de la file, pas du fichier."""
        origin = await self._signals.origin_of(attempt.signal_id, attempt.tenant_id)
        if origin is not CasePriority.DEADLINE:
            return
        failed = await self._attempts.count_not_reached(attempt.signal_id)
        if failed < HARD_EXPIRY_ATTEMPTS:
            return
        await self._signals.extinguish_by_id(
            signal_id=attempt.signal_id,
            tenant_id=attempt.tenant_id,
            cause=ExtinguishCause.UNREACHABLE.value,
            at=now,
        )


class PendingAttempts:
    """P3 — ce qu'on demande à la réouverture de l'application.

    Bornée dans le temps : au-delà d'une heure, la conversation est loin et l'invite devient du
    bruit. **Un tap, puis on n'insiste plus de la session.**"""

    def __init__(self, attempts: ContactAttemptStore, *, clock) -> None:
        self._attempts = attempts
        self._clock = clock

    async def execute(
        self, *, account_id: UUID, tenant_id: UUID
    ) -> list[ContactAttempt]:
        since = self._clock() - FOREGROUND_WINDOW
        return await self._attempts.pending_for(
            account_id=account_id, tenant_id=tenant_id, since=since
        )
