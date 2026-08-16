"""`MessagingOtpSender` — l'OTP mobile, par WhatsApp, avec repli SMS.

C'est la **voie transactionnelle** : l'envoi est immédiat, jamais mis en file
derrière une diffusion. Un code qui arrive en retard est un code périmé.

Le repli SMS n'est pas un confort. Avec un numéro WhatsApp unique pour toute la
plateforme (décision M1), un membre qui bloque ce numéro après une invitation ne
recevrait plus ses codes de connexion : il perdrait l'accès à son compte. Le SMS
est la porte de secours, et elle doit rester ouverte.
"""

from __future__ import annotations

from uuid import uuid4

from app.contexts.auth.application.ports import OtpSender
from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.messaging.application.ports import (
    MessageChannel,
    OutboundMessage,
    TemplateRef,
)
from app.contexts.messaging.domain.errors import MessagingError
from app.core.logging import get_logger

_logger = get_logger("messaging.otp")

_TEXT = "Votre code de vérification Dorea est : {code}\nIl expire bientôt. Ne le partagez pas."


class MessagingOtpSender(OtpSender):
    def __init__(
        self,
        *,
        primary: MessageChannel,
        fallback: MessageChannel | None,
        template: TemplateRef,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._template = template

    async def send(
        self, *, channel: OtpChannel, target: str, code: str, purpose: OtpPurpose
    ) -> None:
        message = OutboundMessage(
            to=_to_provider_format(target),
            template=TemplateRef(
                name=self._template.name,
                language=self._template.language,
                category=self._template.category,
                placeholders=(code,),
            ),
            text=_TEXT.format(code=code),
            message_id=str(uuid4()),
            purpose=purpose.value,
        )

        try:
            await self._primary.send(message)
        except MessagingError as first_failure:
            if self._fallback is None:
                raise

            # DOREA-027 — ni le numéro, ni le code dans les journaux. Le motif
            # et la cause suffisent à diagnostiquer un acheminement.
            _logger.warning(
                "otp_primary_failed",
                purpose=purpose.value,
                channel=self._primary.channel.value,
                reason=first_failure.code,
            )
            await self._fallback.send(message)
            _logger.info(
                "otp_sent_by_fallback",
                purpose=purpose.value,
                channel=self._fallback.channel.value,
            )
            return

        _logger.info(
            "otp_sent", purpose=purpose.value, channel=self._primary.channel.value
        )


def _to_provider_format(target: str) -> str:
    """`+2250747769069` → `2250747769069`.

    Infobip attend le numéro international sans `+`. La conversion se fait ici
    plutôt que dans l'adaptateur : c'est une règle du fournisseur, pas du
    transport, et le jour où l'on en change c'est ce fichier qui bouge.
    """
    return target.strip().removeprefix("+").replace(" ", "")
