"""Les deux moitiés de « celui qu'on n'a jamais vu ».

Jusqu'ici, **seule une présence armait le regard**. Deux personnes échappaient donc entièrement au
moteur, et ce sont précisément celles qu'il fallait voir :

- le **nouveau inscrit qu'on ne revoit jamais** — pas de première présence, donc pas d'échéance,
  donc aucun regard. Son silence ne succède à rien, et c'est le plus difficile à entendre ;
- le membre d'un **groupe qui ne saisit aucune rencontre** — il n'y a rien à manquer, donc personne
  n'est jamais absent, et l'écran vide de ce groupe ressemble à la santé.

Les deux réponses sont volontairement différentes. L'adhésion **arme un regard sur la personne** ;
le groupe aveugle est un **défaut de dispositif**, consigné sur le groupe et jamais sur ses
membres — accuser quelqu'un d'un silence qui est le nôtre serait l'erreur exactement inverse.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.attendance.domain.cadence import CadenceFrequency, GroupCadence
from app.contexts.groups.application.watch_facts import EmitJoinedGroupFact, fact_id_for
from app.contexts.watch.application.blind_groups import (
    DetectBlindGroups,
    GroupWatchRhythm,
    RhythmlessGroup,
)
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.absence_watch import ABSENCE_WATCH_KIND
from app.contexts.watch.application.interpreters.joined_group import JoinedGroupV1
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import CoverageGap, CoverageScope
from app.contexts.watch.domain.facts import FactKind
from app.contexts.watch.domain.parameters import DEFAULTS
from app.contexts.watch.domain.registry import GROUPS, default_registry
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeChecks,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 8, 3, tzinfo=UTC)
_WEEK = timedelta(days=7)


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


class _Rhythm:
    def __init__(self, *, cadence=True):
        self._cadence = cadence

    async def next_check_at(self, *, group_id, tenant_id, since):
        return since + _WEEK * 3 + timedelta(days=2) if self._cadence else None


class _Gaps:
    """Le magasin des défauts, avec sa déduplication — un rappel nocturne devient du bruit."""

    def __init__(self):
        self.rows: list[CoverageGapRecord] = []

    async def record_once(self, record):
        already = any(
            r.tenant_id == record.tenant_id
            and r.gap is record.gap
            and r.subject_id == record.subject_id
            and r.resolved_at is None
            for r in self.rows
        )
        if already:
            return False
        self.rows.append(record)
        return True

    async def open_gaps(self, tenant_id):
        return [r for r in self.rows if r.tenant_id == tenant_id]


class _Rhythms:
    def __init__(self, groups):
        self._groups = groups

    async def watched_groups(self, *, tenant_id):
        return self._groups


def _cadence(*, group_id, tenant, active_from):
    return GroupCadence(
        id=uuid4(), tenant_id=tenant, group_id=group_id,
        frequency=CadenceFrequency.WEEKLY, weekday=0, day_of_month=None,
        anchor_date=active_from, active_from=active_from, active_until=None,
        created_at=active_from, created_by_account_id=uuid4(),
    )


def _engine(checks, *, ledger=None, signals=None):
    interpreters = InterpreterRegistry()
    interpreters.register(JoinedGroupV1())
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    return Intake(
        ledger or FakeLedger(), default_registry(), interpreters, store,
        signals or FakeSignals(), checks,
    )


# --- L'adhésion arme le regard -----------------------------------------------------------


async def test_joining_a_group_arms_the_watch_for_someone_never_seen():
    """Le nouveau inscrit est regardé **avant** d'être venu une seule fois."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, signals, ledger = FakeChecks(), FakeSignals(), FakeLedger()
    intake = _engine(checks, ledger=ledger, signals=signals)

    await EmitJoinedGroupFact(intake, _Rhythm()).execute(
        account_id=member, tenant_id=tenant, group_id=group,
        joined_at=_NOW, recorded_at=_NOW,
    )

    (fact,) = ledger.rows
    assert fact.kind is FactKind.JOINED_GROUP
    (armed,) = checks.rows
    assert armed["kind"] == ABSENCE_WATCH_KIND
    assert armed["due_at"] == _NOW + _WEEK * 3 + timedelta(days=2)
    assert armed["payload"]["since"] == _NOW.isoformat()
    # Arriver dans un groupe n'est pas un motif de soin : c'est le moment où l'on commence à
    # attendre quelqu'un.
    assert signals.rows == []


async def test_joining_a_group_without_a_cadence_arms_nothing_but_is_still_written():
    """Sans rythme attendu, il n'y a rien à manquer — on n'arme pas sur une intuition.

    **Mais le fait entre au journal.** Il n'y entrait pas, et la conséquence était silencieuse :
    quelqu'un inscrit dans une cellule sans rythme déclaré n'existait nulle part. Le jour où la
    cellule déclarait enfin son rythme, un rejeu ne trouvait rien à rejouer — la personne restait
    invisible pour toujours, sauf à venir d'elle-même. C'est-à-dire exactement la population que
    ce fait a été créé pour couvrir : *celui qu'on n'a jamais vu*.

    La règle du moteur vaut ici comme ailleurs : un fait garde son sens jusqu'à ce qu'on sache
    l'écrire. Une source dit ce qui a eu lieu ; elle ne jette rien parce qu'un détail d'aval
    manque."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, ledger = FakeChecks(), FakeLedger()
    intake = _engine(checks, ledger=ledger)

    emitted = await EmitJoinedGroupFact(intake, _Rhythm(cadence=False)).execute(
        account_id=member, tenant_id=tenant, group_id=group,
        joined_at=_NOW, recorded_at=_NOW,
    )

    assert emitted is True
    assert len(ledger.rows) == 1
    assert "check_absence_at" not in ledger.rows[0].payload  # rien à armer, et on le dit
    assert checks.rows == []


async def test_rejoining_the_same_group_does_not_stack_a_second_watch():
    """`fact_id` est dérivé de (groupe, personne) : le rejeu n'empile pas."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, ledger = FakeChecks(), FakeLedger()
    intake = _engine(checks, ledger=ledger)
    emit = EmitJoinedGroupFact(intake, _Rhythm())

    await emit.execute(
        account_id=member, tenant_id=tenant, group_id=group,
        joined_at=_NOW, recorded_at=_NOW,
    )
    await emit.execute(
        account_id=member, tenant_id=tenant, group_id=group,
        joined_at=_NOW + _WEEK, recorded_at=_NOW + _WEEK,
    )

    assert len(ledger.rows) == 1
    assert ledger.rows[0].fact_id == fact_id_for(group, member)
    assert len([c for c in checks.rows if c["cancelled_at"] is None]) == 1


def test_the_source_can_only_say_that_someone_joined():
    """Les Groupes n'ont qu'une chose à dire au moteur — pas une présence, pas une inquiétude."""
    registry = default_registry()
    assert registry.accepts(GROUPS, FactKind.JOINED_GROUP) is True
    assert registry.accepts(GROUPS, FactKind.PRESENCE_RECORDED) is False
    assert registry.accepts(GROUPS, FactKind.THIRD_PARTY_CONCERN) is False


# --- Le groupe aveugle est un défaut de dispositif ---------------------------------------


def _detect(groups, **params):
    gaps = _Gaps()
    return (
        DetectBlindGroups(
            _Rhythms(groups), gaps, _Params(**params), clock=lambda: _NOW, id_factory=uuid4
        ),
        gaps,
    )


async def test_a_group_that_never_recorded_a_gathering_is_reported():
    tenant, group = uuid4(), uuid4()
    rhythm = GroupWatchRhythm(
        group_id=group, label="la cellule Bethel",
        cadence=_cadence(group_id=group, tenant=tenant, active_from=_NOW - _WEEK * 6),
        last_gathering_at=None,
    )
    detect, gaps = _detect([rhythm])

    report = await detect.execute(tenant_id=tenant)

    assert report.detected == 1 and report.recorded == 1
    (gap,) = gaps.rows
    # Sur le **groupe**, jamais sur une personne : la faute n'est à personne en particulier.
    assert gap.scope is CoverageScope.GROUP
    assert gap.subject_id == group
    assert gap.gap is CoverageGap.BLIND
    assert "jamais été saisie" in gap.reason
    assert "la cellule Bethel" in gap.reason


async def test_a_group_that_records_its_gatherings_is_not_reported():
    tenant, group = uuid4(), uuid4()
    rhythm = GroupWatchRhythm(
        group_id=group, label="la cellule Bethel",
        cadence=_cadence(group_id=group, tenant=tenant, active_from=_NOW - _WEEK * 10),
        last_gathering_at=_NOW - _WEEK,
    )
    detect, gaps = _detect([rhythm])

    report = await detect.execute(tenant_id=tenant)

    assert report.detected == 0
    assert gaps.rows == []


async def test_the_threshold_is_in_occurrences_so_a_monthly_group_is_not_accused():
    """Six semaines sans rencontre : normal pour un groupe mensuel, anormal pour une cellule.

    C'est le rythme du groupe qui donne son sens au temps qui passe — un seuil en jours punirait
    exactement les groupes qui se réunissent rarement, et qui n'ont rien fait de mal."""
    tenant, weekly, monthly = uuid4(), uuid4(), uuid4()
    six_weeks_ago = _NOW - _WEEK * 6
    weekly_cadence = _cadence(group_id=weekly, tenant=tenant, active_from=_NOW - _WEEK * 20)
    monthly_cadence = GroupCadence(
        id=uuid4(), tenant_id=tenant, group_id=monthly,
        frequency=CadenceFrequency.MONTHLY, weekday=None, day_of_month=5,
        anchor_date=_NOW - _WEEK * 20, active_from=_NOW - _WEEK * 20, active_until=None,
        created_at=_NOW - _WEEK * 20, created_by_account_id=uuid4(),
    )
    detect, gaps = _detect(
        [
            GroupWatchRhythm(
                group_id=weekly, label="la cellule", cadence=weekly_cadence,
                last_gathering_at=six_weeks_ago,
            ),
            GroupWatchRhythm(
                group_id=monthly, label="la commission", cadence=monthly_cadence,
                last_gathering_at=six_weeks_ago,
            ),
        ]
    )

    await detect.execute(tenant_id=tenant)

    reported = {gap.subject_id for gap in gaps.rows}
    assert weekly in reported
    assert monthly not in reported


async def test_a_coverage_signal_is_finally_written_somewhere():
    """`CoverageSignal` attendait son écran depuis le premier jour — et retombait en « différé ».

    Un défaut de dispositif consigné nulle part n'existe pour personne : l'église mal configurée
    resterait silencieuse, son écran vide disant « tout va bien » alors qu'il dit « personne n'est
    là pour voir »."""
    from app.contexts.watch.application.materialization import Materializer
    from app.contexts.watch.domain.effects import CoverageSignal
    from app.contexts.watch.domain.facts import Fact, SubjectKind
    from app.contexts.watch.domain.registry import ATTENDANCE

    tenant, member = uuid4(), uuid4()
    gaps = _Gaps()
    materializer = Materializer(
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        FakeSignals(), FakeChecks(), gaps,
    )
    fact = Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=ATTENDANCE, kind=FactKind.PRESENCE_RECORDED,
        subject_kind=SubjectKind.PERSON, subject_id=member, payload={},
    )

    result = await materializer.apply(
        fact,
        [
            CoverageSignal(
                subject_id=member,
                reason="Personne ne connaît cette personne.",
                gap=CoverageGap.NO_REFERENT,
                at=_NOW,
            )
        ],
    )

    assert result.deferred == ()  # plus rien ne se perd en silence
    (gap,) = gaps.rows
    assert gap.gap is CoverageGap.NO_REFERENT
    assert gap.scope is CoverageScope.PERSON
    assert gap.subject_id == member


async def test_the_defect_is_not_repeated_every_night():
    """Un rappel qui revient chaque nuit devient du bruit, et le bruit se désapprend."""
    tenant, group = uuid4(), uuid4()
    rhythm = GroupWatchRhythm(
        group_id=group, label="la cellule Bethel",
        cadence=_cadence(group_id=group, tenant=tenant, active_from=_NOW - _WEEK * 6),
        last_gathering_at=None,
    )
    detect, gaps = _detect([rhythm])

    first = await detect.execute(tenant_id=tenant)
    second = await detect.execute(tenant_id=tenant)

    assert first.recorded == 1
    assert second.detected == 1 and second.recorded == 0  # détecté encore, consigné une fois
    assert len(gaps.rows) == 1


# --- Le groupe sans rythme : un cran avant l'aveugle -------------------------------------
#
# Un groupe aveugle a au moins dit **quand** il se réunit : le moteur sait qu'il devrait voir
# quelque chose, et son silence est lisible. Un groupe sans cadence n'attend personne à aucune
# date — aucune détection ne s'y arme jamais, personne n'y manque jamais.
#
# Il échappait aux deux filets à la fois : l'adhésion n'armait rien *et ne journalisait rien*, et
# la détection des aveugles part des cadences, donc ne pouvait pas le voir. Son écran vide
# ressemblait à la santé : la faute exacte que `BLIND` existe pour empêcher, un étage plus haut.


class _RhythmsWithout:
    """Un adaptateur qui connaît les deux questions : les groupes suivis, et ceux sans rythme."""

    def __init__(self, watched=(), rhythmless=()):
        self._watched = list(watched)
        self._rhythmless = list(rhythmless)

    async def watched_groups(self, *, tenant_id):
        return list(self._watched)

    async def groups_without_rhythm(self, *, tenant_id):
        return list(self._rhythmless)


async def test_a_group_with_members_and_no_rhythm_is_a_coverage_gap():
    """Le défaut porte sur le **groupe**, comme `BLIND` : ce n'est pas une personne qui manque,
    c'est le regard qui n'existe pas."""
    tenant = uuid4()
    gaps = _Gaps()
    rhythms = _RhythmsWithout(
        rhythmless=[RhythmlessGroup(group_id=uuid4(), label="la cellule Bethel", member_count=12)]
    )

    result = await DetectBlindGroups(rhythms, gaps, _Params(), clock=lambda: _NOW).execute(
        tenant_id=tenant
    )

    assert result.rhythmless == 1
    (record,) = gaps.rows
    assert record.gap is CoverageGap.NO_RHYTHM
    assert record.scope is CoverageScope.GROUP
    assert "la cellule Bethel" in record.reason
    assert "12 membres" in record.reason


async def test_an_empty_group_is_not_reproached_for_having_no_rhythm():
    """Un groupe fraîchement créé et encore vide n'a rien à déclarer.

    Le signaler ferait du défaut de couverture un reproche de démarrage — et le bruit se
    désapprend en trois semaines."""
    gaps = _Gaps()
    # L'adaptateur ne rend que les groupes **avec des membres** : c'est sa requête qui filtre.
    rhythms = _RhythmsWithout(rhythmless=[])

    result = await DetectBlindGroups(rhythms, gaps, _Params(), clock=lambda: _NOW).execute(
        tenant_id=uuid4()
    )

    assert result.rhythmless == 0
    assert gaps.rows == []


async def test_the_same_rhythmless_group_is_not_recorded_twice():
    """Un rappel qui revient chaque nuit devient du bruit."""
    tenant = uuid4()
    gaps = _Gaps()
    rhythms = _RhythmsWithout(
        rhythmless=[RhythmlessGroup(group_id=uuid4(), label="Bethel", member_count=4)]
    )
    detect = DetectBlindGroups(rhythms, gaps, _Params(), clock=lambda: _NOW)

    await detect.execute(tenant_id=tenant)
    second = await detect.execute(tenant_id=tenant)

    assert second.rhythmless == 0
    assert len(gaps.rows) == 1


async def test_the_two_gaps_are_distinct_because_the_action_is_not_the_same():
    """« Faites saisir vos rencontres » et « dites quand vous vous réunissez » ne sont pas la
    même demande. Les confondre laisserait le pasteur sans savoir quoi faire."""
    assert CoverageGap.NO_RHYTHM is not CoverageGap.BLIND
    assert {CoverageGap.NO_RHYTHM, CoverageGap.BLIND} <= set(CoverageGap)
