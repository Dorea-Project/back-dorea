"""Les deux dépôts de la boucle froide, contre une vraie base.

Le premier recolle un cas à **la parole qui l'a ouvert** : `source_refs` est une colonne JSON, et
la joindre au journal marcherait en Postgres et pas en SQLite. Une requête qui ne tourne que sur
la base de production est une requête qu'on ne teste pas — donc deux requêtes, et le recollement
en Python.

Le second tient la règle qui protège l'écran du pasteur : **une seule proposition en attente par
`(église, paramètre)`**.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.watch.calibration.proposal import CalibrationProposal, ProposalStatus
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.parameters import WatchParam
from app.contexts.watch.domain.signal import SignalOutcome, SignalStatus
from app.contexts.watch.infrastructure.persistence.calibration import (
    SqlAbsenceEvidenceReader,
    SqlCalibrationProposalStore,
)
from app.contexts.watch.infrastructure.persistence.models import (
    FactLedgerModel,
    SignalModel,
)
from app.contexts.watch.infrastructure.persistence.signals import SqlSignalStore
from app.core.database import Base

_NOW = datetime(2026, 8, 5, tzinfo=UTC)
_SINCE = _NOW - timedelta(days=30)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


def _fired(tenant, *, occurrences, threshold=3, seq=1):
    """Le tir d'échéance tel que le worker l'a écrit — c'est **lui** qui porte le contrefactuel."""
    return FactLedgerModel(
        seq=seq, fact_id=uuid4(), tenant_id=tenant,
        occurred_at=_NOW - timedelta(days=10), recorded_at=_NOW - timedelta(days=10),
        source="watch", kind="check_fired", subject_kind="person", subject_id=uuid4(),
        payload={
            "kind": "absence_watch",
            "occurrences": occurrences,
            "threshold": threshold,
        },
    )


def _absence_case(
    tenant, *, fact, outcome=None, origin=CasePriority.ABSENCE, days_old=10
) -> SignalModel:
    return SignalModel(
        id=uuid4(), tenant_id=tenant, subject_id=uuid4(), origin=origin.value,
        status=SignalStatus.CLOSED.value if outcome else SignalStatus.ASSIGNED.value,
        reason="…", opened_at=_NOW - timedelta(days=days_old),
        owner_account_id=uuid4(),
        source_refs=[str(fact.fact_id)] if fact else [],
        priority=origin.value, annotations=[],
        outcome=outcome.value if outcome else None,
        closed_at=_NOW - timedelta(days=1) if outcome else None,
        # Fermé **par quelqu'un** : c'est la signature qui fait la vérité terrain.
        closed_by_account_id=uuid4() if outcome else None,
        episode_id=uuid4(), occurrence_number=1, gestures_count=0,
    )


def _system_closed(tenant):
    """Un cas éteint par le moteur : `closed_by_account_id` est nul, personne n'a rien vérifié."""
    case = _absence_case(tenant, fact=None, outcome=SignalOutcome.EXPLAINED_BY_ANNOUNCEMENT)
    case.closed_by_account_id = None
    return case


def _borne_case(tenant, *, seen, days_old=30, status=SignalStatus.ASSIGNED):
    return SignalModel(
        id=uuid4(), tenant_id=tenant, subject_id=uuid4(),
        origin=CasePriority.ABSENCE.value, status=status.value, reason="…",
        opened_at=_NOW - timedelta(days=days_old), owner_account_id=uuid4(),
        source_refs=[], priority=CasePriority.ABSENCE.value, annotations=[],
        first_seen_at=_NOW - timedelta(days=1) if seen else None,
        episode_id=uuid4(), occurrence_number=1, gestures_count=0,
    )


def _gesture(tenant, *, subject_id, at, seq):
    return FactLedgerModel(
        seq=seq, fact_id=uuid4(), tenant_id=tenant, occurred_at=at, recorded_at=at,
        source="companion", kind="gesture_done", subject_kind="person",
        subject_id=subject_id, payload={"kind": "visit"},
    )


async def test_a_confirmed_absence_already_visited_counts_once_against_the_thresholds(session):
    """La seconde moitié de « un humain a vu avant le moteur », **contre une vraie base**.

    Elle mérite ce test plus que les autres : la fenêtre se compte depuis une colonne, ce qui
    aurait donné une arithmétique d'intervalle que SQLite ne sait pas faire. Le recollement est
    donc en Python — et c'est précisément ce genre de choix qu'on ne vérifie pas en relisant.

    Quatre cas, un seul compte : le confirmé qu'on avait déjà visité. Le visité mais clos sur
    « rien à signaler » est de l'amitié ordinaire ; la visite trop vieille n'explique plus rien ;
    et trois visites avant le même cas ne font pas trois détections manquées."""
    tenant = uuid4()
    visite, amical, ancien, triple = (uuid4() for _ in range(4))
    ouvert = _NOW - timedelta(days=10)
    cases = [
        _absence_case(tenant, fact=None, outcome=SignalOutcome.FOLLOWED),
        _absence_case(tenant, fact=None, outcome=SignalOutcome.NOTHING_TO_REPORT),
        _absence_case(tenant, fact=None, outcome=SignalOutcome.FOLLOWED),
        _absence_case(tenant, fact=None, outcome=SignalOutcome.FOLLOWED),
    ]
    for case, subject in zip(cases, (visite, amical, ancien, triple), strict=True):
        case.subject_id = subject
    session.add_all([
        *cases,
        _gesture(tenant, subject_id=visite, at=ouvert - timedelta(days=3), seq=1),
        _gesture(tenant, subject_id=amical, at=ouvert - timedelta(days=3), seq=2),
        _gesture(tenant, subject_id=ancien, at=ouvert - timedelta(days=45), seq=3),
        *[
            _gesture(tenant, subject_id=triple, at=ouvert - timedelta(days=d), seq=10 + d)
            for d in (2, 5, 9)
        ],
    ])
    await session.flush()

    counted = await SqlSignalStore(session).absences_confirmed_after_a_gesture(
        tenant_id=tenant, since=_SINCE, within=timedelta(days=30)
    )

    assert counted == 2  # le visité confirmé, et le triple-visité — une fois chacun


async def test_a_case_is_joined_back_to_the_shot_that_opened_it(session):
    """Deux requêtes, un recollement, et l'issue vient avec — c'est tout ce que la simulation a
    besoin de savoir, et il n'y a aucun identifiant dedans."""
    tenant = uuid4()
    fact = _fired(tenant, occurrences=4)
    session.add_all([fact, _absence_case(tenant, fact=fact, outcome=SignalOutcome.FOLLOWED)])
    await session.flush()

    (row,) = await SqlAbsenceEvidenceReader(session).absence_evidence(
        tenant_id=tenant, since=_SINCE
    )

    assert (row.occurrences, row.threshold) == (4, 3)
    assert row.outcome == SignalOutcome.FOLLOWED.value


async def test_a_case_born_of_something_else_has_no_counterfactual(session):
    """Un cas d'absence sans tir d'échéance derrière — ou né avant `CheckFiredV1` — n'a pas de
    contrefactuel lisible. On ne l'invente pas, on le laisse dehors."""
    tenant = uuid4()
    session.add(_absence_case(tenant, fact=None))
    await session.flush()

    assert await SqlAbsenceEvidenceReader(session).absence_evidence(
        tenant_id=tenant, since=_SINCE
    ) == []


async def test_it_reads_absences_only_and_only_in_the_window(session):
    """Une inquiétude signalée n'a pas de seuil d'occurrences : la simuler n'aurait aucun sens."""
    tenant = uuid4()
    old, concern = _fired(tenant, occurrences=4, seq=1), _fired(tenant, occurrences=9, seq=2)
    session.add_all([
        old, concern,
        _absence_case(tenant, fact=old, days_old=90),  # hors fenêtre
        _absence_case(tenant, fact=concern, origin=CasePriority.CONCERN),
    ])
    await session.flush()

    assert await SqlAbsenceEvidenceReader(session).absence_evidence(
        tenant_id=tenant, since=_SINCE
    ) == []


async def test_another_church_is_not_read(session):
    tenant, other = uuid4(), uuid4()
    fact = _fired(other, occurrences=4)
    session.add_all([fact, _absence_case(other, fact=fact)])
    await session.flush()

    assert await SqlAbsenceEvidenceReader(session).absence_evidence(
        tenant_id=tenant, since=_SINCE
    ) == []


async def test_ground_truth_reads_human_closures_only(session):
    """Les deux lectures qui alimentent toute la boucle froide, contre une vraie base.

    Elles n'avaient aucun test SQL : `closed_cases_since` filtre sur la clôture humaine, et
    `ignored_ratio` s'appuie sur un `COUNT(*) FILTER (WHERE …)` — deux choses qu'on ne vérifie
    pas en relisant du Python."""
    tenant = uuid4()
    human = _fired(tenant, occurrences=4, seq=1)
    session.add_all([
        human,
        _absence_case(tenant, fact=human, outcome=SignalOutcome.NOTHING_TO_REPORT),
        # Clôturé par le système : la vérité terrain ne l'écoute pas.
        _system_closed(tenant),
    ])
    await session.flush()

    rows = await SqlSignalStore(session).closed_cases_since(
        tenant_id=tenant, since=_SINCE
    )

    assert rows == [(CasePriority.ABSENCE.value, SignalOutcome.NOTHING_TO_REPORT.value)]


async def test_the_ignored_ratio_counts_what_weighs_on_someone(session):
    """Numérateur : jamais ouverts. Dénominateur : ce qui pèse — donc pas les retenus, qui ne
    sont précisément pas encore sur les épaules de quelqu'un."""
    tenant = uuid4()
    session.add_all([
        _borne_case(tenant, seen=True),
        _borne_case(tenant, seen=False),
        _borne_case(tenant, seen=False),
        _borne_case(tenant, seen=False, days_old=1),  # trop récent
        _borne_case(tenant, seen=False, status=SignalStatus.HELD),  # retenu ≠ porté
    ])
    await session.flush()

    assert await SqlSignalStore(session).ignored_ratio(
        tenant_id=tenant, older_than=_NOW - timedelta(days=7)
    ) == (2, 3)


def _proposal(tenant, *, param=WatchParam.OPEN_CASES_CAP, proposed=4):
    return CalibrationProposal(
        id=uuid4(), tenant_id=tenant, param=param, current=5, proposed=proposed,
        evidence="…",
    )


async def test_only_one_proposal_waits_per_parameter(session):
    """Trente fois la même phrase, et l'écran du pasteur devient un endroit qu'on ferme
    sans lire."""
    store, tenant = SqlCalibrationProposalStore(session), uuid4()

    first = await store.add_all([_proposal(tenant)])
    second = await store.add_all([_proposal(tenant, proposed=3)])

    assert len(first) == 1 and second == []
    assert len(await store.pending(tenant)) == 1


async def test_a_decided_proposal_frees_the_parameter(session):
    """Une décision ne fait pas revenir la même proposition — elle rouvre la place pour une
    **neuve**, avec des nombres neufs, à la prochaine mesure."""
    store, tenant, pastor = SqlCalibrationProposalStore(session), uuid4(), uuid4()
    (waiting,) = await store.add_all([_proposal(tenant)])

    await store.save(
        CalibrationProposal(
            **{
                **waiting.__dict__,
                "status": ProposalStatus.REJECTED,
                "decided_by_account_id": pastor,
                "decided_at": _NOW,
            }
        )
    )

    assert await store.pending(tenant) == []
    refetched = await store.get(proposal_id=waiting.id, tenant_id=tenant)
    assert refetched.status is ProposalStatus.REJECTED
    assert refetched.decided_by_account_id == pastor
    assert len(await store.add_all([_proposal(tenant)])) == 1


async def test_only_the_decision_is_writable(session):
    """Une preuve réécrite après coup ne prouve plus rien : `save` ne touche ni au nombre proposé,
    ni à la phrase qui le justifie."""
    store, tenant = SqlCalibrationProposalStore(session), uuid4()
    (waiting,) = await store.add_all([_proposal(tenant, proposed=4)])

    await store.save(
        CalibrationProposal(
            **{**waiting.__dict__, "proposed": 99, "evidence": "réécrit après coup"}
        )
    )

    refetched = await store.get(proposal_id=waiting.id, tenant_id=tenant)
    assert (refetched.proposed, refetched.evidence) == (4, "…")
