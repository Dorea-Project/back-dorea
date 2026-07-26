"""Erreurs du module Notifications — codes préfixés `NOTIF_`."""

from app._shared.domain.errors import DomainError


class NotificationError(DomainError):
    code = "NOTIF_ERROR"


class DeviceTokenRequiredError(NotificationError):
    """Enregistrer un appareil exige son jeton push."""

    code = "NOTIF_DEVICE_TOKEN_REQUIRED"
    http_status = 422
