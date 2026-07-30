"""Le lecteur paresseux — le coût d'un fait cesse de dépendre de la taille de l'église.

Chaque fait déclenchait trois requêtes **à l'échelle du tenant** : tous les exclus, toutes les
neutralisations ouvertes, tous les cas vivants. Les interpreters et l'arbitrage ne posent pourtant
que quatre questions, toutes bornées à une personne — et les index qu'elles demandent existaient
déjà (`ix_watch_signals_subject`, `ix_watch_signals_owner`).

Une église de cinq mille membres payait donc cent fois le prix d'une église de cinquante pour
écrire la même présence. Et à la reprojection, ce chargement est **dans la boucle** : le coût
devenait quadratique sur l'opération qu'on lance précisément quand quelque chose est déjà cassé.

La mesure retenue ici est le **nombre d'appels au dépôt**, pas la durée. C'est l'invariant qu'on
veut tenir — *le coût d'un fait ne dépend plus du nombre de membres* — il est déterministe, et il
ne peut pas passer au vert par accident sur une petite fixture.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.attendance.domain.enums import (
    AbsenceReason,
    AbsenceSource,
    WatchExclusionReason,
)
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.attendance.domain.watch_exclusion import WatchExclusion
from app.contexts.watch.application.intake import Intake, load_full_state, load_state
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.presence_recorded import PresenceRecordedV1
from app.contexts.watch.application.interpreters.third_party_concern import (
    ThirdPartyConcernV1,
)
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.errors import StateScopeError
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.registry import ATTENDANCE, WATCH_UI, default_registry
from app.contexts.watch.domain.signal import Signal, SignalStatus
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 5, 1, tzinfo=UTC)

# Les lectures qui balaient une église entière. Aucune ne doit se produire sur le chemin d'un fait.
_TENANT_WIDE = {"excluded_subject_ids", "open_neutralizations", "live_cases"}


class _Counting:
    """Compte les appels au dépôt sans rien changer à son comportement."""

    def __init__(self, inner):
        self._inner = inner
        self.calls: Counter = Counter()

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        async def counted(*args, **kwargs):
            self.calls[name] += 1
            return await attr(*args, **kwargs)

        return counted

    @property
    def tenant_wide(self) -> int:
        return sum(n for name, n in self.calls.items() if name in _TENANT_WIDE)

    @property
    def total(self) -> int:
        return sum(self.calls.values())


def _neutralization(*, tenant, member, days=30):
    """Posée par une annonce — c'est ce qui en fait une neutralisation, pas un drapeau."""
    return PlannedAbsence(
        id=uuid4(), tenant_id=tenant, account_id=member,
        from_date=_NOW - timedelta(days=1), to_date=_NOW + timedelta(days=days),
        reason=AbsenceReason.FAMILY, source=AbsenceSource.ANNOUNCEMENT,
        declared_by_account_id=uuid4(), declared_at=_NOW, source_ref=uuid4(),
    )


def _case(*, tenant, member, owner, status=SignalStatus.ASSIGNED, origin=CasePriority.ABSENCE):
    return Signal(
        id=uuid4(), tenant_id=tenant, subject_id=member, origin=origin,
        reason="Sans nouvelles.", opened_at=_NOW - timedelta(days=7),
        status=status, owner_account_id=owner,
    )


def _presence_fact(*, tenant, member):
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=ATTENDANCE, kind=FactKind.PRESENCE_RECORDED,
        subject_kind=SubjectKind.PERSON, subject_id=member,
        payload={"gathering_id": str(uuid4())},
    )


def _concern_fact(*, tenant, member, owner):
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=WATCH_UI, kind=FactKind.THIRD_PARTY_CONCERN,
        subject_kind=SubjectKind.PERSON, subject_id=member,
        payload={"owner_account_id": str(owner)},
        consent=ConsentProof(given_by=uuid4(), scope=ConsentScope.SPEAK_FOR_ANOTHER,
                             given_at=_NOW),
    )


def _populated_church(*, size, tenant, owner):
    """Une église peuplée : des cas ouverts, des neutralisations, des retirés de la veille."""
    signals, absences, exclusions = FakeSignals(), FakeAbsences(), FakeExclusions()
    for _ in range(size):
        other = uuid4()
        signals.rows.append(_case(tenant=tenant, member=other, owner=owner))
        absences.rows.append(_neutralization(tenant=tenant, member=other))
    return signals, absences, exclusions


def _engine(signals, absences, exclusions, *, interpreters=None):
    store = _Counting(AttendanceNeutralizationStore(absences, exclusions))
    counted_signals = _Counting(signals)
    registry = interpreters or InterpreterRegistry()
    intake = Intake(
        FakeLedger(), default_registry(), registry, store, counted_signals
    )
    return intake, store, counted_signals


# --- 1. Le coût d'un fait ne dépend plus de la taille de l'église ------------------------


async def test_a_fact_costs_the_same_in_a_church_of_fifty_and_of_five_thousand():
    """La clause d'arrêt du lot, mesurée là où elle veut dire quelque chose.

    Si ce test échoue un jour, ce n'est pas une régression de performance : c'est que le chemin
    d'un fait a recommencé à lire toute l'église."""
    tenant, owner = uuid4(), uuid4()
    interpreters = InterpreterRegistry()
    interpreters.register(PresenceRecordedV1())

    counts = []
    for size in (10, 1_000):
        signals, absences, exclusions = _populated_church(
            size=size, tenant=tenant, owner=owner
        )
        intake, store, counted = _engine(
            signals, absences, exclusions, interpreters=interpreters
        )
        await intake.submit(_presence_fact(tenant=tenant, member=uuid4()))
        counts.append((store.calls, counted.calls, store.tenant_wide + counted.tenant_wide))

    small, big = counts[0], counts[1]
    assert small[0] == big[0] and small[1] == big[1]  # exactement les mêmes lectures
    assert small[2] == big[2] == 0  # et aucune ne balaie l'église


async def test_the_pointed_reads_are_at_most_four():
    """Quatre questions, pas une de plus — et en pratique trois quand rien ne s'ouvre."""
    tenant = uuid4()
    interpreters = InterpreterRegistry()
    interpreters.register(PresenceRecordedV1())
    signals, absences, exclusions = _populated_church(size=50, tenant=tenant, owner=uuid4())
    intake, store, counted = _engine(
        signals, absences, exclusions, interpreters=interpreters
    )

    await intake.submit(_presence_fact(tenant=tenant, member=uuid4()))

    assert store.calls["is_excluded"] == 1
    assert store.calls["neutralizations_of_subject"] == 1
    assert counted.calls["case_of_subject"] == 1
    assert store.total + counted.total <= 4


# --- 2. La vue réduite répond comme la vue complète --------------------------------------


@pytest.mark.parametrize("excluded", [False, True])
@pytest.mark.parametrize("neutralized", [False, True])
@pytest.mark.parametrize("with_case", [False, True])
async def test_the_reduced_view_answers_exactly_like_the_materialized_one(
    excluded, neutralized, with_case
):
    """L'équivalence est la seule preuve qui vaille : mêmes données, mêmes réponses.

    Elle est vérifiée sur les huit combinaisons de ce qu'une personne peut porter — retirée de la
    veille, sous neutralisation, avec un cas en cours."""
    tenant, member, owner = uuid4(), uuid4(), uuid4()
    signals, absences, exclusions = _populated_church(size=20, tenant=tenant, owner=owner)
    if neutralized:
        absences.rows.append(_neutralization(tenant=tenant, member=member))
    if with_case:
        signals.rows.append(_case(tenant=tenant, member=member, owner=owner))
    if excluded:
        exclusions.rows.append(
            WatchExclusion(
                id=uuid4(), account_id=member, tenant_id=tenant,
                reason=WatchExclusionReason.DECEASED, excluded_at=_NOW,
                declared_by_account_id=uuid4(), source_ref=uuid4(),
            )
        )

    store = AttendanceNeutralizationStore(absences, exclusions)
    fact = _presence_fact(tenant=tenant, member=member)

    reduced = await load_state(store, signals, fact)
    full = await load_full_state(store, signals, tenant)

    assert reduced.is_excluded(member) == full.is_excluded(member)
    assert reduced.has_open_case(member) == full.has_open_case(member)
    assert reduced.owner_of(member) == full.owner_of(member)
    assert [n.id for n in reduced.neutralizations_of(member)] == [
        n.id for n in full.neutralizations_of(member)
    ]
    reduced_case, full_case = reduced.case_of(member), full.case_of(member)
    assert (reduced_case is None) == (full_case is None)
    if full_case is not None:
        assert reduced_case.id == full_case.id
        assert reduced_case.owner_id == full_case.owner_id
        assert reduced_case.is_held == full_case.is_held


# --- 3. La portée : une question sur un tiers ne peut pas recevoir une réponse vide -------


async def test_asking_the_reduced_view_about_someone_else_raises():
    """Un interpreter n'a jamais eu de raison légitime de regarder quelqu'un d'autre.

    Avant, la vue portait toute l'église : la question aurait eu une vraie réponse. Maintenant elle
    en aurait une **vide**, et l'interpreter se tromperait en silence. La règle devient un type."""
    tenant, member = uuid4(), uuid4()
    signals, absences, exclusions = _populated_church(size=5, tenant=tenant, owner=uuid4())
    store = AttendanceNeutralizationStore(absences, exclusions)
    state = await load_state(store, signals, _presence_fact(tenant=tenant, member=member))

    with pytest.raises(StateScopeError):
        state.is_excluded(uuid4())
    with pytest.raises(StateScopeError):
        state.has_open_case(uuid4())
    with pytest.raises(StateScopeError):
        state.neutralizations_of(uuid4())


async def test_the_full_view_answers_about_anyone():
    """La vue complète, elle, n'est pas bornée : elle sert les usages qui lisent une église."""
    tenant, member = uuid4(), uuid4()
    signals, absences, exclusions = _populated_church(size=5, tenant=tenant, owner=uuid4())
    store = AttendanceNeutralizationStore(absences, exclusions)

    full = await load_full_state(store, signals, tenant)

    assert full.is_excluded(member) is False  # une réponse, pas une erreur


# --- 4. Le plafond de débit tient toujours (l'écart le plus dangereux du lot) -------------


async def test_the_debit_cap_still_holds_with_a_subject_scoped_view():
    """La vue est bornée au **sujet** ; le plafond compte les cas du **propriétaire**.

    Livrés naïvement, le compteur aurait répondu zéro : le plafond n'aurait plus rien retenu, un
    responsable aurait pu recevoir trente cas dans la soirée, et aucun test n'aurait rougi. D'où
    l'ordre : résoudre les destinataires, précharger leur budget, **puis** arbitrer."""
    tenant, lead, member = uuid4(), uuid4(), uuid4()
    interpreters = InterpreterRegistry()
    interpreters.register(ThirdPartyConcernV1())
    signals, absences, exclusions = FakeSignals(), FakeAbsences(), FakeExclusions()
    for _ in range(5):  # le responsable est déjà au plafond par défaut
        signals.rows.append(_case(tenant=tenant, member=uuid4(), owner=lead))
    intake, *_ = _engine(signals, absences, exclusions, interpreters=interpreters)

    result = await intake.submit(_concern_fact(tenant=tenant, member=member, owner=lead))

    assert result.arbitration.held  # détecté, retenu — pas émis
    opened = next(s for s in signals.rows if s.subject_id == member)
    assert opened.status is SignalStatus.HELD


async def test_a_case_still_passes_when_the_owner_is_under_the_cap():
    """Le pendant : sous le plafond, le cas sort. Sinon le test précédent ne prouverait rien."""
    tenant, lead, member = uuid4(), uuid4(), uuid4()
    interpreters = InterpreterRegistry()
    interpreters.register(ThirdPartyConcernV1())
    signals, absences, exclusions = FakeSignals(), FakeAbsences(), FakeExclusions()
    for _ in range(2):
        signals.rows.append(_case(tenant=tenant, member=uuid4(), owner=lead))
    intake, *_ = _engine(signals, absences, exclusions, interpreters=interpreters)

    result = await intake.submit(_concern_fact(tenant=tenant, member=member, owner=lead))

    assert not result.arbitration.held
    opened = next(s for s in signals.rows if s.subject_id == member)
    assert opened.status is SignalStatus.ASSIGNED
