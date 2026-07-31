"""Les gestes du responsable au journal — **un rejeu ne détruit plus le soin**.

Le ledger ne contenait que ce que les sources disent du monde. Ce qu'un responsable *faisait* —
ouvrir un cas, le fermer avec une issue — vivait uniquement sur la projection. Une reprojection
l'effaçait donc sans pouvoir le reconstruire : les issues qu'il avait conclues, le premier regard,
la chaîne d'épisode qui évite de rappeler quelqu'un en repartant de zéro. Très exactement la trace
du soin apporté, détruite au nom de la réparation.

Ce module vérifie les quatre propriétés qui font que ça tient : le geste entre au journal, le rejeu
le reconstruit, un geste refusé n'y entre **pas**, et fermer le cas d'un défunt reste possible.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.case_acts import fact_id_for
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.case_acts import CaseClosedV1, CaseSeenV1
from app.contexts.watch.application.my_cases import CloseCase, SeeCase
from app.contexts.watch.application.projections import RebuildProjections
from app.contexts.watch.domain.errors import AbsorbingOutcomeError
from app.contexts.watch.domain.facts import CASE_ACTS, FactKind
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeExclusions,
    FakeSignals,
    case_acts_for,
)

_NOW = datetime(2026, 8, 4, tzinfo=UTC)


def _case(signals, *, tenant, subject, owner, status=SignalStatus.ASSIGNED):
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=subject,
        origin=__import__(
            "app.contexts.watch.domain.effects", fromlist=["CasePriority"]
        ).CasePriority.ABSENCE,
        reason="Sans nouvelles.", opened_at=_NOW - timedelta(days=7),
        status=status, owner_account_id=owner,
    )
    signals.rows.append(case)
    return case


def _acts(signals, *, at=_NOW):
    return case_acts_for(signals, clock=lambda: at)


# --- Le geste entre au journal -----------------------------------------------------------


async def test_seeing_a_case_writes_a_fact_not_just_a_column():
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)
    acts = _acts(signals)

    await SeeCase(signals, acts, clock=lambda: _NOW).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    assert case.first_seen_at == _NOW  # la projection est à jour
    (fact,) = acts._intake._ledger.rows  # et le geste est au journal
    assert fact.kind is FactKind.CASE_SEEN
    assert fact.subject_id == subject  # porte sur la personne, pas sur un identifiant de cas
    assert fact.payload["actor_account_id"] == str(jean)
    assert fact.payload["signal_id"] == str(case.id)


async def test_the_same_gesture_never_enters_twice():
    """On n'ouvre un cas pour la première fois qu'une fois — `fact_id` est dérivé du geste."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)
    acts = _acts(signals)
    see = SeeCase(signals, acts, clock=lambda: _NOW)

    await see.execute(signal_id=case.id, tenant_id=tenant, actor_account_id=jean)
    await see.execute(signal_id=case.id, tenant_id=tenant, actor_account_id=jean)

    assert len(acts._intake._ledger.rows) == 1
    assert acts._intake._ledger.rows[0].fact_id == fact_id_for(case.id, FactKind.CASE_SEEN)


# --- Le rejeu reconstruit ce que le responsable a fait -----------------------------------


async def test_a_replay_rebuilds_the_outcome_the_responsable_had_concluded():
    """Le test qui donne son sens au lot : avant, ce rejeu effaçait l'issue et son auteur.

    Le journal porte ici toute l'histoire — la parole qui ouvre le cas, le regard, la clôture — et
    c'est la première fois que les deux derniers y sont."""
    from app.contexts.watch.application.case_acts import RecordCaseAct
    from app.contexts.watch.application.intake import Intake
    from app.contexts.watch.application.interpreters.self_declaration import (
        SelfDeclarationV1,
    )
    from app.contexts.watch.domain.facts import ConsentProof, ConsentScope, Fact, SubjectKind
    from app.contexts.watch.domain.registry import MISSION, default_registry
    from tests.contexts.watch.fakes import FakeLedger

    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, ledger = FakeSignals(), FakeLedger()

    def _interpreters():
        registry = InterpreterRegistry()
        registry.register(SelfDeclarationV1())
        registry.register(CaseSeenV1())
        registry.register(CaseClosedV1())
        return registry

    intake = Intake(
        ledger, default_registry(), _interpreters(),
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()), signals,
    )
    # « Appelez-moi » — la parole qui ouvre le cas.
    await intake.submit(
        Fact(
            fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
            source=MISSION, kind=FactKind.SELF_DECLARATION,
            subject_kind=SubjectKind.PERSON, subject_id=subject,
            payload={"kind": "contact_request"},
            consent=ConsentProof(
                given_by=subject, scope=ConsentScope.BE_WATCHED, given_at=_NOW
            ),
        )
    )
    case = signals.rows[0]
    case.owner_account_id = jean
    acts = RecordCaseAct(intake, clock=lambda: _NOW)

    await SeeCase(signals, acts, clock=lambda: _NOW).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )
    await CloseCase(signals, acts, None, clock=lambda: _NOW).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
        outcome=SignalOutcome.FOLLOWED,
    )

    # On efface la projection et on rejoue le seul journal, comme le ferait une réparation.
    await RebuildProjections(
        ledger,
        _interpreters(),
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals,
    ).execute(tenant_id=tenant, force=True)

    (rebuilt,) = signals.rows
    assert rebuilt.first_seen_at == _NOW  # la métrique qui anticipe l'abandon
    assert rebuilt.outcome is SignalOutcome.FOLLOWED  # l'issue conclue par un humain
    assert rebuilt.closed_by_account_id == jean  # et qui l'a conclue


# --- Un geste refusé n'entre pas au journal ----------------------------------------------


async def test_a_refused_closure_never_reaches_the_ledger():
    """L'agrégat tranche **avant** l'émission.

    Un geste refusé déjà écrit ferait échouer chaque rejeu ultérieur, sur un acte qui n'a jamais
    eu lieu — le journal deviendrait une bombe à retardement."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)
    acts = _acts(signals)
    close = CloseCase(signals, acts, None, clock=lambda: _NOW)

    await close.execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
        outcome=SignalOutcome.DO_NOT_CONTACT,  # absorbante
    )
    with pytest.raises(AbsorbingOutcomeError):
        await close.execute(
            signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
            outcome=SignalOutcome.FOLLOWED,
        )

    kinds = [f.kind for f in acts._intake._ledger.rows]
    assert kinds == [FactKind.CASE_CLOSED]  # une seule clôture, celle qui a eu lieu


# --- Fermer le cas d'un défunt reste possible --------------------------------------------


async def test_closing_the_case_of_a_deceased_person_still_works():
    """L'exclusion protège des **sources**, pas des gestes du responsable.

    Refuser cet acte laisserait le cas ouvert pour toujours sur son écran, et ferait de la mort de
    quelqu'un un bug d'interface."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, exclusions = FakeSignals(), FakeExclusions()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)

    from app.contexts.attendance.domain.enums import WatchExclusionReason
    from app.contexts.attendance.domain.watch_exclusion import WatchExclusion
    from app.contexts.watch.application.case_acts import RecordCaseAct
    from app.contexts.watch.application.intake import Intake
    from app.contexts.watch.domain.registry import default_registry
    from tests.contexts.watch.fakes import FakeLedger

    exclusions.rows.append(
        WatchExclusion(
            id=uuid4(), account_id=subject, tenant_id=tenant,
            reason=WatchExclusionReason.DECEASED, excluded_at=_NOW,
            declared_by_account_id=uuid4(), source_ref=uuid4(),
        )
    )
    interpreters = InterpreterRegistry()
    interpreters.register(CaseSeenV1())
    interpreters.register(CaseClosedV1())
    ledger = FakeLedger()
    acts = RecordCaseAct(
        Intake(
            ledger, default_registry(), interpreters,
            AttendanceNeutralizationStore(FakeAbsences(), exclusions), signals,
        ),
        clock=lambda: _NOW,
    )

    await CloseCase(signals, acts, None, clock=lambda: _NOW).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
        outcome=SignalOutcome.DECEASED,
    )

    assert case.status is SignalStatus.CLOSED
    assert [f.kind for f in ledger.rows] == [FactKind.CASE_CLOSED]


def test_the_acts_are_a_closed_family():
    """La liste est fermée : on n'ajoute pas un geste sans y penser."""
    assert CASE_ACTS == frozenset({FactKind.CASE_SEEN, FactKind.CASE_CLOSED})
