"""La boucle boomerang — enregistrer l'effort avant de perdre la main.

Le pire des faux négatifs : le responsable appelle vingt minutes, ne revient pas le dire, et le
produit conclut que la veille ne fonctionne pas. C'est ce qui fait abandonner un outil qui
marchait.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.contact_loop import (
    FOREGROUND_WINDOW,
    RETURN_PROMPT_DELAY,
    AnswerContact,
    PendingAttempts,
    StartContact,
)
from app.contexts.watch.domain.contact import (
    HARD_EXPIRY_ATTEMPTS,
    ContactChannel,
    ContactResult,
)
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from tests.contexts.watch.fakes import FakeContactAttempts, FakeSignals

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


class _Scheduler:
    def __init__(self):
        self.calls = []

    async def schedule(self, account_ids, notification, *, at):
        self.calls.append((list(account_ids), notification, at))


def _case(*, tenant, subject, origin=CasePriority.ABSENCE, owner=None) -> Signal:
    return Signal(
        id=uuid4(), tenant_id=tenant, subject_id=subject, origin=origin,
        reason="Sans nouvelles depuis 4 semaines.", opened_at=_NOW,
        status=SignalStatus.ASSIGNED, owner_account_id=owner,
    )


def _loop(signals, attempts, scheduler=None, *, now=_NOW):
    return StartContact(attempts, signals, scheduler, clock=lambda: now)


# --- P1 : l'intention s'écrit au départ ---------------------------------------------------


async def test_the_effort_is_recorded_before_the_app_loses_focus():
    """Si le responsable ne revient jamais, on saura au moins qu'il a essayé."""
    tenant, owner, subject = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=subject, owner=owner)
    signals.rows.append(case)

    started = await _loop(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.CALL, person_label="Awa",
    )

    (attempt,) = attempts.rows
    assert attempt.id == started.attempt_id
    assert attempt.result is ContactResult.PENDING  # l'état normal, pas une anomalie
    assert attempt.attempted_at == _NOW


async def test_starting_a_contact_stamps_the_two_pilot_metrics():
    """`first_seen_at` alimente le taux d'ignorés ; `first_contact_at`, le délai reine."""
    tenant, owner, subject = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=subject, owner=owner)
    signals.rows.append(case)

    await _loop(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.WHATSAPP, person_label="Awa",
    )

    assert case.first_seen_at == _NOW
    assert case.first_contact_at == _NOW
    assert case.status is SignalStatus.IN_CONTACT


async def test_a_second_attempt_never_rewrites_the_first_contact():
    """Le délai détection → **premier** contact ne se recalcule pas."""
    tenant, owner, subject = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=subject, owner=owner)
    signals.rows.append(case)

    await _loop(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.CALL, person_label="Awa",
    )
    later = _NOW + timedelta(days=2)
    await _loop(signals, attempts, now=later).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.CALL, person_label="Awa",
    )

    assert case.first_contact_at == _NOW
    assert len(attempts.rows) == 2


# --- P2 : le rappel de retour --------------------------------------------------------------


async def test_the_return_prompt_carries_its_answers():
    """On répond **sans ouvrir l'application** — exiger un détour perd les trois quarts."""
    tenant, owner = uuid4(), uuid4()
    signals, attempts, scheduler = FakeSignals(), FakeContactAttempts(), _Scheduler()
    case = _case(tenant=tenant, subject=uuid4(), owner=owner)
    signals.rows.append(case)

    started = await _loop(signals, attempts, scheduler).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.CALL, person_label="Awa Traoré",
    )

    (targets, notification, at) = scheduler.calls[0]
    assert targets == [owner]  # au responsable, jamais à la personne
    assert "Awa Traoré" in notification.body
    assert notification.data["actions"] == "reached,not_reached,postponed"
    assert at == started.prompt_at == _NOW + RETURN_PROMPT_DELAY


async def test_answering_once_is_enough():
    """Une tentative résolue ne se réécrit pas : on n'insiste pas, et la métrique reste juste."""
    tenant, owner = uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=uuid4(), owner=owner)
    signals.rows.append(case)
    started = await _loop(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.CALL, person_label="Awa",
    )
    answer = AnswerContact(attempts, signals, clock=lambda: _NOW + timedelta(hours=3))

    await answer.execute(attempt_id=started.attempt_id, result=ContactResult.REACHED)
    await answer.execute(attempt_id=started.attempt_id, result=ContactResult.NOT_REACHED)

    assert attempts.rows[0].result is ContactResult.REACHED


# --- P3 : la reprise au premier plan --------------------------------------------------------


async def test_only_recent_attempts_are_worth_asking_about():
    """Au-delà d'une heure, la conversation est loin : l'invite devient du bruit."""
    tenant, owner = uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=uuid4(), owner=owner)
    signals.rows.append(case)

    await _loop(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.CALL, person_label="Awa",
    )

    just_after = await PendingAttempts(
        attempts, clock=lambda: _NOW + timedelta(minutes=10)
    ).execute(account_id=owner, tenant_id=tenant)
    much_later = await PendingAttempts(
        attempts, clock=lambda: _NOW + FOREGROUND_WINDOW + timedelta(minutes=1)
    ).execute(account_id=owner, tenant_id=tenant)

    assert len(just_after) == 1
    assert much_later == []


async def test_an_answered_attempt_is_never_asked_about_again():
    tenant, owner = uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=uuid4(), owner=owner)
    signals.rows.append(case)
    started = await _loop(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.CALL, person_label="Awa",
    )

    await AnswerContact(attempts, signals, clock=lambda: _NOW).execute(
        attempt_id=started.attempt_id, result=ContactResult.POSTPONED
    )
    remaining = await PendingAttempts(
        attempts, clock=lambda: _NOW + timedelta(minutes=5)
    ).execute(account_id=owner, tenant_id=tenant)

    assert remaining == []


# --- La péremption dure ----------------------------------------------------------------------


async def test_three_failed_attempts_close_a_deadline_case():
    """Sans elle, un module d'évangélisation qui fonctionne noie son inviteur en trois semaines.

    La personne **reste en base** : elle sort de la file, pas du fichier."""
    tenant, owner, subject = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=subject, origin=CasePriority.DEADLINE, owner=owner)
    signals.rows.append(case)

    for _ in range(HARD_EXPIRY_ATTEMPTS):
        started = await _loop(signals, attempts).execute(
            signal_id=case.id, tenant_id=tenant, by_account_id=owner,
            channel=ContactChannel.CALL, person_label="Awa",
        )
        await AnswerContact(attempts, signals, clock=lambda: _NOW).execute(
            attempt_id=started.attempt_id, result=ContactResult.NOT_REACHED
        )

    assert case.status is SignalStatus.CLOSED
    assert case.outcome is SignalOutcome.UNREACHABLE_ARCHIVED
    assert case.closed_by_account_id is None  # clôture système, assumée


async def test_the_hard_expiry_never_touches_another_regime():
    """Elle existe pour un problème de volume sur les invités — pas comme règle générale."""
    tenant, owner, subject = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=subject, origin=CasePriority.ABSENCE, owner=owner)
    signals.rows.append(case)

    for _ in range(HARD_EXPIRY_ATTEMPTS + 2):
        started = await _loop(signals, attempts).execute(
            signal_id=case.id, tenant_id=tenant, by_account_id=owner,
            channel=ContactChannel.CALL, person_label="Awa",
        )
        await AnswerContact(attempts, signals, clock=lambda: _NOW).execute(
            attempt_id=started.attempt_id, result=ContactResult.NOT_REACHED
        )

    assert case.is_live is True  # seul un humain fermera


async def test_reaching_someone_never_expires_anything():
    tenant, owner = uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(tenant=tenant, subject=uuid4(), origin=CasePriority.DEADLINE, owner=owner)
    signals.rows.append(case)

    for _ in range(HARD_EXPIRY_ATTEMPTS + 1):
        started = await _loop(signals, attempts).execute(
            signal_id=case.id, tenant_id=tenant, by_account_id=owner,
            channel=ContactChannel.CALL, person_label="Awa",
        )
        await AnswerContact(attempts, signals, clock=lambda: _NOW).execute(
            attempt_id=started.attempt_id, result=ContactResult.REACHED
        )

    assert case.is_live is True
