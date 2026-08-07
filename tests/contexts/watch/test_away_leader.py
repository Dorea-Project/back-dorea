"""**Le responsable en voyage** — G-2 et G-3, et un mot conflué qui coûtait cher.

Deux choses distinctes, découvertes l'une derrière l'autre.

**G-2, une correction.** Le membre qui prend la peine de dire *« je pars du 5 au 20 »* recevait
quand même *« sans nouvelles — 3 rencontres »*. Deux questions vivaient sous le même mot :

| La question | La bonne réponse |
| :-- | :-- |
| quelles lignes le moteur a-t-il posées ? (prolonger, purger) | `ANNOUNCEMENT` seul |
| sait-on pourquoi cette personne n'est pas là ? | **les deux origines** |

La seconde est la seule que la veille pose, et elle lisait la réponse de la première. Le roster
honorait la dignité de prévenir ; la veille l'ignorait — et c'est précisément à celui qui avait
prévenu qu'on allait demander pourquoi il n'était pas venu.

**G-3, une relève.** Un responsable parti trois semaines finissait consigné *« n'ouvre plus rien,
a probablement besoin d'aide »*. Le diagnostic est faux, le mot est blessant, et l'action qu'il
appelle n'est pas la bonne : un absent n'a pas besoin qu'on l'aide, il a besoin qu'on le relève.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.attendance.application.return_detection import DetectReturn
from app.contexts.attendance.domain.enums import (
    AbsenceReason,
    AbsenceSource,
)
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.watch.application.concern_watchdog import (
    WatchForAwayLeaders,
    WatchForUnopenedCases,
)
from app.contexts.watch.application.fire_checks import FireDueChecks
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.check_fired import CheckFiredV1
from app.contexts.watch.application.interpreters.presence_recorded import (
    ABSENCE_WATCH_KIND,
    PresenceRecordedV2,
)
from app.contexts.watch.calibration.judge import IGNORED_AFTER_DAYS
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import CasePriority, CoverageGap
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam
from app.contexts.watch.domain.registry import default_registry
from app.contexts.watch.domain.signal import Signal, SignalStatus
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

_NOW = datetime(2026, 8, 2, tzinfo=UTC)  # un dimanche
_WEEK = timedelta(days=7)


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


class _Rhythm:
    async def next_check_at(self, *, group_id, tenant_id, since):
        return since + _WEEK * 3 + timedelta(days=2)


class _Context:
    async def for_check(self, check):
        if check.kind != ABSENCE_WATCH_KIND:
            return {}
        return {"occurrences": 3, "threshold": 3, "group_label": "la cellule Bethel"}


class _Gaps:
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


def _declared_absence(*, tenant, account, frm, to, source=AbsenceSource.SELF_DECLARED):
    return PlannedAbsence(
        id=uuid4(), tenant_id=tenant, account_id=account,
        from_date=frm, to_date=to, reason=AbsenceReason.TRAVEL, source=source,
        declared_by_account_id=account, declared_at=frm, source_ref=uuid4(),
    )


def _carried(signals, *, tenant, owner, seen=False, days_old=IGNORED_AFTER_DAYS + 1):
    signals.rows.append(
        Signal(
            id=uuid4(), tenant_id=tenant, subject_id=uuid4(),
            origin=CasePriority.ABSENCE, reason="Sans nouvelles.",
            opened_at=_NOW - timedelta(days=days_old),
            status=SignalStatus.ASSIGNED, owner_account_id=owner,
            first_seen_at=_NOW - timedelta(days=1) if seen else None,
        )
    )


def _away_watch(signals, gaps, absences):
    return WatchForAwayLeaders(
        signals, gaps,
        AttendanceNeutralizationStore(absences, FakeExclusions()),
        clock=lambda: _NOW,
    )


# --- G-2 : la dignité de prévenir, enfin entendue par la veille -----------------------------


async def test_a_member_who_declared_his_trip_is_never_asked_why_he_was_not_there():
    """**La correction du mot conflué**, vérifiée sur le chemin complet d'un fait.

    Sondet dit qu'il part du 9 au 30. L'échéance tombe pendant son voyage — et rien ne s'ouvre.
    C'est exactement ce que le test de neutralisation promettait depuis le début : *« un deuil, un
    voyage, une maladie **déclarée** : le silence a une explication »*. La promesse était écrite,
    la lecture filtrait sur l'origine, et la moitié déclarée n'arrivait jamais."""
    tenant, sondet, group = uuid4(), uuid4(), uuid4()
    checks, signals, absences = FakeChecks(), FakeSignals(), FakeAbsences()
    interpreters = InterpreterRegistry()
    interpreters.register(PresenceRecordedV2())
    interpreters.register(CheckFiredV1())
    intake = Intake(
        FakeLedger(), default_registry(), interpreters,
        AttendanceNeutralizationStore(absences, FakeExclusions()), signals, checks,
    )
    await DetectReturn(intake, _Rhythm()).on_positive_presence(
        account_id=sondet, tenant_id=tenant, occurred_at=_NOW,
        gathering_id=uuid4(), recorded_at=_NOW, group_id=group,
    )
    due = checks.rows[0]["due_at"]
    absences.rows.append(
        _declared_absence(
            tenant=tenant, account=sondet, frm=_NOW + _WEEK, to=due + _WEEK
        )
    )

    await FireDueChecks(
        checks, intake, _Params(), _Context(), clock=lambda: due
    ).execute(tenant_id=tenant)

    assert signals.rows == []  # personne n'est dérangé : il avait prévenu


# --- G-3 : la relève ------------------------------------------------------------------------


async def test_a_leader_who_left_with_cases_on_his_desk_calls_for_a_stand_in():
    """Le défaut se lève **à la déclaration**, sans seuil de volume, et il dit jusqu'à quand.

    Attendre le taux d'ignorés donnerait l'alerte au tiers du voyage. Et « absent » sans la date
    n'est pas actionnable : on ne désigne pas la même chose pour quatre jours et pour six semaines.
    """
    tenant, responsable = uuid4(), uuid4()
    signals, gaps, absences = FakeSignals(), _Gaps(), FakeAbsences()
    _carried(signals, tenant=tenant, owner=responsable)
    absences.rows.append(
        _declared_absence(
            tenant=tenant, account=responsable,
            frm=_NOW - timedelta(days=1), to=_NOW + timedelta(days=20),
        )
    )

    flagged = await _away_watch(signals, gaps, absences).execute(tenant_id=tenant)

    assert flagged == [responsable]
    (gap,) = gaps.rows
    assert gap.gap is CoverageGap.LEADER_AWAY
    assert gap.reason == "Absent jusqu'au 22 août — 1 situation(s) lui sont confiées. À relever."


async def test_an_absent_leader_carrying_nobody_raises_nothing():
    """Absent sans charge : il n'y a rien à relever, et un défaut vide se désapprend en trois
    semaines."""
    tenant, responsable = uuid4(), uuid4()
    signals, gaps, absences = FakeSignals(), _Gaps(), FakeAbsences()
    absences.rows.append(
        _declared_absence(
            tenant=tenant, account=responsable,
            frm=_NOW - timedelta(days=1), to=_NOW + timedelta(days=20),
        )
    )

    assert await _away_watch(signals, gaps, absences).execute(tenant_id=tenant) == []
    assert gaps.rows == []


async def test_a_leader_back_already_is_not_flagged_as_away():
    """Une absence terminée n'explique plus rien : la fenêtre est lue au présent."""
    tenant, responsable = uuid4(), uuid4()
    signals, gaps, absences = FakeSignals(), _Gaps(), FakeAbsences()
    _carried(signals, tenant=tenant, owner=responsable)
    absences.rows.append(
        _declared_absence(
            tenant=tenant, account=responsable,
            frm=_NOW - timedelta(days=30), to=_NOW - timedelta(days=2),
        )
    )

    assert await _away_watch(signals, gaps, absences).execute(tenant_id=tenant) == []


async def test_the_travelling_leader_is_no_longer_told_he_is_probably_overloaded():
    """**Basculé le 05/08/2026 — l'assertion d'acceptation de G-3.**

    Le même responsable, les mêmes quatre cas jamais ouverts. Avant, l'indicateur qui anticipe
    l'abandon écrivait sur lui *« a probablement besoin d'aide »*. Il n'est pas débordé, il est en
    voyage, et il l'avait déclaré.

    `LEADER_AWAY` porte déjà sa charge et appelle une relève ; ajouter le second défaut serait deux
    fois la même personne pour le même fait, et le mauvais des deux."""
    tenant, voyageur, noye = uuid4(), uuid4(), uuid4()
    signals, gaps, absences = FakeSignals(), _Gaps(), FakeAbsences()
    for _ in range(DEFAULTS[WatchParam.UNOPENED_VOLUME_FLOOR]):
        _carried(signals, tenant=tenant, owner=voyageur)
        _carried(signals, tenant=tenant, owner=noye)
    absences.rows.append(
        _declared_absence(
            tenant=tenant, account=voyageur,
            frm=_NOW - timedelta(days=1), to=_NOW + timedelta(days=20),
        )
    )

    flagged = await WatchForUnopenedCases(
        signals, gaps, _Params(), _away_watch(signals, gaps, absences), clock=lambda: _NOW
    ).execute(tenant_id=tenant)

    assert flagged == [noye]  # le voyageur n'est pas soupçonné, l'autre l'est toujours
    assert [g.gap for g in gaps.rows] == [CoverageGap.CASES_NOT_OPENED]
