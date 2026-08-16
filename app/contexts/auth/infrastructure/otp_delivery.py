"""Acheminement **réel** de l'OTP (production) — email (SMTP) + SMS (HTTP).

Le port `OtpSender` reste abstrait ; ici trois adaptateurs concrets :
- `SmtpEmailOtpSender` — email (Owner / backoffice), via `smtplib` (stdlib, lancé hors boucle).
- `HttpSmsOtpSender` — SMS (membre / mobile), via un fournisseur HTTP générique (Twilio /
  Africa's Talking…) avec `httpx`.
- `RoutingOtpSender` — aiguille selon le canal (email vs SMS).

**Repli sûr** : `build_otp_sender(settings)` renvoie le sender réel là où c'est configuré, sinon le
`LoggingOtpSender` (le dev tourne sans fournisseur ; rien ne casse). On ne loggue jamais le code en
prod (le sender réel ne journalise que l'échec/succès d'acheminement).
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.contexts.auth.application.ports import OtpSender
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.infrastructure.otp import LoggingOtpSender
from app.contexts.messaging.application.otp_sender import MessagingOtpSender
from app.contexts.messaging.application.ports import TemplateRef
from app.contexts.messaging.domain.enums import TemplateCategory
from app.contexts.messaging.infrastructure.infobip import build_infobip_channels
from app.core.config import Settings
from app.core.logging import get_logger

_logger = get_logger("auth.otp.delivery")

_SUBJECT = "Votre code Dorea"
_BODY = "Votre code de vérification Dorea est : {code}\nIl expire bientôt. Ne le partagez pas."


class SmtpEmailOtpSender(OtpSender):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        use_tls: bool,
        sender: str,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._sender = sender

    async def send(
        self, *, channel: OtpChannel, target: str, code: str, purpose: OtpPurpose
    ) -> None:
        # `smtplib` est bloquant → on l'exécute hors de la boucle asyncio.
        await asyncio.to_thread(self._send_sync, target, code)
        # DOREA-027 — l'adresse est une donnée personnelle : elle ne va pas dans les
        # journaux. Le `purpose` suffit à diagnostiquer un problème d'acheminement.
        _logger.info("otp_email_sent", purpose=purpose.value)

    def _send_sync(self, target: str, code: str) -> None:
        message = EmailMessage()
        message["Subject"] = _SUBJECT
        message["From"] = self._sender
        message["To"] = target
        message.set_content(_BODY.format(code=code))
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._use_tls:
                # DOREA-018 — `starttls()` **sans contexte** n'authentifie rien : ni la
                # chaîne de certificats, ni le nom d'hôte. Un intermédiaire pouvait se
                # placer entre nous et le relais, et **lire les codes OTP**.
                # `create_default_context()` vérifie les deux.
                smtp.starttls(context=ssl.create_default_context())
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(message)


class HttpSmsOtpSender(OtpSender):
    def __init__(self, *, provider_url: str, token: str | None, sender_id: str) -> None:
        self._url = provider_url
        self._token = token
        self._sender_id = sender_id

    async def send(
        self, *, channel: OtpChannel, target: str, code: str, purpose: OtpPurpose
    ) -> None:
        payload = {
            "to": target,
            "from": self._sender_id,
            "message": _BODY.format(code=code),
        }
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
        # DOREA-027 — le numéro est une donnée personnelle : hors des journaux.
        _logger.info("otp_sms_sent", purpose=purpose.value)


class RoutingOtpSender(OtpSender):
    """Aiguille l'OTP selon son canal : email → owner/backoffice, SMS → membre/mobile."""

    def __init__(self, *, email: OtpSender, sms: OtpSender) -> None:
        self._email = email
        self._sms = sms

    async def send(
        self, *, channel: OtpChannel, target: str, code: str, purpose: OtpPurpose
    ) -> None:
        sender = self._email if channel is OtpChannel.EMAIL else self._sms
        await sender.send(channel=channel, target=target, code=code, purpose=purpose)


def build_otp_sender(settings: Settings) -> OtpSender:
    """Sender réel là où c'est configuré, sinon repli sur le log (**dev seulement**).

    Le repli journalise le code en clair : **interdit hors `local`** (fuite d'OTP dans les logs).
    En staging/production, chaque canal utilisé doit avoir un fournisseur réel."""
    if settings.environment in ("staging", "production") and not (
        settings.otp_email_enabled and settings.otp_sms_enabled
    ):
        raise RuntimeError(
            "Hors 'local', chaque canal OTP (e-mail ET SMS) doit avoir un fournisseur réel : "
            "le repli journalise le code OTP en clair."
        )
    fallback = LoggingOtpSender()
    email: OtpSender = (
        SmtpEmailOtpSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            sender=settings.otp_email_from,
        )
        if settings.otp_email_enabled
        else fallback
    )
    return RoutingOtpSender(email=email, sms=_build_mobile_sender(settings, fallback))


def _build_mobile_sender(settings: Settings, fallback: OtpSender) -> OtpSender:
    """L'OTP du membre : WhatsApp, avec repli SMS chez le même fournisseur.

    Trois états, dans cet ordre de préférence :

    1. **Messagerie configurée** — WhatsApp par modèle `authentication`, repli
       SMS automatique. C'est la voie normale.
    2. **Ancien fournisseur SMS seul** — conservé le temps de la bascule, pour
       qu'un déploiement en cours ne perde pas ses codes.
    3. **Rien** — repli journal, interdit hors `local` par le garde ci-dessus.
    """
    if settings.messaging_enabled:
        whatsapp, sms = build_infobip_channels(settings)

        return MessagingOtpSender(
            primary=whatsapp,
            fallback=sms,
            template=TemplateRef(
                name=settings.whatsapp_otp_template,
                language=settings.whatsapp_otp_language,
                category=TemplateCategory.AUTHENTICATION,
            ),
        )

    if settings.sms_provider_url is not None:
        return HttpSmsOtpSender(
            provider_url=settings.sms_provider_url,
            token=settings.sms_provider_token,
            sender_id=settings.sms_sender_id,
        )

    return fallback
