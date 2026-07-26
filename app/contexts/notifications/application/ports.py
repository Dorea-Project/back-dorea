"""Port `PushSender` — l'acheminement **réel** d'une push vers un jeton d'appareil.

Abstrait : `HttpPushSender` (FCM / passerelle) en prod, `LoggingPushSender` en repli (dev)."""

from abc import ABC, abstractmethod


class PushSender(ABC):
    @abstractmethod
    async def send(
        self, *, token: str, title: str, body: str, data: dict | None
    ) -> None: ...
