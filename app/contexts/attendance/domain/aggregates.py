"""Agrégats du contexte Présence (M6) : `Gathering` et `AttendanceRecord`.

Le roster attendu **n'est pas stocké** (dérivé des membres du groupe) ; on ne persiste que
les **signaux** (présents / excusés). L'absence est déduite (M6 §3).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.attendance.domain.enums import (
    AttendanceMark,
    AttendanceSource,
    GatheringStatus,
    GatheringType,
)


class Gathering(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        group_id: UUID | None,
        type: GatheringType,
        title: str | None,
        scheduled_at: datetime,
        status: GatheringStatus,
        created_by_account_id: UUID,
        created_at: datetime,
        check_in_code: str | None = None,
        closed_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.group_id = group_id  # None = rencontre église-entière (culte) — M6-0 : groupe requis
        self.type = type
        self.title = title
        self.scheduled_at = scheduled_at
        self.status = status
        self.created_by_account_id = created_by_account_id
        self.created_at = created_at
        # Code de séance affiché par le responsable ; les membres s'auto-marquent avec (M6-1).
        self.check_in_code = check_in_code
        self.closed_at = closed_at

    @property
    def is_open(self) -> bool:
        return self.status is GatheringStatus.OPEN

    def close(self, *, now: datetime) -> None:
        self.status = GatheringStatus.CLOSED
        self.closed_at = now


class AttendanceRecord(AggregateRoot):
    """Un signal de présence (un par personne et par rencontre)."""

    def __init__(
        self,
        *,
        id: UUID,
        gathering_id: UUID,
        account_id: UUID,
        mark: AttendanceMark,
        source: AttendanceSource,
        recorded_at: datetime,
        recorded_by_account_id: UUID,
        reason: str | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.gathering_id = gathering_id
        self.account_id = account_id
        self.mark = mark
        self.source = source
        self.recorded_at = recorded_at
        self.recorded_by_account_id = recorded_by_account_id
        self.reason = reason  # motif d'excuse (M6-2)
