"""L'échéance qui tombe **produit** enfin quelque chose.

Le worker écrivait des `CHECK_FIRED` au ledger depuis le premier jour, et aucun interpreter n'était
enregistré pour ce type de fait : le registre renvoyait une liste vide. Toute la mécanique existait
— la table, la pose, l'annulation, le garde anti-orage — et elle tirait dans le vide.

Ce module vérifie la boucle entière : une **parole** pose une échéance, l'échéance tombe, le fait
entre au journal, l'interpreter en tire un cas, et la suivante est posée. Puis la même chose
rejouée depuis le journal seul.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.fire_checks import FireDueChecks, fact_id_for
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.check_fired import CheckFiredV1, CheckKind
from app.contexts.watch.application.interpreters.self_declaration import (
    RHYTHM_KIND,
    SelfDeclarationV1,
)
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.parameters import DEFAULTS
from app.contexts.watch.domain.registry import MISSION, default_registry
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

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


def _engine(checks, *, ledger=None, signals=None):
    """Le moteur complet : la parole pose, le tir interprète."""
    interpreters = InterpreterRegistry()
    interpreters.register(SelfDeclarationV1())
    interpreters.register(CheckFiredV1())
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    return Intake(
        ledger or FakeLedger(), default_registry(), interpreters, store,
        signals or FakeSignals(), checks,
    )


def _rhythm(tenant, member, *, every_days=30) -> Fact:
    """« Prenez de mes nouvelles tous les N jours. » — une parole, jamais un calcul."""
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=MISSION, kind=FactKind.SELF_DECLARATION,
        subject_kind=SubjectKind.PERSON, subject_id=member,
        payload={"kind": RHYTHM_KIND, "every_days": every_days},
        consent=ConsentProof(given_by=member, scope=ConsentScope.BE_WATCHED, given_at=_NOW),
    )


async def _fire(checks, intake, *, at):
    return await FireDueChecks(checks, intake, _Params(), clock=lambda: at).execute(
        tenant_id=next(iter({c["tenant_id"] for c in checks.rows}))
    )


# --- La boucle entière -------------------------------------------------------------------


async def test_a_chosen_rhythm_opens_a_case_when_its_deadline_falls():
    """De la parole au cas, en passant par le temps — et sans qu'un interpreter lise l'horloge."""
    tenant, member = uuid4(), uuid4()
    checks, signals, ledger = FakeChecks(), FakeSignals(), FakeLedger()
    intake = _engine(checks, ledger=ledger, signals=signals)

    await intake.submit(_rhythm(tenant, member, every_days=30))
    assert signals.rows == []  # choisir un rythme n'ouvre rien : ça règle une cadence

    due = _NOW + timedelta(days=30)
    report = await _fire(checks, intake, at=due)

    assert report.fired == 1
    (case,) = signals.rows
    assert case.origin is CasePriority.DECLARED  # sa parole, donc hors plafond
    assert "30 jours" in case.reason  # la raison posée voyage jusqu'à l'écran
    assert case.opened_at == due  # daté de l'échéance, pas de la passe


async def test_the_next_deadline_is_posed_when_the_previous_one_falls():
    """Un rythme qu'on honore une fois puis qu'on oublie est pire que pas de rythme du tout."""
    tenant, member = uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)
    await intake.submit(_rhythm(tenant, member, every_days=30))

    await _fire(checks, intake, at=_NOW + timedelta(days=30))

    pending = [c for c in checks.rows if c["fired_at"] is None and c["cancelled_at"] is None]
    assert len(pending) == 1
    assert pending[0]["due_at"] == _NOW + timedelta(days=60)
    # La cadence se transmet d'échéance en échéance, sans jamais être relue ailleurs.
    assert pending[0]["payload"]["every_days"] == 30


async def test_an_unknown_check_kind_produces_nothing_and_is_kept():
    """Une échéance d'un type qu'on ne sait pas encore lire reste au journal.

    Le jour où son interpreter arrivera, une reprojection lui donnera rétroactivement son sens."""
    tenant, member = uuid4(), uuid4()
    checks, signals, ledger = FakeChecks(), FakeSignals(), FakeLedger()
    intake = _engine(checks, ledger=ledger, signals=signals)
    await checks.schedule(
        subject_id=member, tenant_id=tenant, kind="un_regime_futur", reason="…",
        due_at=_NOW - timedelta(days=1), at=_NOW,
    )

    await _fire(checks, intake, at=_NOW)

    assert len(ledger.rows) == 1  # le fait est là
    assert signals.rows == []  # et rien n'a été inventé


async def test_an_expected_return_that_never_came_opens_a_deadline_case():
    """L'échéance, pas la personne : c'est le dispositif qui avait posé une date."""
    tenant, member = uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)
    await checks.schedule(
        subject_id=member, tenant_id=tenant, kind=CheckKind.RETURN.value,
        reason="Retour attendu après un deuil, non constaté.",
        due_at=_NOW - timedelta(days=1), at=_NOW,
    )

    await _fire(checks, intake, at=_NOW)

    (case,) = signals.rows
    assert case.origin is CasePriority.DEADLINE
    assert "Retour attendu" in case.reason
    # Et rien ne se repose : à un moment il faut un humain, pas un rappel de plus.
    assert [c for c in checks.rows if c["fired_at"] is None] == []


# --- L'idempotence du tir ----------------------------------------------------------------


async def test_two_overlapping_passes_never_fire_the_same_deadline_twice():
    """L'identifiant du fait est **dérivé de l'échéance** : une échéance ne tombe qu'une fois.

    Avec un identifiant tiré au hasard à chaque passe, le contrôle de doublon de l'intake ne
    pouvait rien attraper — et deux crons qui se chevauchent relançaient deux fois la même
    personne. Une relance en double n'est pas une imprécision : elle est reçue comme un
    harcèlement."""
    tenant, member = uuid4(), uuid4()
    checks, signals, ledger = FakeChecks(), FakeSignals(), FakeLedger()
    intake = _engine(checks, ledger=ledger, signals=signals)
    await checks.schedule(
        subject_id=member, tenant_id=tenant, kind=CheckKind.RETURN.value, reason="…",
        due_at=_NOW - timedelta(days=1), at=_NOW,
    )
    check_id = checks.rows[0]["id"]

    # La première passe tire ; on remet la ligne « non tirée » pour simuler la seconde passe qui
    # l'avait déjà lue avant que la première ne la marque.
    await _fire(checks, intake, at=_NOW)
    checks.rows[0]["fired_at"] = None
    await _fire(checks, intake, at=_NOW)

    assert len(ledger.rows) == 1
    assert ledger.rows[0].fact_id == fact_id_for(check_id)
    assert len(signals.rows) == 1


async def test_a_deadline_is_marked_fired_before_the_fact_enters():
    """L'ordre protège : la ligne est verrouillée, et si l'intake échoue la transaction retombe.

    L'ordre inverse laissait une fenêtre où le fait était au journal sans que l'échéance soit
    close — la passe suivante l'aurait retirée."""
    tenant, member = uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)
    await checks.schedule(
        subject_id=member, tenant_id=tenant, kind=CheckKind.RETURN.value, reason="…",
        due_at=_NOW - timedelta(days=1), at=_NOW,
    )

    await _fire(checks, intake, at=_NOW)

    assert checks.rows[0]["fired_at"] == _NOW


# --- Le rejeu ----------------------------------------------------------------------------


async def test_replaying_the_ledger_rebuilds_the_whole_chain():
    """Le temps est rejouable : le journal contient la parole **et** l'échéance tombée.

    C'est tout l'intérêt de faire entrer le temps par un fait plutôt que par un service qui
    évaluerait les échéances en direct."""
    from app.contexts.watch.application.projections import RebuildProjections

    tenant, member = uuid4(), uuid4()
    checks, signals, ledger = FakeChecks(), FakeSignals(), FakeLedger()
    intake = _engine(checks, ledger=ledger, signals=signals)
    await intake.submit(_rhythm(tenant, member, every_days=15))
    await _fire(checks, intake, at=_NOW + timedelta(days=15))

    before = [(c.subject_id, c.reason, c.origin, c.opened_at) for c in signals.rows]

    interpreters = InterpreterRegistry()
    interpreters.register(SelfDeclarationV1())
    interpreters.register(CheckFiredV1())
    await RebuildProjections(
        ledger,
        interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals,
        None,
        checks,
    ).execute(tenant_id=tenant)

    after = [(c.subject_id, c.reason, c.origin, c.opened_at) for c in signals.rows]
    assert after == before
    # Et la chaîne des échéances est reconstruite à l'identique, sans la faire retomber.
    assert sum(1 for c in checks.rows if c["fired_at"] is None) == 1
