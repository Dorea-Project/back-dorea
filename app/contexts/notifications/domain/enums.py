"""Énumérations du module Notifications."""

from enum import StrEnum


class DevicePlatform(StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class ScheduledStatus(StrEnum):
    """État d'une notification planifiée (outbox : enqueue → dispatch)."""

    PENDING = "pending"  # en attente de son heure
    SENT = "sent"  # dispatchée

