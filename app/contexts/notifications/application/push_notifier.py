"""`PushNotifier` — l'implémentation du port `Notifier` par la push.

Résout les **jetons** des comptes visés puis les envoie un à un via `PushSender`. **Best-effort** :
un échec d'envoi (jeton périmé, fournisseur indisponible) est journalisé, jamais propagé — une
notification ne casse pas l'action qui l'a déclenchée.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.notifications.application.notifier import Notifier, PushNotification
from app.contexts.notifications.application.ports import PushSender
from app.contexts.notifications.domain.repositories import DeviceRepository
from app.core.logging import get_logger

_logger = get_logger("notifications.push")


class PushNotifier(Notifier):
    def __init__(self, devices: DeviceRepository, sender: PushSender) -> None:
        self._devices = devices
        self._sender = sender

    async def notify(
        self, account_ids: list[UUID], notification: PushNotification
    ) -> None:
        if not account_ids:
            return
        tokens = await self._devices.tokens_for_accounts(account_ids)
        for token in tokens:
            try:
                await self._sender.send(
                    token=token,
                    title=notification.title,
                    body=notification.body,
                    data=notification.data,
                )
            except Exception as exc:  # best-effort : une push ne casse jamais l'appelant
                _logger.warning("push_send_failed", error=str(exc))
