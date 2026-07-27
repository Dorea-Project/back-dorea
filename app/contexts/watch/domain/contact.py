"""La **tentative de contact** — et pourquoi elle s'écrit au départ, jamais au retour.

Dorea n'héberge pas le contact : on sort vers WhatsApp ou le téléphone. Mais **on ne revient
pas**. Le responsable appelle, la conversation dure vingt minutes, il passe à autre chose, et
l'issue n'est jamais enregistrée.

Le signal reste ouvert. Le taux d'ignorés explose — **non parce que personne n'a appelé, mais
parce que personne n'est revenu le dire.** Le système conclut que la veille ne fonctionne pas
alors que le contact humain a bien eu lieu. C'est le pire des faux négatifs : celui qui invalide
un succès réel, et qui ferait abandonner un outil qui marchait.

D'où la règle : **la trace de l'effort est écrite avant de perdre la main.** Au tap sur
« appeler », la tentative existe déjà, en attente d'issue. Si le responsable ne revient jamais,
on sait au moins qu'il a essayé — et c'est déjà une information de soin.

`first_contact_at` est la métrique reine du pilote : le délai entre la détection et le premier
contact humain. Elle n'a de sens que si l'intention est enregistrée au départ.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app._shared.domain.entity import AggregateRoot


class ContactChannel(StrEnum):
    CALL = "call"
    WHATSAPP = "whatsapp"
    VISIT = "visit"
    OTHER = "other"


class ContactResult(StrEnum):
    """`PENDING` est l'état normal au départ, pas une anomalie."""

    PENDING = "pending"  # partie, issue inconnue — écrite avant de perdre la main
    REACHED = "reached"
    NOT_REACHED = "not_reached"
    POSTPONED = "postponed"  # « je rappelle plus tard » — ni un succès ni un échec


class ContactAttempt(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        signal_id: UUID,
        by_account_id: UUID,
        channel: ContactChannel,
        attempted_at: datetime,
        result: ContactResult = ContactResult.PENDING,
        answered_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.signal_id = signal_id
        self.by_account_id = by_account_id
        self.channel = channel
        self.attempted_at = attempted_at
        self.result = result
        self.answered_at = answered_at

    @property
    def awaits_answer(self) -> bool:
        return self.result is ContactResult.PENDING

    def resolve(self, *, result: ContactResult, at: datetime) -> None:
        """Le responsable revient dire ce qui s'est passé. Une seule fois — on n'insiste plus."""
        if self.result is not ContactResult.PENDING:
            return
        self.result = result
        self.answered_at = at


# Trois tentatives non abouties sur un régime d'échéance : la **péremption dure**. C'est la
# seconde et dernière exception à la fermeture humaine, et elle existe pour une raison de
# volume — sans elle, un module d'évangélisation qui fonctionne noie son propre inviteur en
# trois semaines. La personne reste en base ; elle sort de la file, pas du fichier.
HARD_EXPIRY_ATTEMPTS = 3
HARD_EXPIRY_DAYS = 30
