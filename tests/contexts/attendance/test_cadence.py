"""Fondation A (P1) — la cadence attendue : occurrences dérivées + les trois états d'occurrence.

Tests **purs** (aucune I/O) : la règle produit les bonnes occurrences, et le classement
saisie / acquittée / silencieuse respecte la précédence et la tolérance d'appariement.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.attendance.domain.cadence import (
    CadenceFrequency,
    GroupCadence,
    OccurrenceState,
    expected_occurrences,
    occurrence_state,
)


def _cadence(
    frequency: CadenceFrequency,
    anchor: datetime,
    *,
    active_from: datetime | None = None,
    active_until: datetime | None = None,
    day_of_month: int | None = None,
) -> GroupCadence:
    return GroupCadence(
        id=uuid4(),
        tenant_id=uuid4(),
        group_id=uuid4(),
        frequency=frequency,
        anchor_date=anchor,
        active_from=active_from or anchor,
        created_at=anchor,
        created_by_account_id=uuid4(),
        day_of_month=day_of_month,
        active_until=active_until,
    )


def test_weekly_occurrences_land_every_seven_days_within_window():
    anchor = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)  # un mercredi soir
    cad = _cadence(CadenceFrequency.WEEKLY, anchor)
    occ = expected_occurrences(cad, anchor, datetime(2026, 7, 29, tzinfo=UTC))
    assert occ == [
        datetime(2026, 7, 1, 19, 0, tzinfo=UTC),
        datetime(2026, 7, 8, 19, 0, tzinfo=UTC),
        datetime(2026, 7, 15, 19, 0, tzinfo=UTC),
        datetime(2026, 7, 22, 19, 0, tzinfo=UTC),
    ]


def test_biweekly_keeps_the_anchor_parity_when_window_starts_late():
    anchor = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    cad = _cadence(CadenceFrequency.BIWEEKLY, anchor)
    # fenêtre qui démarre après l'ancre : on garde la parité (15 et 29, pas 22)
    occ = expected_occurrences(
        cad, datetime(2026, 7, 10, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC)
    )
    assert occ == [
        datetime(2026, 7, 15, 19, 0, tzinfo=UTC),
        datetime(2026, 7, 29, 19, 0, tzinfo=UTC),
    ]


def test_monthly_occurrences_land_on_the_same_day_each_month():
    anchor = datetime(2026, 1, 5, 18, 30, tzinfo=UTC)
    cad = _cadence(CadenceFrequency.MONTHLY, anchor)
    occ = expected_occurrences(
        cad, datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 5, 31, tzinfo=UTC)
    )
    assert occ == [
        datetime(2026, 3, 5, 18, 30, tzinfo=UTC),
        datetime(2026, 4, 5, 18, 30, tzinfo=UTC),
        datetime(2026, 5, 5, 18, 30, tzinfo=UTC),
    ]


def test_active_until_clips_the_series():
    anchor = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    cad = _cadence(
        CadenceFrequency.WEEKLY, anchor, active_until=datetime(2026, 7, 16, tzinfo=UTC)
    )
    occ = expected_occurrences(cad, anchor, datetime(2026, 8, 1, tzinfo=UTC))
    assert occ == [
        datetime(2026, 7, 1, 19, 0, tzinfo=UTC),
        datetime(2026, 7, 8, 19, 0, tzinfo=UTC),
        datetime(2026, 7, 15, 19, 0, tzinfo=UTC),
    ]


def test_a_gathering_within_tolerance_makes_the_occurrence_saisie():
    occ = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    # rencontre tenue le lendemain (±3 j) → saisie
    state = occurrence_state(
        occ,
        gathering_dates=[occ + timedelta(days=1)],
        acknowledged_dates=[],
        suspensions=[],
    )
    assert state is OccurrenceState.SAISIE


def test_an_acknowledgement_makes_the_occurrence_acquittee():
    occ = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    state = occurrence_state(
        occ,
        gathering_dates=[],
        acknowledged_dates=[occ],
        suspensions=[],
    )
    assert state is OccurrenceState.ACQUITTEE


def test_a_suspension_period_makes_the_occurrence_acquittee():
    occ = datetime(2026, 12, 25, 19, 0, tzinfo=UTC)
    state = occurrence_state(
        occ,
        gathering_dates=[],
        acknowledged_dates=[],
        suspensions=[(datetime(2026, 12, 20, tzinfo=UTC), datetime(2027, 1, 5, tzinfo=UTC))],
    )
    assert state is OccurrenceState.ACQUITTEE


def test_nothing_at_all_makes_the_occurrence_silencieuse():
    occ = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    state = occurrence_state(
        occ,
        gathering_dates=[datetime(2026, 7, 20, tzinfo=UTC)],  # hors tolérance
        acknowledged_dates=[],
        suspensions=[],
    )
    assert state is OccurrenceState.SILENCIEUSE


def test_a_held_gathering_wins_over_an_overlapping_suspension():
    occ = datetime(2026, 12, 25, 19, 0, tzinfo=UTC)
    # la cellule s'est réunie malgré la suspension → la preuve l'emporte (SAISIE)
    state = occurrence_state(
        occ,
        gathering_dates=[occ],
        acknowledged_dates=[],
        suspensions=[(datetime(2026, 12, 20, tzinfo=UTC), datetime(2027, 1, 5, tzinfo=UTC))],
    )
    assert state is OccurrenceState.SAISIE
