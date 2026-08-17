"""Module Notifications — appareils (jetons push) + envoi best-effort, repli sûr.

Depuis le bilingue, ce module porte aussi **le seul endroit du produit où le texte d'une push
naît**. Les tests de la section « Envoi » vérifient donc deux choses à la fois : que l'envoi
reste best-effort, et que le texte est rendu *par destinataire*, une fois par langue présente.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app._shared.domain.locale import DEFAULT_LOCALE, Locale
from app._shared.messages import Message, MessageKey
from app.contexts.iam.application.ports import LocaleResolver
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
from app.contexts.notifications.domain.aggregates import Device, ScheduledNotification
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

# Une notification quelconque, quand le test ne parle pas du texte mais du chemin.
_ANY = PushNotification(key=MessageKey.APPOINTMENT_CONFIRMED)


class _FakeDevices(DeviceRepository):
    def __init__(self, items=()):
        self._d = list(items)

    async def get_by_token(self, token):
        return next((d for d in self._d if d.token == token), None)

    async def add(self, device):
        self._d.append(device)

    async def save(self, device):
        pass  # muté en mémoire (même instance)

    async def remove_by_token(self, token, *, account_id):
        self._d = [
            d for d in self._d if not (d.token == token and d.account_id == account_id)
        ]

    async def list_by_account(self, account_id):
        return [d for d in self._d if d.account_id == account_id]

    async def tokens_by_account(self, account_ids):
        s = set(account_ids)
        grouped: dict = {}
        for d in self._d:
            if d.account_id in s:
                grouped.setdefault(d.account_id, []).append(d.token)
        return grouped


class _FakeLocales(LocaleResolver):
    """La langue de chacun, posée par le test. Tout le monde en `fr` par défaut."""

    def __init__(self, spoken=None):
        self._spoken = spoken or {}

    async def resolve_many(self, account_ids):
        return {a: self._spoken.get(a, DEFAULT_LOCALE) for a in account_ids}

    async def resolve_tenant(self, tenant_id):
        return DEFAULT_LOCALE  # une push se rend par lecteur : l'église n'entre pas ici


class _FakeSender(PushSender):
    def __init__(self):
        self.sent = []

    async def send(self, *, token, title, body, data):
        self.sent.append((token, title, body))

    @property
    def tokens(self):
        return [token for token, _, _ in self.sent]

    def text_for(self, token) -> tuple[str, str]:
        return next((t, b) for tok, t, b in self.sent if tok == token)


class _RaisingSender(PushSender):
    async def send(self, *, token, title, body, data):
        raise RuntimeError("fournisseur indisponible")


def _device(account, token) -> Device:
    return Device.register(
        id=uuid4(), account_id=account, token=token, platform=DevicePlatform.ANDROID, now=_NOW
    )


def _notifier(devices, sender, spoken=None) -> PushNotifier:
    return PushNotifier(devices, sender, _FakeLocales(spoken))


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
    await UnregisterDevice(devices).execute(token="tok", account_id=acc)
    assert devices._d == []


async def test_unregister_ne_touche_pas_l_appareil_d_un_autre():
    """DOREA-023 — un jeton n'est pas un secret : il transite, il se journalise.

    Connaître celui de quelqu'un d'autre suffisait à faire taire ses notifications."""
    victime, attaquant = uuid4(), uuid4()
    devices = _FakeDevices([_device(victime, "tok-victime")])

    await UnregisterDevice(devices).execute(token="tok-victime", account_id=attaquant)

    assert await devices.get_by_token("tok-victime") is not None  # intact


# --- Envoi ---


async def test_notifier_sends_to_all_tokens_of_targeted_accounts():
    acc, other = uuid4(), uuid4()
    devices = _FakeDevices([_device(acc, "a"), _device(acc, "b"), _device(other, "c")])
    sender = _FakeSender()
    await _notifier(devices, sender).notify([acc], _ANY)
    assert sorted(sender.tokens) == ["a", "b"]  # pas le jeton de l'autre compte


async def test_notifier_is_a_noop_without_targets():
    sender = _FakeSender()
    await _notifier(_FakeDevices(), sender).notify([], _ANY)
    assert sender.sent == []


async def test_push_is_best_effort_and_never_raises():
    acc = uuid4()
    devices = _FakeDevices([_device(acc, "tok")])
    # un envoi qui échoue ne doit pas remonter (une push ne casse pas l'action déclenchante)
    await _notifier(devices, _RaisingSender()).notify([acc], _ANY)


async def test_la_meme_notification_part_dans_deux_langues():
    """**Le cœur du lot.** Un seul geste du pasteur, deux membres, deux langues.

    L'église est francophone et l'un de ses membres lit l'anglais : c'est le cas d'Abidjan, et
    c'est ce qu'aucune phrase écrite au point d'appel ne pouvait servir."""
    francophone, anglophone = uuid4(), uuid4()
    devices = _FakeDevices([_device(francophone, "fr-tok"), _device(anglophone, "en-tok")])
    sender = _FakeSender()

    await _notifier(devices, sender, {anglophone: Locale.EN}).notify(
        [francophone, anglophone], PushNotification(key=MessageKey.APPOINTMENT_CONFIRMED)
    )

    assert sender.text_for("fr-tok") == (
        "Rendez-vous confirmé", "Votre rendez-vous a été confirmé."
    )
    assert sender.text_for("en-tok") == (
        "Appointment confirmed", "Your appointment has been confirmed."
    )


async def test_le_contenu_humain_traverse_les_deux_langues_intact():
    """Le titre de l'événement est écrit par un humain : il sort tel quel des deux côtés.
    Seule la coquille autour de lui change de langue."""
    francophone, anglophone = uuid4(), uuid4()
    devices = _FakeDevices([_device(francophone, "fr-tok"), _device(anglophone, "en-tok")])
    sender = _FakeSender()

    await _notifier(devices, sender, {anglophone: Locale.EN}).notify(
        [francophone, anglophone],
        PushNotification(key=MessageKey.EVENT_CANCELLED, params={"title": "Veillée de prière"}),
    )

    assert sender.text_for("fr-tok") == ("Événement annulé", "« Veillée de prière » a été annulé.")
    assert sender.text_for("en-tok") == (
        "Event cancelled", "“Veillée de prière” has been cancelled."
    )


async def test_un_titre_a_accolades_nest_pas_reinterprete():
    """Le `.format` porte sur le gabarit, jamais sur les valeurs — sinon un titre d'annonce
    contenant `{}` ferait exploser la publication de quelqu'un d'autre."""
    acc = uuid4()
    devices = _FakeDevices([_device(acc, "tok")])
    sender = _FakeSender()

    await _notifier(devices, sender).notify(
        [acc], PushNotification(key=MessageKey.EVENT_PUBLISHED, params={"title": "Culte {spécial}"})
    )

    assert sender.text_for("tok")[1] == "« Culte {spécial} »"


async def test_un_parametre_manquant_ne_casse_pas_la_publication():
    """Défaut de programmation (le test de structure du catalogue le rattrape en amont) — en
    production il fait taire la push, pas l'action qui l'a déclenchée."""
    acc = uuid4()
    devices = _FakeDevices([_device(acc, "tok")])
    sender = _FakeSender()

    await _notifier(devices, sender).notify(
        [acc], PushNotification(key=MessageKey.EVENT_PUBLISHED)  # « title » manquant
    )

    assert sender.sent == []


async def test_sans_appareil_on_nouvre_meme_pas_le_catalogue():
    sender = _FakeSender()
    await _notifier(_FakeDevices(), sender).notify([uuid4()], _ANY)
    assert sender.sent == []


def test_une_notification_sans_cle_ni_texte_est_refusee():
    """L'invariant qui empêche `key` de redevenir optionnelle pour de bon."""
    with pytest.raises(ValueError):
        PushNotification()
    with pytest.raises(ValueError):
        PushNotification(key=MessageKey.EVENT_REMOVED, rendered=Message("T", "B"))


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
    await OutboxScheduler(jobs, clock=lambda: _NOW).schedule([acc], _ANY, at=at)
    assert len(jobs.items) == 1
    job = jobs.items[0]
    assert job.is_pending and job.scheduled_for == at and job.account_ids == [acc]


async def test_l_outbox_met_la_cle_en_file_pas_la_phrase():
    """Le piège du lot : un rappel se pose des semaines avant d'être lu. Une phrase écrite ici
    se figerait dans la langue du jour où elle a été planifiée."""
    jobs = _FakeJobs()
    await OutboxScheduler(jobs, clock=lambda: _NOW).schedule(
        [uuid4()],
        PushNotification(
            key=MessageKey.EVENT_TOMORROW_AT,
            params={"title": "Veillée", "place": "Salle 2"},
        ),
        at=_NOW,
    )
    job = jobs.items[0]
    assert job.key is MessageKey.EVENT_TOMORROW_AT
    assert job.params == {"title": "Veillée", "place": "Salle 2"}
    assert job.legacy_title is None and job.legacy_body is None


async def test_scheduler_is_a_noop_without_targets():
    jobs = _FakeJobs()
    await OutboxScheduler(jobs, clock=lambda: _NOW).schedule([], _ANY, at=_NOW)
    assert jobs.items == []


async def test_dispatch_sends_due_jobs_and_marks_them_sent():
    acc = uuid4()
    jobs = _FakeJobs()
    past = datetime(2025, 12, 31, tzinfo=UTC)
    await OutboxScheduler(jobs, clock=lambda: past).schedule([acc], _ANY, at=past)
    notifier = _RecordingNotifier()
    sent = await DispatchDueNotifications(jobs, notifier, clock=lambda: _NOW).run()
    assert sent == 1
    assert notifier.calls[0][0] == [acc]
    assert jobs.items[0].status is ScheduledStatus.SENT and jobs.items[0].sent_at == _NOW


async def test_une_ligne_davant_le_bilingue_part_avec_son_texte():
    """La porte de sortie du déploiement : les rappels déjà en file portent leur phrase et
    aucune clé. Ils partent tels quels au lieu d'être devinés — aucun n'est perdu."""
    jobs = _FakeJobs()
    past = datetime(2025, 12, 31, tzinfo=UTC)
    jobs.items.append(
        ScheduledNotification(
            id=uuid4(), account_ids=[uuid4()], key=None, params={}, data=None,
            scheduled_for=past, status=ScheduledStatus.PENDING, created_at=past, sent_at=None,
            legacy_title="Rappel de rendez-vous", legacy_body="Votre rendez-vous approche.",
        )
    )
    notifier = _RecordingNotifier()

    sent = await DispatchDueNotifications(jobs, notifier, clock=lambda: _NOW).run()

    assert sent == 1
    assert notifier.calls[0][1].rendered == Message(
        "Rappel de rendez-vous", "Votre rendez-vous approche."
    )


async def test_dispatch_skips_jobs_not_yet_due():
    acc = uuid4()
    jobs = _FakeJobs()
    future = datetime(2026, 6, 1, tzinfo=UTC)
    await OutboxScheduler(jobs, clock=lambda: _NOW).schedule([acc], _ANY, at=future)
    notifier = _RecordingNotifier()
    sent = await DispatchDueNotifications(jobs, notifier, clock=lambda: _NOW).run()
    assert sent == 0 and notifier.calls == [] and jobs.items[0].is_pending


async def test_runner_drains_the_queue_across_multiple_passes():
    from scripts.dispatch_notifications import drain

    jobs = _FakeJobs()
    past = datetime(2025, 12, 31, tzinfo=UTC)
    scheduler = OutboxScheduler(jobs, clock=lambda: past)
    for _ in range(5):
        await scheduler.schedule([uuid4()], _ANY, at=past)
    notifier = _RecordingNotifier()
    dispatch = DispatchDueNotifications(jobs, notifier, clock=lambda: _NOW)
    # lot de 2 → passes 2+2+1 : le drain vide tout en une invocation
    total = await drain(dispatch, batch=2)
    assert total == 5 and len(notifier.calls) == 5
    assert all(j.status is ScheduledStatus.SENT for j in jobs.items)
