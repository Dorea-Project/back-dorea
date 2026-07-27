"""L'**indisponibilité déclarée** d'un pasteur — à ne pas confondre avec ses créneaux.

`AvailabilityRule` dit *quand il reçoit*. Ceci dit *quand il n'est pas là*. Ce sont deux
mécanismes distincts, et les confondre coûte cher :

| | Nature | Traitement |
|---|---|---|
| **Absence** | Prévisible, déclarée | Consultée **avant** l'assignation. Zéro attente |
| **Oubli** | Constaté après coup | Relais après délai |

Sans cette distinction, un pasteur en voyage trois semaines ferait attendre **chaque** demande
le délai de relais complet avant d'être contourné — alors qu'on savait dès le premier jour qu'il
ne répondrait pas. C'est la même idée que la neutralisation d'un membre, appliquée à la
disponibilité d'un acteur : le silence a une explication, et on la connaît d'avance.

Le motif est court et **jamais exigé** : un pasteur n'a pas à justifier son absence pour que le
système sache l'anticiper.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot


class PastorUnavailability(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        pastor_account_id: UUID,
        unavailable_from: datetime,
        unavailable_until: datetime,
        declared_by_account_id: UUID,
        declared_at: datetime,
        reason: str | None = None,
        canceled_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.pastor_account_id = pastor_account_id
        self.unavailable_from = unavailable_from
        self.unavailable_until = unavailable_until
        self.declared_by_account_id = declared_by_account_id
        self.declared_at = declared_at
        self.reason = reason
        self.canceled_at = canceled_at

    @property
    def is_active(self) -> bool:
        return self.canceled_at is None

    def covers(self, moment: datetime) -> bool:
        return self.is_active and self.unavailable_from <= moment <= self.unavailable_until

    def cancel(self, *, now: datetime) -> None:
        if self.canceled_at is None:
            self.canceled_at = now


def is_available(
    unavailabilities: list[PastorUnavailability], moment: datetime
) -> bool:
    """Fonction **pure** : ce pasteur peut-il recevoir à ce moment-là ?"""
    return not any(u.covers(moment) for u in unavailabilities)
