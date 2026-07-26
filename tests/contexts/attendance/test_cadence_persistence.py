"""Fondation A (P1) — commandes de cadence + calcul de couverture (fakes in-memory).

Valide la logique applicative : déclaration (validation + unicité), acquittement idempotent,
suspension, et le comptage saisie / acquittée / silencieuse de `GetGroupCoverage`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.contexts.attendance.application.commands.manage_cadence import (
    AcknowledgeOccurrence,
    DeclareCadence,
    SuspendChurch,
)
from app.contexts.attendance.application.queries.get_group_coverage import GetGroupCoverage
from app.contexts.attendance.domain.cadence import (
    AcknowledgementReason,
    CadenceAcknowledgement,
    CadenceFrequency,
    ChurchSuspension,
    GroupCadence,
    SuspensionReason,
)
from app.contexts.attendance.domain.errors import (
    CadenceAlreadyExistsError,
    InvalidCadenceError,
    InvalidSuspensionPeriodError,
)
from app.contexts.attendance.domain.repositories import (
    CadenceAcknowledgementRepository,
    ChurchSuspensionRepository,
    GatheringRepository,
    GroupCadenceRepository,
)

_NOW = datetime(2026, 7, 25, tzinfo=UTC)


class _FakeCadences(GroupCadenceRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, GroupCadence] = {}

    async def add(self, cadence: GroupCadence) -> None:
        self._by_id[cadence.id] = cadence

    async def get_active_by_group(self, group_id):
        for c in self._by_id.values():
            if c.group_id == group_id and c.is_active:
                return c
        return None

    async def save(self, cadence: GroupCadence) -> None:
        self._by_id[cadence.id] = cadence


class _FakeAcks(CadenceAcknowledgementRepository):
    def __init__(self) -> None:
        self._items: list[CadenceAcknowledgement] = []

    async def add(self, ack: CadenceAcknowledgement) -> None:
        self._items.append(ack)

    async def get_for(self, group_id, occurrence_date):
        for a in self._items:
            if a.group_id == group_id and a.occurrence_date == occurrence_date:
                return a
        return None

    async def list_by_group(self, group_id):
        return [a for a in self._items if a.group_id == group_id]


class _FakeSuspensions(ChurchSuspensionRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, ChurchSuspension] = {}

    async def add(self, suspension: ChurchSuspension) -> None:
        self._by_id[suspension.id] = suspension

    async def get(self, suspension_id):
        return self._by_id.get(suspension_id)

    async def save(self, suspension: ChurchSuspension) -> None:
        self._by_id[suspension.id] = suspension

    async def list_active_by_tenant(self, tenant_id):
        return [s for s in self._by_id.values() if s.tenant_id == tenant_id and s.is_active]


@dataclass
class _StubGathering:
    group_id: UUID
    scheduled_at: datetime


class _FakeGatherings(GatheringRepository):
    def __init__(self, gatherings=()) -> None:
        self._items = list(gatherings)

    async def add(self, gathering) -> None: ...

    async def get(self, gathering_id): ...

    async def get_open_by_check_in_code(self, code): ...

    async def list_by_group(self, group_id):
        return [g for g in self._items if g.group_id == group_id]

    async def save(self, gathering) -> None: ...


async def test_declare_cadence_creates_a_weekly_rhythm():
    tenant, group, leader = uuid4(), uuid4(), uuid4()
    cadences = _FakeCadences()
    anchor = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    dto = await DeclareCadence(cadences, clock=lambda: _NOW).execute(
        actor_account_id=leader,
        tenant_id=tenant,
        group_id=group,
        frequency=CadenceFrequency.WEEKLY,
        anchor_date=anchor,
        active_from=anchor,
        weekday=2,
    )
    assert dto.frequency == "weekly" and dto.weekday == 2
    assert (await cadences.get_active_by_group(group)) is not None


async def test_declare_cadence_rejects_a_second_active_cadence():
    tenant, group, leader = uuid4(), uuid4(), uuid4()
    cadences = _FakeCadences()
    anchor = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    cmd = DeclareCadence(cadences, clock=lambda: _NOW)
    await cmd.execute(
        actor_account_id=leader,
        tenant_id=tenant,
        group_id=group,
        frequency=CadenceFrequency.WEEKLY,
        anchor_date=anchor,
        active_from=anchor,
        weekday=2,
    )
    with pytest.raises(CadenceAlreadyExistsError):
        await cmd.execute(
            actor_account_id=leader,
            tenant_id=tenant,
            group_id=group,
            frequency=CadenceFrequency.WEEKLY,
            anchor_date=anchor,
            active_from=anchor,
            weekday=2,
        )


async def test_weekly_cadence_requires_a_weekday():
    cadences = _FakeCadences()
    anchor = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    with pytest.raises(InvalidCadenceError):
        await DeclareCadence(cadences, clock=lambda: _NOW).execute(
            actor_account_id=uuid4(),
            tenant_id=uuid4(),
            group_id=uuid4(),
            frequency=CadenceFrequency.WEEKLY,
            anchor_date=anchor,
            active_from=anchor,
        )


async def test_monthly_cadence_requires_a_valid_day_of_month():
    cadences = _FakeCadences()
    anchor = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    with pytest.raises(InvalidCadenceError):
        await DeclareCadence(cadences, clock=lambda: _NOW).execute(
            actor_account_id=uuid4(),
            tenant_id=uuid4(),
            group_id=uuid4(),
            frequency=CadenceFrequency.MONTHLY,
            anchor_date=anchor,
            active_from=anchor,
            day_of_month=31,  # hors 1-28
        )


async def test_acknowledging_the_same_occurrence_twice_is_idempotent():
    tenant, group, leader = uuid4(), uuid4(), uuid4()
    acks = _FakeAcks()
    occ = datetime(2026, 7, 15, 19, 0, tzinfo=UTC)
    cmd = AcknowledgeOccurrence(acks, clock=lambda: _NOW)
    first = await cmd.execute(
        actor_account_id=leader,
        tenant_id=tenant,
        group_id=group,
        occurrence_date=occ,
        reason=AcknowledgementReason.HOLIDAY,
    )
    second = await cmd.execute(
        actor_account_id=leader,
        tenant_id=tenant,
        group_id=group,
        occurrence_date=occ,
        reason=AcknowledgementReason.LEADER_ABSENT,  # ignoré : l'existant est renvoyé
    )
    assert first.id == second.id
    assert len(await acks.list_by_group(group)) == 1


async def test_suspend_church_rejects_an_inverted_period():
    with pytest.raises(InvalidSuspensionPeriodError):
        await SuspendChurch(_FakeSuspensions(), clock=lambda: _NOW).execute(
            actor_account_id=uuid4(),
            tenant_id=uuid4(),
            reason=SuspensionReason.HOLIDAY,
            from_date=datetime(2026, 12, 25, tzinfo=UTC),
            to_date=datetime(2026, 12, 20, tzinfo=UTC),
        )


async def test_coverage_without_a_cadence_is_blind():
    dto = await GetGroupCoverage(
        _FakeCadences(), _FakeGatherings(), _FakeAcks(), _FakeSuspensions()
    ).execute(
        tenant_id=uuid4(),
        group_id=uuid4(),
        from_date=datetime(2026, 7, 1, tzinfo=UTC),
        to_date=datetime(2026, 7, 29, tzinfo=UTC),
    )
    assert dto.has_cadence is False and dto.expected_count == 0


async def test_coverage_counts_the_three_states():
    tenant, group, leader = uuid4(), uuid4(), uuid4()
    anchor = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)  # occurrences: 1, 8, 15, 22 juillet
    cadences = _FakeCadences()
    await DeclareCadence(cadences, clock=lambda: _NOW).execute(
        actor_account_id=leader,
        tenant_id=tenant,
        group_id=group,
        frequency=CadenceFrequency.WEEKLY,
        anchor_date=anchor,
        active_from=anchor,
        weekday=2,
    )
    # une rencontre tenue le 8 (saisie) ; le 15 acquitté ; 1 et 22 → silencieuses
    gatherings = _FakeGatherings([_StubGathering(group, datetime(2026, 7, 8, 19, 0, tzinfo=UTC))])
    acks = _FakeAcks()
    await AcknowledgeOccurrence(acks, clock=lambda: _NOW).execute(
        actor_account_id=leader,
        tenant_id=tenant,
        group_id=group,
        occurrence_date=datetime(2026, 7, 15, 19, 0, tzinfo=UTC),
        reason=AcknowledgementReason.HOLIDAY,
    )

    dto = await GetGroupCoverage(cadences, gatherings, acks, _FakeSuspensions()).execute(
        tenant_id=tenant,
        group_id=group,
        from_date=datetime(2026, 7, 1, tzinfo=UTC),
        to_date=datetime(2026, 7, 29, tzinfo=UTC),
    )
    assert dto.has_cadence is True
    assert dto.expected_count == 4
    assert dto.saisie_count == 1
    assert dto.acquittee_count == 1
    assert dto.silencieuse_count == 2
