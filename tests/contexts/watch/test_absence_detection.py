"""*« Awa, trois rencontres, sans nouvelles. »*

La phrase fondatrice du produit — et jusqu'à aujourd'hui, **rien ne la produisait**.
`CasePriority.ABSENCE` existait, l'arbitrage savait la trier, la machine à états savait la porter,
et aucune source ne l'émettait.

Elle ne pouvait pas naître autrement. Le silence ne peut pas entrer comme fait : c'est l'asymétrie
fondatrice, et `FactKind` ne contient volontairement aucun `MEMBER_INACTIVE`. La seule façon de
constater une absence est donc de poser une **échéance au moment d'une parole** — quelqu'un était
là — et de la laisser tomber plus tard.

Ce module vérifie les deux moitiés de cette promesse : ce qui s'ouvre, et surtout **ce qui ne
s'ouvre pas**.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.attendance.application.return_detection import DetectReturn
from app.contexts.attendance.domain.enums import AbsenceReason, AbsenceSource
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.watch.application.fire_checks import FireDueChecks
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.check_fired import CheckFiredV1
from app.contexts.watch.application.interpreters.presence_recorded import (
    ABSENCE_WATCH_KIND,
    PresenceRecordedV2,
)
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.parameters import DEFAULTS
from app.contexts.watch.domain.registry import default_registry
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

# Après la date d'effet de `PresenceRecordedV2` : avant elle, c'est la V1 qui répond, et elle
# n'arme rien. Le passé ne change jamais de sens — y compris dans les tests.
_NOW = datetime(2026, 8, 2, tzinfo=UTC)  # un dimanche
_WEEK = timedelta(days=7)


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


class _Rhythm:
    """Le rythme du groupe, réduit à ce qu'il dit : la N-ième rencontre attendue après une date."""

    def __init__(self, *, every=_WEEK, threshold=3, grace=timedelta(days=2), cadence=True):
        self._every, self._threshold, self._grace, self._cadence = (
            every, threshold, grace, cadence,
        )

    async def next_check_at(self, *, group_id, tenant_id, since):
        if not self._cadence:
            return None  # un groupe sans cadence déclarée n'attend rien de personne
        return since + self._every * self._threshold + self._grace


class _Context:
    """Ce que la Présence répond au moment du tir — les rencontres **réellement tenues**."""

    def __init__(self, *, occurrences, threshold=3, label="la cellule Bethel", following=None):
        self._occurrences, self._threshold = occurrences, threshold
        self._label, self._following = label, following

    async def for_check(self, check):
        if check.kind != ABSENCE_WATCH_KIND:
            return {}
        observed = {
            "occurrences": self._occurrences,
            "threshold": self._threshold,
            "group_label": self._label,
        }
        if self._following is not None:
            observed["next_check_at"] = self._following.isoformat()
        return observed


def _engine(checks, *, absences=None, signals=None, ledger=None):
    interpreters = InterpreterRegistry()
    interpreters.register(PresenceRecordedV2())
    interpreters.register(CheckFiredV1())
    store = AttendanceNeutralizationStore(absences or FakeAbsences(), FakeExclusions())
    return Intake(
        ledger or FakeLedger(), default_registry(), interpreters, store,
        signals or FakeSignals(), checks,
    )


async def _present(intake, *, tenant, member, group, at=_NOW, rhythm=None):
    """Une présence saisie — la parole d'où part tout le reste."""
    await DetectReturn(intake, rhythm or _Rhythm()).on_positive_presence(
        account_id=member, tenant_id=tenant, occurred_at=at,
        gathering_id=uuid4(), recorded_at=at, group_id=group,
    )


async def _fire(checks, intake, *, tenant, at, context=None):
    return await FireDueChecks(
        checks, intake, _Params(), context, clock=lambda: at
    ).execute(tenant_id=tenant)


# --- Ce qui s'ouvre ----------------------------------------------------------------------


async def test_a_presence_arms_the_watch_and_the_deadline_opens_the_case():
    """De « elle était là » à « sans nouvelles », sans qu'aucun fait ne dise jamais un silence."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)

    await _present(intake, tenant=tenant, member=member, group=group)
    (armed,) = checks.rows
    assert armed["kind"] == ABSENCE_WATCH_KIND
    assert armed["due_at"] == _NOW + _WEEK * 3 + timedelta(days=2)  # 3 rencontres + la marge
    assert signals.rows == []  # être là n'ouvre rien

    await _fire(
        checks, intake, tenant=tenant, at=armed["due_at"],
        context=_Context(occurrences=3),
    )

    (case,) = signals.rows
    assert case.origin is CasePriority.ABSENCE
    assert case.reason == "Sans nouvelles — 3 rencontres de la cellule Bethel."


async def test_the_case_names_the_group_so_the_lead_reads_a_person_not_an_id():
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)
    await _present(intake, tenant=tenant, member=member, group=group)

    await _fire(
        checks, intake, tenant=tenant, at=checks.rows[0]["due_at"],
        context=_Context(occurrences=4, label="le groupe des jeunes"),
    )

    assert "le groupe des jeunes" in signals.rows[0].reason


# --- Ce qui ne s'ouvre pas, et qui compte autant ------------------------------------------


async def test_coming_back_pushes_the_deadline_away_so_nothing_ever_falls():
    """**Tant qu'Awa vient, rien ne tombe jamais.**

    Chaque présence annule le regard précédent et en pose un nouveau. Sans l'annulation, une
    personne revenue en février recevrait quand même le regard programmé en janvier."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)

    await _present(intake, tenant=tenant, member=member, group=group, at=_NOW)
    await _present(intake, tenant=tenant, member=member, group=group, at=_NOW + _WEEK)

    pending = [c for c in checks.rows if c["fired_at"] is None and c["cancelled_at"] is None]
    assert len(pending) == 1  # une seule échéance vivante à la fois
    assert pending[0]["due_at"] == _NOW + _WEEK * 4 + timedelta(days=2)
    assert any(c["cancelled_at"] is not None for c in checks.rows)  # la précédente est levée


async def test_a_neutralized_person_is_never_asked_why_she_was_not_there():
    """Un deuil, un voyage, une maladie déclarée : le silence a une explication.

    Rappeler quelqu'un pour lui demander pourquoi il n'est pas venu à l'enterrement de son père
    est l'échec le plus cher que ce produit puisse produire."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, signals, absences = FakeChecks(), FakeSignals(), FakeAbsences()
    intake = _engine(checks, absences=absences, signals=signals)
    await _present(intake, tenant=tenant, member=member, group=group)
    due = checks.rows[0]["due_at"]
    absences.rows.append(
        PlannedAbsence(
            id=uuid4(), tenant_id=tenant, account_id=member,
            from_date=_NOW + _WEEK, to_date=due + _WEEK,
            reason=AbsenceReason.FAMILY, source=AbsenceSource.ANNOUNCEMENT,
            declared_by_account_id=uuid4(), declared_at=_NOW, source_ref=uuid4(),
        )
    )

    await _fire(
        checks, intake, tenant=tenant, at=due,
        context=_Context(occurrences=5, following=due + _WEEK * 3),
    )

    assert signals.rows == []  # rien, personne n'est dérangé
    # Mais on continue de regarder : le silence après le retour attendu reste un silence.
    assert [c["due_at"] for c in checks.rows if c["fired_at"] is None] == [due + _WEEK * 3]


async def test_under_the_threshold_we_look_again_instead_of_opening():
    """Deux rencontres manquées, c'est la vie. La première échéance ne doit pas être la dernière."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)
    await _present(intake, tenant=tenant, member=member, group=group)
    due = checks.rows[0]["due_at"]

    await _fire(
        checks, intake, tenant=tenant, at=due,
        context=_Context(occurrences=2, following=due + _WEEK * 3),
    )

    assert signals.rows == []
    pending = [c for c in checks.rows if c["fired_at"] is None]
    assert [c["due_at"] for c in pending] == [due + _WEEK * 3]
    # Et la mémoire de la dernière présence voyage d'échéance en échéance.
    assert pending[0]["payload"]["since"] == _NOW.isoformat()


async def test_a_group_that_never_met_makes_nobody_absent():
    """Si la cellule ne s'est pas réunie, personne n'a rien manqué.

    C'est ce qu'apporte le comptage des rencontres **tenues** plutôt que des semaines écoulées :
    le problème de l'acquittement se dissout au lieu d'être traité."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)
    await _present(intake, tenant=tenant, member=member, group=group)

    await _fire(
        checks, intake, tenant=tenant, at=checks.rows[0]["due_at"],
        context=_Context(occurrences=0),
    )

    assert signals.rows == []


async def test_a_group_without_a_declared_cadence_arms_nothing():
    """Sans rythme attendu, il n'y a pas d'occurrence à manquer — et on ne pose pas d'échéance
    sur une intuition. Le silence de quelqu'un dont personne n'attend rien n'est pas un signal."""
    tenant, member, group = uuid4(), uuid4(), uuid4()
    checks = FakeChecks()
    intake = _engine(checks)

    await _present(
        intake, tenant=tenant, member=member, group=group, rhythm=_Rhythm(cadence=False)
    )

    assert checks.rows == []


async def test_a_church_wide_gathering_arms_nothing():
    """Un culte n'a pas de groupe : il ne fonde pas un lien de veille, donc pas d'échéance."""
    tenant, member = uuid4(), uuid4()
    checks = FakeChecks()
    intake = _engine(checks)

    await DetectReturn(intake, _Rhythm()).on_positive_presence(
        account_id=member, tenant_id=tenant, occurred_at=_NOW,
        gathering_id=uuid4(), recorded_at=_NOW, group_id=None,
    )

    assert checks.rows == []


# --- Le passé ne change jamais de sens ---------------------------------------------------


def test_the_older_interpreter_still_answers_for_older_facts():
    """La V2 arme la détection ; les faits entrés avant sa date d'effet gardent la V1.

    Sans cette règle, une reprojection armerait rétroactivement des échéances sur des présences
    vieilles de six mois — et le moteur relancerait des gens à propos d'un silence qu'il vient
    d'inventer."""
    from app.contexts.watch.application.interpreters.presence_recorded import (
        PresenceRecordedV1,
    )

    registry = InterpreterRegistry()
    registry.register(PresenceRecordedV1())
    registry.register(PresenceRecordedV2())

    old = datetime(2026, 3, 1, tzinfo=UTC)
    assert isinstance(
        registry.for_fact(_dated(old)), PresenceRecordedV1
    )
    assert isinstance(
        registry.for_fact(_dated(datetime(2026, 8, 1, tzinfo=UTC))), PresenceRecordedV2
    )


def _dated(recorded_at):
    from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
    from app.contexts.watch.domain.registry import ATTENDANCE

    return Fact(
        fact_id=uuid4(), tenant_id=uuid4(), occurred_at=recorded_at, recorded_at=recorded_at,
        source=ATTENDANCE, kind=FactKind.PRESENCE_RECORDED,
        subject_kind=SubjectKind.PERSON, subject_id=uuid4(), payload={},
    )
