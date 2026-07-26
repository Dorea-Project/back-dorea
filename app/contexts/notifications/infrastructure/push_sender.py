"""Acheminement **réel** de la push (production) + repli, sur le patron de l'OtpSender.

- `HttpPushSender` — POST vers un fournisseur HTTP générique (FCM HTTP v1 / passerelle), `httpx`.
- `LoggingPushSender` — repli (dev) : journalise, n'envoie rien.
- `build_push_sender(settings)` — le sender réel si `push_provider_url` est configuré, sinon le log
  (le dev tourne sans fournisseur ; s'active avec des identifiants, comme l'OtpSender).
"""

from __future__ import annotations

import httpx

from app.contexts.notifications.application.ports import PushSender
from app.core.config import Settings
from app.core.logging import get_logger

_logger = get_logger("notifications.push.sender")


class HttpPushSender(PushSender):
    def __init__(self, *, provider_url: str, key: str | None) -> None:
        self._url = provider_url
        self._key = key

    async def send(
        self, *, token: str, title: str, body: str, data: dict | None
    ) -> None:
        payload = {
            "to": token,
            "notification": {"title": title, "body": body},
            "data": data or {},
        }
        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()


class LoggingPushSender(PushSender):
    """Repli dev : trace l'intention d'envoi sans fournisseur (jamais le contenu sensible)."""

    async def send(
        self, *, token: str, title: str, body: str, data: dict | None
    ) -> None:
        _logger.info("push_would_send", title=title)


def build_push_sender(settings: Settings) -> PushSender:
    if settings.push_enabled:
        return HttpPushSender(
            provider_url=settings.push_provider_url, key=settings.push_provider_key
        )
    return LoggingPushSender()
