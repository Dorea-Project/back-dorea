"""L'OTP par WhatsApp, et sa porte de secours.

Avec un numero unique pour toute la plateforme, un membre qui bloque Dorea ne
recevrait plus ses codes : le repli SMS n'est pas un confort, c'est la seule
sortie. Ces tests l'exigent.
"""

import pytest

from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.infrastructure.otp import LoggingOtpSender
from app.contexts.auth.infrastructure.otp_delivery import (
    HttpSmsOtpSender,
    RoutingOtpSender,
    build_otp_sender,
)
from app.contexts.messaging.application.otp_sender import MessagingOtpSender
from app.contexts.messaging.application.ports import (
    MessageChannel,
    OutboundMessage,
    ProviderReceipt,
    TemplateRef,
)
from app.contexts.messaging.domain.enums import (
    Channel,
    DeliveryOutcome,
    TemplateCategory,
)
from app.contexts.messaging.domain.errors import (
    ChannelUnavailableError,
    MessageRejectedError,
)
from app.core.config import Settings

_TEMPLATE = TemplateRef(
    name="dorea_otp", language="fr", category=TemplateCategory.AUTHENTICATION
)


class _Recorder(MessageChannel):
    def __init__(self, channel: Channel, fails: Exception | None = None) -> None:
        self._channel = channel
        self._fails = fails
        self.sent: list[OutboundMessage] = []

    @property
    def channel(self) -> Channel:
        return self._channel

    async def send(self, message: OutboundMessage) -> ProviderReceipt:
        if self._fails is not None:
            raise self._fails
        self.sent.append(message)
        return ProviderReceipt(
            channel=self._channel, outcome=DeliveryOutcome.ACCEPTED
        )


async def _send(sender: MessagingOtpSender) -> None:
    await sender.send(
        channel=OtpChannel.SMS,
        target="+225 07 47 76 90 69",
        code="123456",
        purpose=OtpPurpose.NEW_DEVICE,
    )


async def test_whatsapp_carries_the_code_as_placeholder():
    whatsapp = _Recorder(Channel.WHATSAPP)

    await _send(
        MessagingOtpSender(primary=whatsapp, fallback=None, template=_TEMPLATE)
    )

    message = whatsapp.sent[0]
    assert message.template.placeholders == ("123456",)
    assert message.template.category is TemplateCategory.AUTHENTICATION
    # Le numero part au format du fournisseur : international, sans « + », sans
    # espaces.
    assert message.to == "2250747769069"


async def test_the_code_reaches_the_copy_button_too():
    """Le corps l'affiche, le bouton le copie : deux variables, un seul code."""
    whatsapp = _Recorder(Channel.WHATSAPP)

    await _send(
        MessagingOtpSender(
            primary=whatsapp, fallback=None, template=_TEMPLATE
        )
    )

    assert whatsapp.sent[0].template.button_placeholders == ("123456",)


async def test_a_template_without_a_button_gets_none():
    whatsapp = _Recorder(Channel.WHATSAPP)

    await _send(
        MessagingOtpSender(
            primary=whatsapp,
            fallback=None,
            template=_TEMPLATE,
            copy_code_button=False,
        )
    )

    assert whatsapp.sent[0].template.button_placeholders == ()


async def test_the_same_code_travels_in_both_forms():
    """Le repli ne reconstruit pas le message : il ne peut pas dire autre chose."""
    whatsapp = _Recorder(Channel.WHATSAPP)

    await _send(
        MessagingOtpSender(primary=whatsapp, fallback=None, template=_TEMPLATE)
    )

    message = whatsapp.sent[0]
    assert "123456" in message.text
    assert message.template.placeholders == ("123456",)


@pytest.mark.parametrize(
    "failure",
    [
        ChannelUnavailableError("panne"),
        MessageRejectedError("numero sans compte WhatsApp"),
    ],
)
async def test_sms_takes_over_when_whatsapp_fails(failure):
    whatsapp = _Recorder(Channel.WHATSAPP, fails=failure)
    sms = _Recorder(Channel.SMS)

    await _send(
        MessagingOtpSender(primary=whatsapp, fallback=sms, template=_TEMPLATE)
    )

    assert len(sms.sent) == 1
    assert "123456" in sms.sent[0].text


async def test_without_fallback_the_failure_surfaces():
    """Sans porte de secours, l'echec doit remonter — pas etre avale."""
    whatsapp = _Recorder(Channel.WHATSAPP, fails=ChannelUnavailableError("panne"))

    with pytest.raises(ChannelUnavailableError):
        await _send(
            MessagingOtpSender(primary=whatsapp, fallback=None, template=_TEMPLATE)
        )


# --- Cablage ----------------------------------------------------------------


def test_messaging_takes_over_the_mobile_channel_when_configured():
    router = build_otp_sender(
        Settings(
            _env_file=None,
            infobip_base_url="https://qwvrgw.api.infobip.com",
            infobip_api_key="k",
            whatsapp_sender="447860088970",
        )
    )

    assert isinstance(router, RoutingOtpSender)
    assert isinstance(router._sms, MessagingOtpSender)


def test_the_old_sms_provider_still_works_during_the_switch():
    router = build_otp_sender(
        Settings(_env_file=None, sms_provider_url="https://sms.example", sms_provider_token="tok")
    )

    assert isinstance(router._sms, HttpSmsOtpSender)


def test_nothing_configured_still_falls_back_to_the_log():
    router = build_otp_sender(Settings(_env_file=None))

    assert isinstance(router._sms, LoggingOtpSender)


def test_hardened_environments_refuse_an_unconfigured_channel():
    """Le repli journal ecrit le code en clair : interdit hors « local ».

    L'e-mail est configure, le canal mobile ne l'est pas : c'est precisement le
    cas ou l'on pourrait croire l'acheminement en place.
    """
    production = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="x" * 48,
        backoffice_service_token="y" * 48,
        backoffice_cookie_secure=True,
        cors_origins=["https://app.dorea.church"],
        smtp_host="smtp.example",
    )

    with pytest.raises(RuntimeError):
        build_otp_sender(production)
