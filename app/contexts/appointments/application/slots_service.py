"""Composition des créneaux **ouverts** — engendrés des règles, moins les pris et le passé.

Logique partagée par la requête (voir l'offre) et la réservation (valider un créneau) : un créneau
est ouvert s'il est **futur** et qu'**aucun RDV confirmé** n'occupe déjà `(pasteur, heure)`.
"""

from __future__ import annotations

from datetime import date, datetime

from app.contexts.appointments.domain.aggregates import Appointment
from app.contexts.appointments.domain.availability import AvailabilityRule, Slot


def open_slots_from(
    rules: list[AvailabilityRule],
    booked: list[Appointment],
    *,
    from_date: date,
    to_date: date,
    now: datetime,
) -> list[Slot]:
    taken = {
        (a.with_pastor_account_id, a.scheduled_at)
        for a in booked
        if a.with_pastor_account_id is not None and a.scheduled_at is not None
    }
    out: list[Slot] = []
    for rule in rules:
        for slot in rule.generate(from_date=from_date, to_date=to_date):
            if slot.starts_at > now and (slot.pastor_account_id, slot.starts_at) not in taken:
                out.append(slot)
    out.sort(key=lambda s: (s.starts_at, str(s.pastor_account_id)))
    return out
