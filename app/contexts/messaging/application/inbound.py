"""Ce qui revient du fournisseur : les accusés, et ce que les gens répondent.

Deux flux, deux natures. Un accusé dit ce qu'est devenu **notre** message ; un
message entrant est la parole de quelqu'un — et la seule qu'on écoute pour
l'instant est « stop ».
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.contexts.messaging.domain.enums import Channel

#: Ce qui vaut refus. Volontairement large et multilingue : quelqu'un qui veut
#: qu'on cesse de lui écrire ne doit pas avoir à deviner le mot exact, et un
#: refus mal compris est un refus ignoré.
STOP_KEYWORDS = frozenset(
    {
        "stop",
        "arret",
        "arrêt",
        "arreter",
        "arrêter",
        "desabonner",
        "désabonner",
        "desabonnement",
        "désabonnement",
        "unsubscribe",
        "cancel",
        "quit",
    }
)

#: Ce qui annule le refus.
START_KEYWORDS = frozenset({"start", "oui", "reprendre", "subscribe"})


@dataclass(frozen=True)
class DeliveryReport:
    """Le sort d'un message, tel que le fournisseur le rapporte."""

    message_id: str
    status: str
    provider_message_id: str | None = None
    error_code: str | None = None
    error_text: str | None = None
    occurred_at: datetime | None = None

    @property
    def is_failure(self) -> bool:
        return self.error_code is not None or self.status.lower() in {
            "undeliverable",
            "expired",
            "rejected",
            "failed",
        }


@dataclass(frozen=True)
class InboundMessage:
    """Un message reçu d'une personne."""

    from_number: str
    text: str
    channel: Channel = Channel.WHATSAPP
    received_at: datetime | None = None

    @property
    def keyword(self) -> str:
        """Le premier mot, nettoyé. « STOP ! » et « stop » sont le même refus."""
        stripped = self.text.strip().lower()
        if not stripped:
            return ""

        first = stripped.split()[0]

        return "".join(c for c in first if c.isalpha())

    @property
    def asks_to_stop(self) -> bool:
        return self.keyword in STOP_KEYWORDS

    @property
    def asks_to_resume(self) -> bool:
        return self.keyword in START_KEYWORDS
