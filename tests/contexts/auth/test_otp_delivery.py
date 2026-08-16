"""Acheminement OTP de production : aiguillage par canal, repli sûr, payload SMS."""

import httpx

from app.contexts.auth.application.ports import OtpSender
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.infrastructure.otp import LoggingOtpSender
from app.contexts.auth.infrastructure.otp_delivery import (
    HttpSmsOtpSender,
    RoutingOtpSender,
    SmtpEmailOtpSender,
    build_otp_sender,
)
from app.core.config import Settings


class _Recorder(OtpSender):
    def __init__(self, label):
        self.label = label
        self.calls = []

    async def send(self, *, channel, target, code, purpose):
        self.calls.append((channel, target, code))


# --- Aiguillage par canal ---


async def test_routing_sends_email_to_email_and_sms_to_sms():
    email, sms = _Recorder("email"), _Recorder("sms")
    router = RoutingOtpSender(email=email, sms=sms)

    await router.send(
        channel=OtpChannel.EMAIL, target="pasteur@x.com", code="111111",
        purpose=OtpPurpose.NEW_DEVICE,
    )
    await router.send(
        channel=OtpChannel.SMS, target="+2250700", code="222222",
        purpose=OtpPurpose.NEW_DEVICE,
    )

    assert email.calls == [(OtpChannel.EMAIL, "pasteur@x.com", "111111")]
    assert sms.calls == [(OtpChannel.SMS, "+2250700", "222222")]


# --- Repli sûr : non configuré → log (le dev tourne sans fournisseur) ---


def test_build_falls_back_to_logging_when_unconfigured():
    router = build_otp_sender(Settings(_env_file=None, smtp_host=None, sms_provider_url=None))
    assert isinstance(router, RoutingOtpSender)
    assert isinstance(router._email, LoggingOtpSender)
    assert isinstance(router._sms, LoggingOtpSender)


def test_build_uses_real_senders_when_configured():
    router = build_otp_sender(
        Settings(
            _env_file=None,
            smtp_host="smtp.example", smtp_username="u", smtp_password="p",
            sms_provider_url="https://sms.example", sms_provider_token="tok",
        )
    )
    assert isinstance(router._email, SmtpEmailOtpSender)
    assert isinstance(router._sms, HttpSmsOtpSender)


# --- L'adaptateur SMS poste bien le code ---


async def test_http_sms_sender_posts_the_code(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

    async def fake_post(self, url, json=None, headers=None):
        captured.update(url=url, json=json, headers=headers)
        return _Resp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await HttpSmsOtpSender(
        provider_url="https://sms.example", token="tok", sender_id="Dorea"
    ).send(
        channel=OtpChannel.SMS, target="+2250700", code="123456",
        purpose=OtpPurpose.NEW_DEVICE,
    )

    assert captured["url"] == "https://sms.example"
    assert captured["json"]["to"] == "+2250700"
    assert "123456" in captured["json"]["message"]
    assert captured["headers"]["Authorization"] == "Bearer tok"
