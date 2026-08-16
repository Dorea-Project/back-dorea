"""Canaux Infobip : forme du payload, lecture des statuts, erreurs distinguées."""

import httpx
import pytest

from app.contexts.messaging.application.ports import OutboundMessage, TemplateRef
from app.contexts.messaging.domain.enums import Channel, TemplateCategory
from app.contexts.messaging.domain.errors import (
    ChannelUnavailableError,
    MessageRejectedError,
)
from app.contexts.messaging.infrastructure.infobip import (
    InfobipSmsChannel,
    InfobipWhatsAppChannel,
    LoggingChannel,
    _InfobipClient,
    build_infobip_channels,
)
from app.core.config import Settings


def _message() -> OutboundMessage:
    return OutboundMessage(
        to="2250747769069",
        template=TemplateRef(
            name="dorea_otp",
            language="fr",
            category=TemplateCategory.AUTHENTICATION,
            placeholders=("123456",),
        ),
        text="Votre code de vérification Dorea est : 123456",
        message_id="ac4b645b-8a71-44d1-9253-82b2ae646ed6",
        purpose="new_device",
    )


def _client() -> _InfobipClient:
    return _InfobipClient(base_url="https://qwvrgw.api.infobip.com", api_key="k")


def _accepted(status_group: int = 1) -> dict:
    return {
        "messages": [
            {
                "to": "2250747769069",
                "messageId": "provider-id",
                "status": {"groupId": status_group, "name": "PENDING_ACCEPTED"},
            }
        ]
    }


class _Response:
    def __init__(self, status_code: int, body: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body or {}

    def json(self) -> dict:
        return self._body


def _fake_post(response: _Response, captured: dict):
    async def post(self, url, json=None, headers=None):
        captured.update(url=url, json=json, headers=headers)
        return response

    return post


# --- WhatsApp ---------------------------------------------------------------


async def test_whatsapp_posts_the_template_payload(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(200, _accepted()), captured)
    )

    receipt = await InfobipWhatsAppChannel(
        _client(), sender="447860088970"
    ).send(_message())

    assert captured["url"].endswith("/whatsapp/1/message/template")
    sent = captured["json"]["messages"][0]
    assert sent["from"] == "447860088970"
    assert sent["to"] == "2250747769069"
    # Notre identifiant est transmis : c'est lui qui rend l'envoi idempotent et
    # permet de rapprocher l'accuse de reception.
    assert sent["messageId"] == "ac4b645b-8a71-44d1-9253-82b2ae646ed6"
    assert sent["content"]["templateName"] == "dorea_otp"
    assert sent["content"]["templateData"]["body"]["placeholders"] == ["123456"]

    # L'en-tete Infobip n'est ni Bearer ni Basic.
    assert captured["headers"]["Authorization"] == "App k"

    assert receipt.channel is Channel.WHATSAPP
    assert receipt.provider_message_id == "provider-id"


async def test_whatsapp_rejects_a_dead_status_group(monkeypatch):
    # 5 = REJECTED : accepte en HTTP, mort a l'arrivee.
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(200, _accepted(5)), {})
    )

    with pytest.raises(MessageRejectedError):
        await InfobipWhatsAppChannel(_client(), sender="447860088970").send(_message())


# --- SMS --------------------------------------------------------------------


async def test_sms_posts_the_text_without_template(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(200, _accepted()), captured)
    )

    await InfobipSmsChannel(_client(), sender="Dorea").send(_message())

    assert captured["url"].endswith("/sms/2/text/advanced")
    sent = captured["json"]["messages"][0]
    assert sent["destinations"][0]["to"] == "2250747769069"
    assert "123456" in sent["text"]
    assert "content" not in sent


# --- Erreurs : reessayable ou non -------------------------------------------


@pytest.mark.parametrize("status", [500, 502, 429])
async def test_server_side_failures_are_retryable(monkeypatch, status):
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(status), {})
    )

    with pytest.raises(ChannelUnavailableError):
        await InfobipWhatsAppChannel(_client(), sender="s").send(_message())


async def test_network_failure_is_retryable(monkeypatch):
    async def explode(self, url, json=None, headers=None):
        raise httpx.ConnectError("dns")

    monkeypatch.setattr(httpx.AsyncClient, "post", explode)

    with pytest.raises(ChannelUnavailableError):
        await InfobipWhatsAppChannel(_client(), sender="s").send(_message())


async def test_rejected_message_is_not_retryable(monkeypatch):
    body = {"requestError": {"serviceException": {"text": "Template not found"}}}
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(400, body), {})
    )

    with pytest.raises(MessageRejectedError) as failure:
        await InfobipWhatsAppChannel(_client(), sender="s").send(_message())

    assert "Template not found" in str(failure.value)


# --- Le bouton « Copier le code » -------------------------------------------


async def test_the_copy_code_button_carries_its_own_parameter(monkeypatch):
    """Le modele d'authentification francais porte un bouton dont l'URL contient
    une variable. Elle se renseigne a part du corps : l'oublier fait refuser
    l'envoi, ou laisse un bouton vide a cote d'un code affiche."""
    captured: dict = {}
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(200, _accepted()), captured)
    )

    message = OutboundMessage(
        to="2250747769069",
        template=TemplateRef(
            name="authentication",
            language="fr",
            category=TemplateCategory.AUTHENTICATION,
            placeholders=("123456",),
            button_placeholders=("123456",),
        ),
        text="Votre code de vérification est 123456",
        message_id="id",
    )

    await InfobipWhatsAppChannel(_client(), sender="s").send(message)

    data = captured["json"]["messages"][0]["content"]["templateData"]
    assert data["body"]["placeholders"] == ["123456"]
    assert data["buttons"] == [{"type": "URL", "parameter": "123456"}]


async def test_a_template_without_buttons_declares_none(monkeypatch):
    """Declarer un bouton absent est aussi fautif que d'en oublier un."""
    captured: dict = {}
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(200, _accepted()), captured)
    )

    await InfobipWhatsAppChannel(_client(), sender="s").send(_message())

    data = captured["json"]["messages"][0]["content"]["templateData"]
    assert "buttons" not in data


# --- Retour du fournisseur : ou nous rappeler -------------------------------


async def test_the_callback_url_travels_with_the_message(monkeypatch):
    """Posee a l'envoi, pas dans le portail : le compte Infobip est unique, les
    environnements ne le sont pas — sans cela, les accuses du poste de
    developpement partiraient en production."""
    captured: dict = {}
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(200, _accepted()), captured)
    )

    await InfobipWhatsAppChannel(
        _client(), sender="s", notify_url="https://api.dorea.church/api/webhooks/infobip/reports"
    ).send(_message())

    sent = captured["json"]["messages"][0]
    assert sent["notifyUrl"].endswith("/api/webhooks/infobip/reports")


async def test_without_a_callback_url_nothing_is_added(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        httpx.AsyncClient, "post", _fake_post(_Response(200, _accepted()), captured)
    )

    await InfobipWhatsAppChannel(_client(), sender="s").send(_message())

    assert "notifyUrl" not in captured["json"]["messages"][0]


# --- Construction -----------------------------------------------------------


def test_unconfigured_falls_back_to_logging():
    whatsapp, sms = build_infobip_channels(Settings(_env_file=None))

    assert isinstance(whatsapp, LoggingChannel)
    assert isinstance(sms, LoggingChannel)


def test_configured_builds_real_channels():
    whatsapp, sms = build_infobip_channels(
        Settings(
            _env_file=None,
            infobip_base_url="https://qwvrgw.api.infobip.com",
            infobip_api_key="k",
            whatsapp_sender="447860088970",
        )
    )

    assert isinstance(whatsapp, InfobipWhatsAppChannel)
    assert isinstance(sms, InfobipSmsChannel)
