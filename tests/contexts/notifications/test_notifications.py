"""Module Notifications — appareils (jetons push) + envoi best-effort, repli sûr."""

from datetime import UTC, datetime
from uuid import uuid4

from app.contexts.notifications.application.commands.register_device import (
    RegisterDevice,
    UnregisterDevice,
)
from app.contexts.notifications.application.dispatch import (
    DispatchDueNotifications,
    OutboxScheduler,
)
from app.contexts.notifications.application.notifier import PushNotification
from app.contexts.notifications.application.ports import PushSender
from app.contexts.notifications.application.push_notifier import PushNotifier
from app.contexts.notifications.domain.aggregates import Device
from app.contexts.notifications.domain.enums import DevicePlatform, ScheduledStatus
from app.contexts.notifications.domain.repositories import (
    DeviceRepository,
    ScheduledNotificationRepository,
)
from app.contexts.notifications.infrastructure.push_sender import (
    LoggingPushSender,
    build_push_sender,
)
from app.core.config import Settings

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeDevices(DeviceRepository):
    def __init__(self, items=()):
        self._d = list(items)

    async def get_by_token(self, token):
        return next((d for d in self._d if d.token == token), None)

    async def add(self, device):
        self._d.append(device)

    async def save(self, device):
        pass  # muté en mémoire (même instance)

    async def remove_by_token(self, token):
        self._d = [d for d in self._d if d.token != token]

    async def list_by_account(self, account_id):
        return [d for d in self._d if d.account_id == account_id]

    async def tokens_for_accounts(self, account_ids):
        s = set(account_ids)
        return [d.token for d in self._d if d.account_id in s]


class _FakeSender(PushSender):
    def __init__(self):
        self.sent = []

    async def send(self, *, token, title, body, data):
        self.sent.append(token)


class _RaisingSender(PushSender):
    async def send(self, *, token, title, body, data):
        raise RuntimeError("fournisseur indisponible")


def _device(account, token) -> Device:
    return Device.register(
        id=uuid4(), account_id=account, token=token, platform=DevicePlatform.ANDROID, now=_NOW
    )


# --- Appareils ---


async def test_registering_an_appareil():
    devices = _FakeDevices()
    await RegisterDevice(devices, clock=lambda: _NOW).execute(
        actor_account_id=uuid4(), token="tok1", platform=DevicePlatform.ANDROID
    )
    assert len(devices._d) == 1


async def test_re_registering_the_same_token_updates_not_duplicates():
    acc1, acc2 = uuid4(), uuid4()
    devices = _FakeDevices()
    reg = RegisterDevice(devices, clock=lambda: _NOW)
    await reg.execute(actor_account_id=acc1, token="tok", platform=DevicePlatform.ANDROID)
    await reg.execute(actor_account_id=acc2, token="tok", platform=DevicePlatform.IOS)  # même jeton
    assert len(devices._d) == 1 and devices._d[0].account_id == acc2


async def test_unregister_removes_the_device():
    acc = uuid4()
    devices = _FakeDevices([_device(acc, "tok")])
    await UnregisterDevice(devices).execute(token="tok")
    assert devices._d == []


# --- Envoi ---


async def test_notifier_sends_to_all_tokens_of_targeted_accounts():
    acc, other = uuid4(), uuid4()
    devices = _FakeDevices([_device(acc, "a"), _device(acc, "b"), _device(other, "c")])
    sender = _FakeSender()
    await PushNotifier(devices, sender).notify([acc], PushNotification(title="T", body="B"))
    assert sorted(sender.sent) == ["a", "b"]  # pas le jeton de l'autre compte


async def test_notifier_is_a_noop_without_targets():
    sender = _FakeSender()
    await PushNotifier(_FakeDevices(), sender).notify([], PushNotification(title="T", body="B"))
    assert sender.sent == []


async def test_push_is_best_effort_and_never_raises():
    acc = uuid4()
    devices = _FakeDevices([_device(acc, "tok")])
    # un envoi qui échoue ne doit pas remonter (une push ne casse pas l'action déclenchante)
    await PushNotifier(devices, _RaisingSender()).notify(
        [acc], PushNotification(title="T", body="B")
    )


def test_build_push_sender_falls_back_to_logging():
    assert isinstance(build_push_sender(Settings(push_provider_url=None)), LoggingPushSender)


# --- Outbox / fan-out asynchrone ---


class _FakeJobs(ScheduledNotificationRepository):
    def __init__(self):
        self.items = []

    async def add(self, job):
        self.items.append(job)

    async def save(self, job):
        pass  # muté en mémoire (même instance)

    async def list_due(self, now, *, limit):
        due = [j for j in self.items if j.is_pending and j.scheduled_for <= now]
        return due[:limit]


class _RecordingNotifier:
    def __init__(self):
        self.calls = []

    async def notify(self, account_ids, notification):
        self.calls.append((list(account_ids), notification))


async def test_scheduler_enqueues_a_pending_job():
    acc = uuid4()
    jobs = _FakeJobs()
    at = datetime(2026, 1, 2, tzinfo=UTC)
    await OutboxScheduler(jobs, clock=lambda: _NOW).schedule(
        [acc], PushNotification(title="T", body="B"), at=at
    )
    assert len(jobs.items) == 1
    job = jobs.items[0]
    assert job.is_pending and job.scheduled_for == at and job.account_ids == [acc]


async def test_scheduler_is_a_noop_without_targets():
    jobs = _FakeJobs()
    await OutboxScheduler(jobs, clock=lambda: _NOW).schedule(
        [], PushNotification(title="T", body="B"), at=_NOW
    )
    assert jobs.items == []


async def test_dispatch_sends_due_jobs_and_marks_them_sent():
    acc = uuid4()
    jobs = _FakeJobs()
    past = datetime(2025, 12, 31, tzinfo=UTC)
    await OutboxScheduler(jobs, clock=lambda: past).schedule(
        [acc], PushNotification(title="T", body="B"), at=past
    )
    notifier = _RecordingNotifier()
    sent = await DispatchDueNotifications(jobs, notifier, clock=lambda: _NOW).run()
    assert sent == 1
    assert notifier.calls[0][0] == [acc]
    assert jobs.items[0].status is ScheduledStatus.SENT and jobs.items[0].sent_at == _NOW


async def test_dispatch_skips_jobs_not_yet_due():
    acc = uuid4()
    jobs = _FakeJobs()
    future = datetime(2026, 6, 1, tzinfo=UTC)
    await OutboxScheduler(jobs, clock=lambda: _NOW).schedule(
        [acc], PushNotification(title="T", body="B"), at=future
    )
    notifier = _RecordingNotifier()
    sent = await DispatchDueNotifications(jobs, notifier, clock=lambda: _NOW).run()
    assert sent == 0 and notifier.calls == [] and jobs.items[0].is_pending


async def test_runner_drains_the_queue_across_multiple_passes():
    from scripts.dispatch_notifications import drain

    jobs = _FakeJobs()
    past = datetime(2025, 12, 31, tzinfo=UTC)
    scheduler = OutboxScheduler(jobs, clock=lambda: past)
    for _ in range(5):
        await scheduler.schedule([uuid4()], PushNotification(title="T", body="B"), at=past)
    notifier = _RecordingNotifier()
    dispatch = DispatchDueNotifications(jobs, notifier, clock=lambda: _NOW)
    # lot de 2 → passes 2+2+1 : le drain vide tout en une invocation
    total = await drain(dispatch, batch=2)
    assert total == 5 and len(notifier.calls) == 5
    assert all(j.status is ScheduledStatus.SENT for j in jobs.items)
