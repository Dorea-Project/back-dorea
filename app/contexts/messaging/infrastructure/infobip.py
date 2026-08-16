"""Adaptateurs Infobip — WhatsApp et SMS, plus le repli journal.

Un seul fournisseur pour les deux canaux : c'est ce qui rend le repli SMS de
l'OTP praticable — même compte, même jeton, une seule facture.

## Ce que l'API impose

- L'hôte est **propre au compte** (`xxxxx.api.infobip.com`) : il vient de la
  configuration, jamais d'une constante.
- L'en-tête est `Authorization: App <clé>` — ni `Bearer`, ni `Basic`.
- Le numéro est international **sans `+`**.
- `messageId` est fourni par l'appelant : c'est notre clé d'idempotence.
- Un HTTP 200 ne dit pas que le message est parti. Il dit qu'Infobip l'a pris.
  Le sort réel arrive par accusé de réception (étape 2).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.contexts.messaging.application.ports import (
    MessageChannel,
    OutboundMessage,
    ProviderReceipt,
)
from app.contexts.messaging.domain.enums import Channel, DeliveryOutcome
from app.contexts.messaging.domain.errors import (
    ChannelUnavailableError,
    MessageRejectedError,
)
from app.core.config import Settings
from app.core.logging import get_logger

_logger = get_logger("messaging.infobip")

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

#: Groupes de statut Infobip. 1 = PENDING, 3 = DELIVERED : le message vit.
#: 2 = UNDELIVERABLE, 4 = EXPIRED, 5 = REJECTED : il est mort à l'arrivée.
_LIVE_STATUS_GROUPS = frozenset({1, 3})


class _InfobipClient:
    """Transport partagé par les deux canaux.

    Isolé pour une raison : c'est le seul endroit qui sait lire une réponse
    d'Infobip, et donc le seul à corriger quand leur format changera.
    """

    def __init__(self, *, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"App {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    f"{self._base_url}{path}", json=payload, headers=self._headers
                )
        except httpx.HTTPError as e:
            # Réseau, DNS, délai dépassé : le fournisseur est injoignable, le
            # message n'est parti nulle part. Repliable.
            raise ChannelUnavailableError(
                "Fournisseur de messagerie injoignable.",
                details={"cause": type(e).__name__},
            ) from e

        if response.status_code >= 500:
            raise ChannelUnavailableError(
                "Le fournisseur de messagerie est en panne.",
                details={"status": response.status_code},
            )

        if response.status_code == 429:
            raise ChannelUnavailableError(
                "Débit dépassé chez le fournisseur.",
                details={"status": 429},
            )

        if response.status_code >= 400:
            # 401, 403 : jeton refusé. 400 : requête malformée, modèle inconnu.
            # Dans les deux cas, réessayer à l'identique ne changera rien.
            raise MessageRejectedError(
                _extract_error(response),
                details={"status": response.status_code},
            )

        return response.json()


class InfobipWhatsAppChannel(MessageChannel):
    """WhatsApp par modèle approuvé.

    Toujours par modèle, jamais en texte libre : hors de la fenêtre de 24 h,
    c'est la seule forme autorisée, et l'OTP est par nature hors fenêtre.
    """

    _PATH = "/whatsapp/1/message/template"

    def __init__(
        self, client: _InfobipClient, *, sender: str, notify_url: str | None = None
    ) -> None:
        self._client = client
        self._sender = sender
        self._notify_url = notify_url

    @property
    def channel(self) -> Channel:
        return Channel.WHATSAPP

    async def send(self, message: OutboundMessage) -> ProviderReceipt:
        template_data: dict[str, Any] = {
            "body": {"placeholders": list(message.template.placeholders)}
        }

        # Le bouton « Copier le code » porte la variable dans son URL : elle se
        # renseigne à part du corps. Les réponses rapides, elles, n'ont aucun
        # paramètre — on ne les déclare donc pas.
        if message.template.button_placeholders:
            template_data["buttons"] = [
                {"type": "URL", "parameter": parameter}
                for parameter in message.template.button_placeholders
            ]

        envelope: dict[str, Any] = {
            "from": self._sender,
            "to": message.to,
            "messageId": message.message_id,
            "content": {
                "templateName": message.template.name,
                "templateData": template_data,
                "language": message.template.language,
            },
        }

        if self._notify_url:
            envelope["notifyUrl"] = self._notify_url

        body = await self._client.post(self._PATH, {"messages": [envelope]})

        return _receipt(Channel.WHATSAPP, body)


class InfobipSmsChannel(MessageChannel):
    """SMS — le repli. Pas de modèle : le texte part tel quel."""

    _PATH = "/sms/2/text/advanced"

    def __init__(
        self, client: _InfobipClient, *, sender: str, notify_url: str | None = None
    ) -> None:
        self._client = client
        self._sender = sender
        self._notify_url = notify_url

    @property
    def channel(self) -> Channel:
        return Channel.SMS

    async def send(self, message: OutboundMessage) -> ProviderReceipt:
        envelope: dict[str, Any] = {
            "from": self._sender,
            "destinations": [{"to": message.to, "messageId": message.message_id}],
            "text": message.text,
        }

        if self._notify_url:
            envelope["notifyUrl"] = self._notify_url

        body = await self._client.post(self._PATH, {"messages": [envelope]})

        return _receipt(Channel.SMS, body)


class LoggingChannel(MessageChannel):
    """Repli de développement : trace l'intention, n'envoie rien.

    Ne journalise **ni le numéro, ni le contenu** — donc pas le code OTP. C'est
    ce qui le rend inoffensif ; l'ancien repli, lui, écrivait le code en clair
    et devait être interdit hors `local`.
    """

    def __init__(self, channel: Channel = Channel.WHATSAPP) -> None:
        self._channel = channel

    @property
    def channel(self) -> Channel:
        return self._channel

    async def send(self, message: OutboundMessage) -> ProviderReceipt:
        _logger.info(
            "message_would_send",
            channel=self._channel.value,
            purpose=message.purpose,
            template=message.template.name,
        )
        return ProviderReceipt(
            channel=self._channel, outcome=DeliveryOutcome.ACCEPTED
        )


def _receipt(channel: Channel, body: dict[str, Any]) -> ProviderReceipt:
    """Lit la première entrée de `messages` — nous n'en envoyons qu'une."""
    messages = body.get("messages") or []
    first = messages[0] if messages else {}
    status = first.get("status") or {}
    group = status.get("groupId")

    accepted = group in _LIVE_STATUS_GROUPS if group is not None else True

    if not accepted:
        raise MessageRejectedError(
            status.get("description") or "Message refusé par le fournisseur.",
            details={"status": status.get("name", "")},
        )

    return ProviderReceipt(
        channel=channel,
        outcome=DeliveryOutcome.ACCEPTED,
        provider_message_id=first.get("messageId"),
        provider_status=status.get("name"),
    )


def _extract_error(response: httpx.Response) -> str:
    """Sort le message d'erreur d'Infobip, sans jamais laisser fuiter le corps.

    Leur forme : `{"requestError": {"serviceException": {"text": "..."}}}`.
    """
    try:
        body = response.json()
    except ValueError:
        return "Le fournisseur a répondu une erreur illisible."

    exception = (body.get("requestError") or {}).get("serviceException") or {}

    return exception.get("text") or "Le fournisseur a refusé le message."


def build_infobip_channels(
    settings: Settings,
) -> tuple[MessageChannel, MessageChannel | None]:
    """Le canal principal et son repli, selon ce qui est configuré.

    Sans configuration, les deux tombent sur le journal : le développement
    tourne sans compte Infobip, et aucun code n'apparaît nulle part.
    """
    if not settings.messaging_enabled:
        return LoggingChannel(Channel.WHATSAPP), LoggingChannel(Channel.SMS)

    client = _InfobipClient(
        base_url=settings.infobip_base_url or "",
        api_key=settings.infobip_api_key or "",
    )

    notify_url = settings.messaging_notify_url

    whatsapp = InfobipWhatsAppChannel(
        client, sender=settings.whatsapp_sender or "", notify_url=notify_url
    )
    sms = InfobipSmsChannel(
        client, sender=settings.sms_sender_id, notify_url=notify_url
    )

    return whatsapp, sms
