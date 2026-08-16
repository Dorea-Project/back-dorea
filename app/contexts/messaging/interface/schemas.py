"""Lecture des webhooks Infobip.

Le corps vient d'un tiers : on le lit avec méfiance, en ne réclamant que ce dont
on a besoin. Tout le reste est ignoré — un fournisseur ajoute des champs sans
prévenir, et une validation trop stricte transformerait une amélioration de leur
côté en panne du nôtre.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.contexts.messaging.application.inbound import DeliveryReport, InboundMessage
from app.contexts.messaging.domain.enums import Channel


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class InfobipStatus(_Lenient):
    group_id: int | None = Field(default=None, alias="groupId")
    name: str | None = None
    description: str | None = None


class InfobipError(_Lenient):
    name: str | None = None
    description: str | None = None


class InfobipReport(_Lenient):
    message_id: str | None = Field(default=None, alias="messageId")
    #: Ce que **nous** avions posé à l'envoi. Infobip le renvoie tel quel, et
    #: c'est notre seul lien fiable avec le message d'origine.
    bulk_id: str | None = Field(default=None, alias="bulkId")
    to: str | None = None
    sent_at: datetime | None = Field(default=None, alias="sentAt")
    done_at: datetime | None = Field(default=None, alias="doneAt")
    status: InfobipStatus | None = None
    error: InfobipError | None = None

    def to_report(self) -> DeliveryReport | None:
        if self.message_id is None:
            return None

        status = self.status.name if self.status else "unknown"
        error = self.error

        # Infobip renvoie toujours un bloc `error`, y compris quand tout va
        # bien : `NO_ERROR`, groupe 0. Le prendre pour un échec ferait passer
        # chaque message réussi pour un problème.
        failed = error is not None and (error.name or "").upper() not in {
            "",
            "NO_ERROR",
        }

        return DeliveryReport(
            message_id=self.message_id,
            status=(status or "unknown").lower(),
            error_code=error.name if failed and error else None,
            error_text=error.description if failed and error else None,
            occurred_at=self.done_at or self.sent_at,
        )


class InfobipReportBatch(_Lenient):
    results: list[InfobipReport] = Field(default_factory=list)

    def reports(self) -> list[DeliveryReport]:
        return [r for r in (entry.to_report() for entry in self.results) if r]


class InfobipInboundMessage(_Lenient):
    from_number: str | None = Field(default=None, alias="from")
    received_at: datetime | None = Field(default=None, alias="receivedAt")
    message: dict[str, Any] | None = None

    def to_message(self) -> InboundMessage | None:
        if self.from_number is None:
            return None

        content = self.message or {}
        text = content.get("text")

        # Une image, un audio, une position : rien à lire pour nous. On ne
        # fabrique pas un message vide, qui passerait pour une parole.
        if not isinstance(text, str):
            return None

        return InboundMessage(
            from_number=self.from_number,
            text=text,
            channel=Channel.WHATSAPP,
            received_at=self.received_at,
        )


class InfobipInboundBatch(_Lenient):
    results: list[InfobipInboundMessage] = Field(default_factory=list)

    def messages(self) -> list[InboundMessage]:
        return [m for m in (entry.to_message() for entry in self.results) if m]
