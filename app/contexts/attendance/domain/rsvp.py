"""Agrégat `GatheringRsvp` — « je viens » à une rencontre (M6, alimenté par M8).

Un **pré-signal** de présence, distinct du présent (venu pour de vrai) et de l'excusé (a prévenu
qu'il ne vient pas) : une *prédiction*. Il pré-remplit le roster (« qui a dit venir »). Posé
surtout par le « je viens » d'une annonce *convoquer* liée à la rencontre. Une ligne par (rencontre,
compte) ; se rétracter la supprime.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot


class GatheringRsvp(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        gathering_id: UUID,
        account_id: UUID,
        rsvp_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.gathering_id = gathering_id
        self.account_id = account_id
        self.rsvp_at = rsvp_at
