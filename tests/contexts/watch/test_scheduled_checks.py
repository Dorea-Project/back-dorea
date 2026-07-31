"""Les échéances — la porte par laquelle le temps entre dans la veille.

Deux dangers, et ils sont opposés. Ne rien tirer : le moteur détecte et rien ne revient jamais
relancer. Tout tirer d'un coup après une panne de cron : le responsable ouvre l'application sur
cinquante lignes et n'ouvre plus rien du tout.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.fire_checks import FireDueChecks
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.self_declaration import (
    ON_DEMAND,
    RHYTHM_KIND,
    SelfDeclarationV1,
)
from app.contexts.watch.application.materialization import Materializer
from app.contexts.watch.application.my_cases import CloseCase
from app.contexts.watch.domain.effects import (
    CancelScheduledChecks,
    CasePriority,
    ExcludeForever,
    ExclusionCause,
    Extinguish,
    ExtinguishCause,
    ScheduleCheck,
)
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam
from app.contexts.watch.domain.registry import MISSION, default_registry
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeChecks,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
    case_acts_for,
)

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


def _fact(tenant, subject, *, at=_NOW) -> Fact:
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=at, recorded_at=at,
        source=MISSION, kind=FactKind.SELF_DECLARATION,
        subject_kind=SubjectKind.PERSON, subject_id=subject, payload={"kind": "prayer"},
    )


def _engine(checks, *, ledger=None, signals=None):
    interpreters = InterpreterRegistry()
    interpreters.register(SelfDeclarationV1())
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    return Intake(
        ledger or FakeLedger(), default_registry(), interpreters, store,
        signals or FakeSignals(), checks,
    )


# --- La matérialisation ------------------------------------------------------------------------


async def test_an_effect_becomes_a_dated_deadline():
    tenant, awa = uuid4(), uuid4()
    checks = FakeChecks()
    materializer = Materializer(
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()), FakeSignals(), checks
    )

    await materializer.apply(
        _fact(tenant, awa),
        [
            ScheduleCheck(
                subject_id=awa, reason="Rythme choisi : tous les 30 jours.",
                at=_NOW + timedelta(days=30), kind=RHYTHM_KIND,
            )
        ],
    )

    (check,) = checks.rows
    assert check["due_at"] == _NOW + timedelta(days=30)
    # La raison voyage : un rappel qu'on ne sait plus expliquer est un rappel qu'on ignore.
    assert "30 jours" in check["reason"]


async def test_replaying_the_same_fact_never_stacks_the_same_deadline():
    """Le ledger se rejoue. Une échéance en triple serait trois relances pour une décision."""
    tenant, awa = uuid4(), uuid4()
    checks = FakeChecks()
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    effect = ScheduleCheck(
        subject_id=awa, reason="…", at=_NOW + timedelta(days=30), kind=RHYTHM_KIND
    )

    for _ in range(3):
        await Materializer(store, FakeSignals(), checks).apply(_fact(tenant, awa), [effect])

    assert len(checks.rows) == 1


# --- L'annulation : la partie vitale -----------------------------------------------------------


async def test_a_permanent_withdrawal_cancels_everything_pending():
    """**L'échec le plus coûteux que ce produit puisse produire** est de relancer un défunt."""
    tenant, awa = uuid4(), uuid4()
    checks = FakeChecks()
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    materializer = Materializer(store, FakeSignals(), checks)
    await materializer.apply(
        _fact(tenant, awa),
        [ScheduleCheck(subject_id=awa, reason="…", at=_NOW, kind=RHYTHM_KIND)],
    )

    await materializer.apply(
        _fact(tenant, awa),
        [ExcludeForever(subject_id=awa, reason="décès", cause=ExclusionCause.DECEASED, at=_NOW)],
    )

    assert checks.rows[0]["cancelled_at"] == _NOW
    assert await checks.due(tenant_id=tenant, now=_NOW, limit=10) == []


async def test_a_return_cancels_only_the_return_deadline():
    """« On peut être présent et endeuillé » : le retour ferme son échéance, pas les autres."""
    tenant, awa = uuid4(), uuid4()
    checks = FakeChecks()
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    materializer = Materializer(store, FakeSignals(), checks)
    for kind in ("return", RHYTHM_KIND):
        await materializer.apply(
            _fact(tenant, awa),
            [ScheduleCheck(subject_id=awa, reason="…", at=_NOW, kind=kind)],
        )

    await materializer.apply(
        _fact(tenant, awa),
        [Extinguish(subject_id=awa, reason="revenue", cause=ExtinguishCause.RETURNED, at=_NOW)],
    )

    remaining = await checks.due(tenant_id=tenant, now=_NOW, limit=10)
    assert [c.kind for c in remaining] == [RHYTHM_KIND]


async def test_asking_to_be_left_alone_stops_the_reminders():
    """« Ne me relancez plus » — le membre reprend la main sur son propre rythme.

    Sans cette annulation, il recevrait exactement ce qu'il vient de demander d'arrêter."""
    tenant, awa = uuid4(), uuid4()
    checks = FakeChecks()
    intake = _engine(checks)
    await intake.submit(
        Fact(
            fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
            source=MISSION, kind=FactKind.SELF_DECLARATION,
            subject_kind=SubjectKind.PERSON, subject_id=awa,
            payload={"kind": "rhythm", "every_days": 30},
            consent=ConsentProof(given_by=awa, scope=ConsentScope.BE_WATCHED, given_at=_NOW),
        )
    )
    assert len(checks.rows) == 1

    await intake.submit(
        Fact(
            fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
            source=MISSION, kind=FactKind.SELF_DECLARATION,
            subject_kind=SubjectKind.PERSON, subject_id=awa,
            payload={"kind": "rhythm", "cadence": ON_DEMAND},
            consent=ConsentProof(given_by=awa, scope=ConsentScope.BE_WATCHED, given_at=_NOW),
        )
    )

    assert await checks.due(tenant_id=tenant, now=_NOW + timedelta(days=60), limit=10) == []


async def test_do_not_contact_cancels_the_deadlines_too():
    """La parole qu'on s'engage à respecter ne doit pas être démentie par une notification."""
    tenant, awa, jean = uuid4(), uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=awa, origin=CasePriority.ABSENCE,
        reason="…", opened_at=_NOW, status=SignalStatus.ASSIGNED, owner_account_id=jean,
    )
    signals.rows.append(case)
    await checks.schedule(
        subject_id=awa, tenant_id=tenant, kind=RHYTHM_KIND, reason="…",
        due_at=_NOW + timedelta(days=10), at=_NOW,
    )

    command = CloseCase(
        signals, case_acts_for(signals, clock=lambda: _NOW), checks, clock=lambda: _NOW
    )
    await command.execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
        outcome=SignalOutcome.DO_NOT_CONTACT,
    )

    assert checks.rows[0]["cancelled_at"] == _NOW


async def test_an_ordinary_closure_leaves_the_rhythm_alone():
    """Fermer un cas n'est pas dire « ne me contactez plus » — le rythme choisi survit."""
    tenant, awa, jean = uuid4(), uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=awa, origin=CasePriority.ABSENCE,
        reason="…", opened_at=_NOW, status=SignalStatus.ASSIGNED, owner_account_id=jean,
    )
    signals.rows.append(case)
    await checks.schedule(
        subject_id=awa, tenant_id=tenant, kind=RHYTHM_KIND, reason="…",
        due_at=_NOW + timedelta(days=10), at=_NOW,
    )

    command = CloseCase(
        signals, case_acts_for(signals, clock=lambda: _NOW), checks, clock=lambda: _NOW
    )
    await command.execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
        outcome=SignalOutcome.FOLLOWED,
    )

    assert checks.rows[0]["cancelled_at"] is None


# --- Le tirage, et le garde anti-orage ----------------------------------------------------------


async def test_a_due_deadline_enters_the_ledger_as_a_fact():
    """Le worker ne modifie **aucun** état : il écrit un fait, et la chaîne normale suit.

    C'est ce qui permet à un interpreter de ne jamais lire l'horloge — sans quoi rejouer demain
    donnerait autre chose qu'aujourd'hui."""
    tenant, awa = uuid4(), uuid4()
    checks, ledger = FakeChecks(), FakeLedger()
    await checks.schedule(
        subject_id=awa, tenant_id=tenant, kind=RHYTHM_KIND,
        reason="Rythme choisi : tous les 30 jours.",
        due_at=_NOW - timedelta(days=1), at=_NOW,
    )

    report = await FireDueChecks(
        checks, _engine(checks, ledger=ledger), _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant)

    assert report.fired == 1
    (written,) = ledger.rows
    assert written.kind is FactKind.CHECK_FIRED
    # La date de l'**échéance**, pas celle de la passe : une panne de cron de trois jours ne
    # décale pas l'histoire de trois jours.
    assert written.occurred_at == _NOW - timedelta(days=1)
    assert "30 jours" in written.payload["reason"]


async def test_the_storm_guard_spreads_a_cron_outage_instead_of_dumping_it():
    """Cinquante lignes d'un coup, et le responsable n'ouvre plus rien du tout.

    Rien n'est perdu : le reste **reste dû** et sortira à la passe suivante."""
    tenant = uuid4()
    checks, ledger = FakeChecks(), FakeLedger()
    for day in range(12):
        await checks.schedule(
            subject_id=uuid4(), tenant_id=tenant, kind=RHYTHM_KIND, reason="…",
            due_at=_NOW - timedelta(days=12 - day), at=_NOW,
        )
    fire = FireDueChecks(
        checks, _engine(checks, ledger=ledger), _Params(**{WatchParam.CHECK_BURST_CAP: 5}),
        clock=lambda: _NOW,
    )

    first = await fire.execute(tenant_id=tenant)

    assert first.fired == 5
    assert first.deferred == 7  # dites, jamais tues
    assert first.was_capped is True

    second = await fire.execute(tenant_id=tenant)
    assert second.fired == 5
    assert (await fire.execute(tenant_id=tenant)).fired == 2


async def test_the_oldest_deadlines_come_out_first():
    """Après une panne, on rattrape dans l'ordre où les échéances sont tombées."""
    tenant = uuid4()
    checks, ledger = FakeChecks(), FakeLedger()
    dates = [_NOW - timedelta(days=d) for d in (1, 9, 5)]
    for due in dates:
        await checks.schedule(
            subject_id=uuid4(), tenant_id=tenant, kind=RHYTHM_KIND, reason="…",
            due_at=due, at=_NOW,
        )

    await FireDueChecks(
        checks, _engine(checks, ledger=ledger), _Params(**{WatchParam.CHECK_BURST_CAP: 2}),
        clock=lambda: _NOW,
    ).execute(tenant_id=tenant)

    assert [f.occurred_at for f in ledger.rows] == sorted(dates)[:2]


async def test_a_deadline_never_fires_twice():
    tenant, awa = uuid4(), uuid4()
    checks, ledger = FakeChecks(), FakeLedger()
    await checks.schedule(
        subject_id=awa, tenant_id=tenant, kind=RHYTHM_KIND, reason="…",
        due_at=_NOW - timedelta(days=1), at=_NOW,
    )
    fire = FireDueChecks(checks, _engine(checks, ledger=ledger), _Params(), clock=lambda: _NOW)

    await fire.execute(tenant_id=tenant)
    second = await fire.execute(tenant_id=tenant)

    assert second.fired == 0
    assert len(ledger.rows) == 1


async def test_a_future_deadline_stays_put():
    tenant, awa = uuid4(), uuid4()
    checks = FakeChecks()
    await checks.schedule(
        subject_id=awa, tenant_id=tenant, kind=RHYTHM_KIND, reason="…",
        due_at=_NOW + timedelta(days=10), at=_NOW,
    )

    report = await FireDueChecks(
        checks, _engine(checks), _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant)

    assert report.fired == 0 and report.deferred == 0


def test_cancelling_everything_is_expressible():
    """`kind=None` existe pour le retrait définitif : tout, sans avoir à énumérer les types."""
    effect = CancelScheduledChecks(subject_id=uuid4(), reason="décès")
    assert effect.kind is None
