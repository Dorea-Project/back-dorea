"""Webhooks Infobip — accusés de réception et messages entrants.

Route **publique** : c'est un tiers qui appelle, il n'a ni compte ni jeton de
session.

## Comment elle est gardée, et pourquoi c'est plus faible que chez Meta

Infobip ne signe pas ses appels — pas de HMAC, rien qui prouve l'origine. La
seule barrière praticable est un **secret partagé**, posé dans l'URL configurée
chez eux et comparé ici en temps constant. Il faut donc le traiter comme un mot
de passe : long, tiré au hasard, changé s'il fuite.

Conséquence à assumer : quelqu'un qui connaîtrait ce secret pourrait nous
raconter qu'un message a été remis alors qu'il ne l'a pas été. C'est pourquoi
**aucune décision de sécurité ne dépend de ces routes** — elles renseignent un
journal d'acheminement et enregistrent des refus, elles n'ouvrent aucun accès et
ne valident aucun code.

## Pourquoi elles répondent toujours 204

Un fournisseur qui reçoit une erreur rejoue, puis se décourage et coupe le flux.
Un corps illisible est donc absorbé et journalisé, jamais renvoyé en 4xx : on
préfère perdre un accusé que perdre la file entière.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, status

from app.api.deps import DbSession
from app.contexts.messaging.interface.schemas import (
    InfobipInboundBatch,
    InfobipReportBatch,
)
from app.contexts.messaging.infrastructure.persistence.repository import (
    DeliveryRepository,
    OptOutRepository,
)
from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter()

_logger = get_logger("messaging.webhook")


def _authorize(token: str | None) -> None:
    expected = get_settings().messaging_webhook_token

    if not expected:
        # Pas de secret configuré : la route reste fermée plutôt que grande
        # ouverte. Un webhook non protégé est une porte laissée ouverte sur
        # l'état d'acheminement de toute la plateforme.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook non configuré."
        )

    if token is None or not secrets.compare_digest(token, expected):
        _logger.warning("webhook_rejected")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.post(
    "/webhooks/infobip/reports",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Infobip — accusés de réception",
)
async def delivery_reports(
    payload: InfobipReportBatch,
    session: DbSession,
    x_dorea_webhook_token: str | None = Header(default=None),
) -> None:
    _authorize(x_dorea_webhook_token)

    now = datetime.now(UTC)
    deliveries = DeliveryRepository(session)

    for report in payload.reports():
        await deliveries.record(report, now=now)

        if report.is_failure:
            # Le motif d'échec est utile ; le numéro ne l'est pas (DOREA-027).
            _logger.warning(
                "delivery_failed",
                message_id=report.message_id,
                status=report.status,
                error=report.error_code,
            )

    await session.commit()


@router.post(
    "/webhooks/infobip/inbound",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Infobip — messages entrants (STOP)",
)
async def inbound_messages(
    payload: InfobipInboundBatch,
    session: DbSession,
    x_dorea_webhook_token: str | None = Header(default=None),
) -> None:
    """Une seule parole est écoutée aujourd'hui : le refus.

    Le reste est ignoré — sans boîte de réception, répondre à quelqu'un qui
    écrit serait promettre une lecture que personne n'assure.
    """
    _authorize(x_dorea_webhook_token)

    now = datetime.now(UTC)
    opt_outs = OptOutRepository(session)

    for message in payload.messages():
        if message.asks_to_stop:
            await opt_outs.add(
                phone_number=message.from_number,
                channel=message.channel,
                keyword=message.keyword,
                now=message.received_at or now,
            )
            _logger.info("opt_out_recorded", channel=message.channel.value)

        elif message.asks_to_resume:
            await opt_outs.remove(message.from_number)
            _logger.info("opt_out_lifted", channel=message.channel.value)

    await session.commit()
