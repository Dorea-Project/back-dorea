"""Injection de dépendances du module Notifications.

Expose aussi `build_notifier(session)` : l'adaptateur `Notifier` que les **autres contextes**
(RDV, Event, Annonces) reçoivent pour prévenir des personnes — sender réel ou repli selon la config.
"""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.contexts.iam.infrastructure.persistence.locale_resolver import SqlLocaleResolver
from app.contexts.notifications.application.commands.register_device import (
    RegisterDevice,
    UnregisterDevice,
)
from app.contexts.notifications.application.dispatch import (
    DispatchDueNotifications,
    OutboxScheduler,
)
from app.contexts.notifications.application.notifier import NotificationScheduler, Notifier
from app.contexts.notifications.application.ports import PushSender
from app.contexts.notifications.application.push_notifier import PushNotifier
from app.contexts.notifications.domain.repositories import DeviceRepository
from app.contexts.notifications.infrastructure.persistence.repository import (
    SqlDeviceRepository,
    SqlScheduledNotificationRepository,
)
from app.contexts.notifications.infrastructure.push_sender import build_push_sender
from app.core.config import get_settings


def _now() -> datetime:
    return datetime.now(UTC)


@lru_cache
def _sender() -> PushSender:
    # Un seul sender par configuration (réel ou repli) — construit une fois.
    return build_push_sender(get_settings())


def build_notifier(session: AsyncSession) -> Notifier:
    """L'adaptateur `Notifier` (push) — appelé par les autres contextes via ce point unique.

    Il reçoit le résolveur de langue : c'est au dispatch, et là seulement, qu'on sait **qui**
    lit — donc dans quelle langue rendre le catalogue."""
    return PushNotifier(SqlDeviceRepository(session), _sender(), SqlLocaleResolver(session))


def build_scheduler(session: AsyncSession) -> NotificationScheduler:
    """Le planificateur (outbox) — appelé par les contextes pour un envoi différé (rappels…)."""
    return OutboxScheduler(SqlScheduledNotificationRepository(session), clock=_now)


def get_dispatch(session: DbSession) -> DispatchDueNotifications:
    return DispatchDueNotifications(
        SqlScheduledNotificationRepository(session), build_notifier(session), clock=_now
    )


DispatchDep = Annotated[DispatchDueNotifications, Depends(get_dispatch)]


def get_devices(session: DbSession) -> DeviceRepository:
    return SqlDeviceRepository(session)


def get_register_command(session: DbSession) -> RegisterDevice:
    return RegisterDevice(SqlDeviceRepository(session), clock=_now)


def get_unregister_command(session: DbSession) -> UnregisterDevice:
    return UnregisterDevice(SqlDeviceRepository(session))


RegisterDeviceDep = Annotated[RegisterDevice, Depends(get_register_command)]
UnregisterDeviceDep = Annotated[UnregisterDevice, Depends(get_unregister_command)]
DeviceRepositoryDep = Annotated[DeviceRepository, Depends(get_devices)]
