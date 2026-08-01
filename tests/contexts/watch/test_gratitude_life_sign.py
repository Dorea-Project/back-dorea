"""Le signe de vie — *« absente depuis 4 semaines, a déposé un sujet de reconnaissance
le 12 avril »*.

Tout ce mécanisme existait depuis longtemps et **n'avait aucun émetteur** : la rétractation d'un
cas encore retenu, la baisse de priorité, l'invariant qui interdit une cause de clôture « signe de
vie ». Ces tests vérifient le chaînon, et surtout ce qu'il refuse de faire.

Ce qui se joue tient en une phrase de responsable. Sans l'annotation, il ouvre son appel par
« je vois que tu n'es pas venue » à quelqu'un qui vient précisément de donner de ses nouvelles.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.gratitude_deposited import (
    GratitudeDepositedV1,
)
from app.contexts.watch.domain.effects import CasePriority, ExtinguishCause
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import COMPANION, WATCH_UI, default_registry
from app.contexts.watch.domain.signal import (
    RetractionCause,
    Signal,
    SignalStatus,
)
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 4, 12, tzinfo=UTC)  # un 12 avril


def _engine(signals=None):
    interpreters = InterpreterRegistry()
    interpreters.register(GratitudeDepositedV1())
    signals = signals if signals is not None else FakeSignals()
    intake = Intake(
        FakeLedger(), default_registry(), interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals,
    )
    return intake, signals


def _gratitude(tenant, member, *, source=COMPANION):
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=source, kind=FactKind.GRATITUDE_DEPOSITED,
        subject_kind=SubjectKind.PERSON, subject_id=member,
        payload={"subject": "Mon fils a retrouvé du travail."},
    )


def _case(signals, *, tenant, member, status=SignalStatus.ASSIGNED):
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=member, origin=CasePriority.ABSENCE,
        reason="Sans nouvelles — 4 rencontres de la cellule Bethel.",
        opened_at=_NOW - timedelta(days=28), status=status,
        owner_account_id=uuid4(), priority=CasePriority.DEADLINE,
        held_reason="cap" if status is SignalStatus.HELD else None,
    )
    signals.rows.append(case)
    return case


# --- Ce qu'il fait ------------------------------------------------------------------------


async def test_it_annotates_the_case_with_the_date_and_nothing_else():
    """La phrase que le responsable lit avant d'appeler — et **pas ce qui a été écrit**.

    Une reconnaissance est adressée à Dieu, pas au responsable de cellule. Un contenu intime qui
    réapparaît sur l'écran de quelqu'un d'autre est exactement la fuite que le produit ferme."""
    tenant, member = uuid4(), uuid4()
    intake, signals = _engine()
    case = _case(signals, tenant=tenant, member=member)

    await intake.submit(_gratitude(tenant, member))

    assert "a déposé un sujet de reconnaissance le 12 avril" in " ".join(
        case.annotations
    ).lower()
    assert not any("travail" in a for a in case.annotations)  # le texte ne remonte pas


async def test_it_lowers_the_priority_without_closing_anything():
    """**Abaisser, pas éteindre.** Le responsable rappellera — après ceux dont personne n'a de
    nouvelles.

    Éteindre le cas là-dessus serait la même erreur que fermer un deuil parce que la personne est
    venue au culte : confondre une présence avec un état."""
    tenant, member = uuid4(), uuid4()
    intake, signals = _engine()
    case = _case(signals, tenant=tenant, member=member)

    await intake.submit(_gratitude(tenant, member))

    assert case.priority is CasePriority.ABSENCE  # descendu depuis DEADLINE
    assert case.status is SignalStatus.ASSIGNED  # toujours vivant
    assert case.outcome is None


async def test_a_case_nobody_had_seen_yet_is_retracted():
    """Un cas encore retenu, que personne n'avait lu et sur lequel aucune promesse n'avait été
    faite : faire appeler quelqu'un qui vient de donner de ses nouvelles serait le contraire de
    ce qu'on cherche.

    Et ce n'est pas une clôture : rien n'a été résolu, donc rien n'entre dans les métriques."""
    tenant, member = uuid4(), uuid4()
    intake, signals = _engine()
    case = _case(signals, tenant=tenant, member=member, status=SignalStatus.HELD)

    await intake.submit(_gratitude(tenant, member))

    assert case.status is SignalStatus.RETRACTED
    assert case.retraction_cause == RetractionCause.SUPERSEDED_BY_LIFE_SIGN.value
    assert case.counts_as_resolved is False


async def test_what_she_asked_for_outranks_what_she_tells():
    """**Un cas né de sa propre parole ne redescend pas parce qu'elle rend grâce par ailleurs.**

    Sans ce garde, quelqu'un qui demande « rappelez-moi » *et* dépose un merci se retrouve
    derrière tout le monde : le produit punirait la gratitude, alors qu'il existe pour l'inverse.
    """
    tenant, member = uuid4(), uuid4()
    intake, signals = _engine()
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=member, origin=CasePriority.DECLARED,
        reason="Rappelez-moi.", opened_at=_NOW - timedelta(days=3),
        status=SignalStatus.ASSIGNED, owner_account_id=uuid4(),
        priority=CasePriority.DECLARED,
    )
    signals.rows.append(case)

    await intake.submit(_gratitude(tenant, member))

    assert case.priority is CasePriority.DECLARED  # sa demande reste en tête de file
    assert any("reconnaissance" in a for a in case.annotations)  # et le signe est bien noté


# --- Ce qu'il ne fait jamais --------------------------------------------------------------


async def test_someone_who_is_doing_well_produces_nothing_at_all():
    """Rendre grâce n'ouvre aucun cas. C'est le contraire d'un motif de soin — et l'application
    n'a rien de plus à en dire que « merci »."""
    tenant, member = uuid4(), uuid4()
    intake, signals = _engine()

    result = await intake.submit(_gratitude(tenant, member))

    assert result.accepted is True  # le fait est au journal
    assert signals.rows == []  # et il n'en sort rien


def test_no_life_sign_closure_cause_exists():
    """Un invariant du produit, revérifié ici parce que c'est ce fichier qui pourrait le tenter.

    Déposer une reconnaissance prouve qu'on est vivant, pas qu'on est revenu en cellule."""
    assert not any("life" in cause.value for cause in ExtinguishCause)


def test_only_the_companion_may_deposit_it():
    """L'asymétrie est le fond du sujet : une reconnaissance ne se dépose qu'à la **première
    personne**.

    Un responsable qui pourrait déposer « elle va bien » à la place de quelqu'un ferait taire un
    cas avec sa propre impression."""
    registry = default_registry()

    assert registry.accepts(COMPANION, FactKind.GRATITUDE_DEPOSITED) is True
    assert registry.accepts(WATCH_UI, FactKind.GRATITUDE_DEPOSITED) is False
    # Et le canal d'inquiétude du compagnon n'a pas été perdu en chemin.
    assert registry.accepts(COMPANION, FactKind.THIRD_PARTY_CONCERN) is True
