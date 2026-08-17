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

Depuis le lot 3bis, les deux gestes entrent par le **journal** : sans ça, une reprojection effaçait
`first_contact_at` — la métrique reine du pilote — sans pouvoir la reconstruire. La péremption dure
a suivi le même chemin : elle vit dans l'interpreter, qui reçoit le décompte et l'origine du cas
dans le fait, et un rejeu conclut donc la même chose qu'au premier jour.

Les trois ensemble, ou aucune : P1 seule laisse des tentatives éternellement en attente, P2 seule
n'a rien à rappeler, P3 seule arrive trop tard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app._shared.messages import MessageKey
from app.contexts.notifications.application.notifier import (
    NotificationScheduler,
    PushNotification,
)
from app.contexts.watch.application.case_acts import RecordCaseAct
from app.contexts.watch.application.ports import ContactAttemptStore, SignalStore
from app.contexts.watch.domain.contact import (
    ContactAttempt,
    ContactChannel,
    ContactResult,
)

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
        acts: RecordCaseAct,
        scheduler: NotificationScheduler | None = None,
        *,
        clock,
        id_factory=uuid4,
    ) -> None:
        self._attempts = attempts
        self._signals = signals
        self._acts = acts
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
        # Le sujet vient du **cas**, pas de l'appelant : c'est lui qui porte la personne, et un
        # geste doit dire de qui il s'agit sans qu'une surface ait à le retrouver.
        case = await self._signals.get_case(signal_id=signal_id, tenant_id=tenant_id)
        subject_id = case.subject_id if case is not None else signal_id
        # L'effort entre par le **journal**, comme tout le reste : sans ça, une reprojection
        # effaçait `first_contact_at` — la métrique reine du pilote — sans pouvoir la reconstruire.
        attempt_id = self._new_id()
        await self._acts.attempted(
            attempt_id=attempt_id,
            signal_id=signal_id,
            subject_id=subject_id,
            tenant_id=tenant_id,
            by_account_id=by_account_id,
            channel=channel,
        )

        prompt_at = now + RETURN_PROMPT_DELAY
        await self._schedule_return(attempt_id, by_account_id, person_label, prompt_at)
        return StartedContact(attempt_id=attempt_id, prompt_at=prompt_at)

    async def _schedule_return(
        self, attempt_id: UUID, owner: UUID, label: str, at: datetime
    ) -> None:
        """P2 — la **seule** notification du produit autorisée à insister.

        Les réponses sont dans la notification : on répond sans ouvrir l'application. Exiger un
        détour par l'app, c'est perdre les trois quarts des retours."""
        if self._scheduler is None:
            return
        await self._scheduler.schedule(
            [owner],
            PushNotification(
                key=MessageKey.WATCH_CONTACT_RETURN,
                params={"label": label},
                data={
                    "type": "contact_return",
                    "attempt_id": str(attempt_id),
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
        acts: RecordCaseAct,
        *,
        clock,
    ) -> None:
        self._attempts = attempts
        self._signals = signals
        self._acts = acts
        self._clock = clock

    async def execute(
        self, *, attempt_id: UUID, result: ContactResult, commitment: str | None = None
    ) -> ContactAttempt | None:
        """`commitment` : ce que **je** m'engage à faire ensuite — jamais ce que je pense d'elle.

        Le champ est optionnel et le restera : un responsable qui n'écrit rien n'a rien manqué,
        et la boucle de contact ne doit pas devenir un formulaire."""
        attempt = await self._attempts.get(attempt_id)
        if attempt is None or not attempt.awaits_answer:
            return attempt

        # Ce que le monde sait **maintenant** voyage avec le fait : le nombre de tentatives sans
        # réponse et l'origine du cas. C'est ce qui permet à l'interpreter de décider seul de la
        # péremption dure, sans rien relire — et à un rejeu de conclure la même chose.
        failed = await self._attempts.count_not_reached(attempt.signal_id)
        case = await self._signals.get_case(
            signal_id=attempt.signal_id, tenant_id=attempt.tenant_id
        )
        if case is None:
            return attempt  # le cas a disparu sous la tentative : rien à raconter
        await self._acts.answered(
            attempt=attempt,
            subject_id=case.subject_id,
            result=result,
            commitment=commitment,
            failed_attempts=failed + (1 if result is ContactResult.NOT_REACHED else 0),
            origin=case.origin.value,
        )
        return await self._attempts.get(attempt_id)


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
