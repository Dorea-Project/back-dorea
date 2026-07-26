"""Disponibilité récurrente d'un pasteur + moteur de créneaux (module Rendez-vous).

Une `AvailabilityRule` dit « ce pasteur reçoit tel **jour de la semaine**, de telle heure à telle
heure, par créneaux de N minutes ». Elle **engendre** des créneaux concrets sur une plage de dates.
Les heures sont exprimées en **minutes depuis minuit, en UTC** (localisation par fuseau plus tard).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.appointments.domain.errors import InvalidAvailabilityError

_MINUTES_IN_DAY = 24 * 60


@dataclass(frozen=True)
class Slot:
    """Un créneau concret réservable, engendré depuis une règle."""

    pastor_account_id: UUID
    starts_at: datetime
    ends_at: datetime


class AvailabilityRule(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        pastor_account_id: UUID,
        weekday: int,  # 0 = lundi … 6 = dimanche (convention `date.weekday()`)
        start_minute: int,  # minutes depuis minuit (UTC)
        end_minute: int,
        slot_minutes: int,
        active: bool,
        created_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.pastor_account_id = pastor_account_id
        self.weekday = weekday
        self.start_minute = start_minute
        self.end_minute = end_minute
        self.slot_minutes = slot_minutes
        self.active = active
        self.created_at = created_at

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        pastor_account_id: UUID,
        weekday: int,
        start_minute: int,
        end_minute: int,
        slot_minutes: int,
        now: datetime,
    ) -> AvailabilityRule:
        if not 0 <= weekday <= 6:
            raise InvalidAvailabilityError("Le jour doit être entre 0 (lundi) et 6 (dimanche).")
        if not (0 <= start_minute < end_minute <= _MINUTES_IN_DAY):
            raise InvalidAvailabilityError("La fenêtre horaire est incohérente.")
        if slot_minutes <= 0 or slot_minutes > (end_minute - start_minute):
            raise InvalidAvailabilityError("La durée de créneau ne tient pas dans la fenêtre.")
        return cls(
            id=id,
            tenant_id=tenant_id,
            pastor_account_id=pastor_account_id,
            weekday=weekday,
            start_minute=start_minute,
            end_minute=end_minute,
            slot_minutes=slot_minutes,
            active=True,
            created_at=now,
        )

    def deactivate(self) -> None:
        self.active = False

    def generate(self, *, from_date: date, to_date: date) -> list[Slot]:
        """Les créneaux concrets de cette règle entre deux dates (bornes incluses)."""
        slots: list[Slot] = []
        day = from_date
        while day <= to_date:
            if day.weekday() == self.weekday:
                minute = self.start_minute
                while minute + self.slot_minutes <= self.end_minute:
                    start = datetime.combine(day, time(minute // 60, minute % 60), tzinfo=UTC)
                    slots.append(
                        Slot(
                            pastor_account_id=self.pastor_account_id,
                            starts_at=start,
                            ends_at=start + timedelta(minutes=self.slot_minutes),
                        )
                    )
                    minute += self.slot_minutes
            day += timedelta(days=1)
        return slots
