"""Le geste posé — *« Sans nouvelles depuis 3 rencontres. Quelqu'un de l'église lui a rendu
visite le 3 août. »*

Même histoire que le signe de vie, un cran plus loin : tout le mécanisme existait — `record_gesture`
sans appelant, `gestures_count` figé à zéro, un garde de reprojection qui protégeait des gestes que
rien n'écrivait — et le contrat de fait réservait le nom depuis le premier jour. Il manquait la
porte.

Ces tests vérifient le chaînon, et surtout les trois choses qu'il **refuse** de faire : ouvrir un
cas, éteindre un cas, écrire pourquoi.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.declare_gesture import DeclareGesture
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.gesture_done import GestureDoneV1
from app.contexts.watch.application.interpreters.gratitude_deposited import (
    GratitudeDepositedV1,
)
from app.contexts.watch.calibration.judge import GESTURE_PRECEDES_WINDOW, OutcomeJudge
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.errors import (
    ConcernRefusedError,
    ConsentRequiredError,
    FactKindNotAllowedError,
    SelfGestureError,
)
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.gesture import GestureKind
from app.contexts.watch.domain.parameters import DEFAULTS
from app.contexts.watch.domain.registry import COMPANION, WATCH_UI, default_registry
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from app.contexts.watch.domain.transparency import is_listable_to_subject
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 8, 3, tzinfo=UTC)  # un 3 août


def _engine(signals=None, *, ledger=None):
    interpreters = InterpreterRegistry()
    interpreters.register(GestureDoneV1())
    interpreters.register(GratitudeDepositedV1())
    signals = signals if signals is not None else FakeSignals()
    ledger = ledger if ledger is not None else FakeLedger()
    intake = Intake(
        ledger, default_registry(), interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals,
    )
    return intake, signals


def _gesture_fact(tenant, subject, jean, *, kind=GestureKind.VISIT, source=COMPANION, fact_id=None):
    return Fact(
        fact_id=fact_id or uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=source, kind=FactKind.GESTURE_DONE,
        subject_kind=SubjectKind.PERSON, subject_id=subject,
        payload={"kind": kind.value},
        consent=ConsentProof(
            given_by=jean, scope=ConsentScope.SPEAK_FOR_ANOTHER, given_at=_NOW
        ),
    )


def _case(signals, *, tenant, member, status=SignalStatus.ASSIGNED, origin=CasePriority.ABSENCE):
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=member, origin=origin,
        reason="Sans nouvelles — 3 rencontres de la cellule Bethel.",
        opened_at=_NOW - timedelta(days=21), status=status,
        owner_account_id=uuid4(), priority=CasePriority.CONCERN,
        held_reason="cap" if status is SignalStatus.HELD else None,
    )
    signals.rows.append(case)
    return case


# --- La porte -----------------------------------------------------------------------------


def test_the_companion_may_now_declare_a_gesture_and_the_leader_screen_may_not():
    """La porte s'ouvre sur le **compagnon** seulement.

    L'écran du responsable a déjà `CASE_ACTIONS` pour dire ce qu'il fait sur un cas. Lui donner en
    plus le geste du membre mélangerait deux choses que le produit sépare depuis le début : dire ce
    qu'on a fait pour quelqu'un, et dire ce qu'on fait de son travail."""
    registry = default_registry()

    assert registry.accepts(COMPANION, FactKind.GESTURE_DONE)
    assert not registry.accepts(WATCH_UI, FactKind.GESTURE_DONE)


async def test_a_gesture_from_an_unauthorised_surface_is_refused():
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    intake, _ = _engine()

    with pytest.raises(FactKindNotAllowedError):
        await intake.submit(_gesture_fact(tenant, sondet, jean, source=WATCH_UI))


async def test_a_gesture_without_consent_never_enters():
    """`SPEAK_FOR_ANOTHER`, comme le signalement — et ce n'est pas la permission du sujet.

    C'est l'engagement de celui qui parle. Sans elle, n'importe quel service pourrait déclarer des
    visites au nom de gens qui n'ont rien fait."""
    tenant, sondet = uuid4(), uuid4()
    intake, _ = _engine()
    sans_preuve = Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=COMPANION, kind=FactKind.GESTURE_DONE,
        subject_kind=SubjectKind.PERSON, subject_id=sondet,
        payload={"kind": GestureKind.VISIT.value},
    )

    with pytest.raises(ConsentRequiredError):
        await intake.submit(sans_preuve)


# --- Ce qu'il fait ------------------------------------------------------------------------


async def test_a_gesture_annotates_the_case_and_counts_without_naming_anyone():
    """Le responsable lit la visite **avant** de décrocher — c'est tout l'objet du lot.

    Il sait alors deux choses : que la personne n'est pas seule, et qu'il peut fermer sur *« on
    sait, quelqu'un s'en occupe déjà »* plutôt que sur *« j'ai pris contact, tout allait bien »* —
    la seule issue du vocabulaire qui dise à la calibration que la détection s'est trompée.

    Et l'annotation ne nomme personne : nommer celui qui est passé est utile, mais c'est le
    **lien**, et le lien vient avec ses propres gardes."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _ = _engine(signals)
    case = _case(signals, tenant=tenant, member=sondet)

    await intake.submit(_gesture_fact(tenant, sondet, jean))

    assert case.annotations == ["Quelqu'un de l'église lui a rendu visite le 3 août."]
    assert case.gestures_count == 1
    assert case.is_live  # il informe, il ne ferme pas
    assert str(jean) not in " ".join(case.annotations)


async def test_the_gesture_pushes_the_case_under_those_nobody_has_news_of():
    """Quelqu'un y est allé : ça passe après ceux vers qui personne n'est allé.

    La descente s'arrête au plancher — sur un cas déjà en priorité `ABSENCE`, elle ne veut rien
    dire et ne fait rien. Ce qui libère la place du responsable n'est pas un rang recalculé, c'est
    lui qui referme le cas en sachant."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _ = _engine(signals)
    case = _case(signals, tenant=tenant, member=sondet)  # priorité CONCERN au départ

    await intake.submit(_gesture_fact(tenant, sondet, jean))

    assert case.priority is CasePriority.ABSENCE


async def test_a_case_she_asked_for_herself_never_goes_down_because_someone_visited():
    """**Ce qu'elle a demandé passe avant ce qu'on a fait pour elle.**

    Quelqu'un qui demande un appel *et* reçoit une visite a toujours demandé un appel. Sans ce
    garde, le produit ferait redescendre sa propre parole derrière tout le monde."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _ = _engine(signals)
    case = _case(signals, tenant=tenant, member=sondet, origin=CasePriority.DECLARED)
    case.priority = CasePriority.DECLARED

    await intake.submit(_gesture_fact(tenant, sondet, jean))

    assert case.priority is CasePriority.DECLARED
    assert case.gestures_count == 1  # le geste est compté quand même


# --- Ce qu'il refuse de faire, et qui compte davantage ---------------------------------------


async def test_a_gesture_on_nobody_watched_opens_nothing_at_all():
    """**Prendre des nouvelles ne doit jamais ficher la personne.**

    Sans cas vivant, il ne se passe rien : pas d'ouverture, pas de mémoire, rien. Le fait reste au
    journal — quelqu'un a pris soin de quelqu'un qui n'était pas en veille, c'est une bonne
    nouvelle et pas un événement de veille."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    ledger = FakeLedger()
    signals = FakeSignals()
    intake, _ = _engine(signals, ledger=ledger)

    await intake.submit(_gesture_fact(tenant, sondet, jean))

    assert signals.rows == []
    assert [f.kind for f in ledger.rows] == [FactKind.GESTURE_DONE]


async def test_a_gesture_never_retracts_a_held_case_where_a_life_sign_would():
    """**L'asymétrie centrale du lot**, vérifiée par le contraste.

    Un signe de vie est la personne qui parle d'elle-même : sur un cas encore retenu, que personne
    n'avait lu, l'arbitrage le rétracte. Un geste est quelqu'un d'autre qui rapporte ce qu'il a
    fait — et ce que Jean a constaté chez Sondet n'est pas ce que Sondet dit de lui-même.

    Le jour où cette assertion tombe, un tiers peut faire taire un cas avec sa propre impression."""
    tenant, sondet, awa, jean = uuid4(), uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _ = _engine(signals)
    retenu_sondet = _case(signals, tenant=tenant, member=sondet, status=SignalStatus.HELD)
    retenu_awa = _case(signals, tenant=tenant, member=awa, status=SignalStatus.HELD)

    await intake.submit(_gesture_fact(tenant, sondet, jean))
    await intake.submit(
        Fact(
            fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
            source=COMPANION, kind=FactKind.GRATITUDE_DEPOSITED,
            subject_kind=SubjectKind.PERSON, subject_id=awa, payload={},
        )
    )

    assert retenu_sondet.is_held  # le geste d'un tiers ne retire rien
    assert retenu_awa.status is SignalStatus.RETRACTED  # sa propre parole, si


def test_the_subject_cannot_list_the_gesture_a_third_party_declared():
    """La personne sait très bien qu'on lui a rendu visite — ce n'est pas un secret.

    Mais ce fait décrit **l'engagement de celui qui est venu**, pas elle : la règle positive de la
    transparence dit que lui appartient ce qui découle de ses propres actes, et recevoir n'est pas
    agir. La frontière ne se négocie pas fait par fait, sinon elle redevient une liste
    d'exceptions."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()

    assert not is_listable_to_subject(_gesture_fact(tenant, sondet, jean))


def test_there_is_nowhere_to_write_why():
    """*« Je suis passé le voir »*, pas *« parce qu'il est malade »*.

    Le payload ne porte **que** la nature du geste. Le motif appartient à la personne : c'est à
    elle de le déclarer, ou à l'église de le publier. Un tiers qui pourrait l'écrire construirait
    un dossier de santé tenu par les voisins, et il survivrait à tous ceux qui l'ont écrit."""
    fact = _gesture_fact(uuid4(), uuid4(), uuid4())

    assert set(fact.payload) == {"kind"}


# --- Le rejeu, et le garde qu'il libère ------------------------------------------------------


async def test_replaying_the_same_fact_does_not_count_a_second_gesture():
    """L'idempotence est portée par la déduplication sur `source_ref`, pas par un compteur à part.

    Sans elle, chaque reprojection empilerait un geste de plus — et le nombre finirait par dire
    l'histoire des rejeux plutôt que celle de l'église."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _ = _engine(signals)
    case = _case(signals, tenant=tenant, member=sondet)
    fact_id = uuid4()

    await intake.submit(_gesture_fact(tenant, sondet, jean, fact_id=fact_id))
    await intake.submit(_gesture_fact(tenant, sondet, jean, fact_id=fact_id))

    assert case.gestures_count == 1


# --- Ce que la calibration en apprend ----------------------------------------------------------


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


def _closed_absence(signals, *, tenant, member, outcome, opened_at):
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=member, origin=CasePriority.ABSENCE,
        reason="Sans nouvelles — 3 rencontres de la cellule Bethel.", opened_at=opened_at,
    )
    case.close(outcome=outcome, at=_NOW, closed_by_account_id=uuid4())
    signals.rows.append(case)
    return case


async def _truth(signals, tenant):
    return await OutcomeJudge(signals, _Params(), clock=lambda: _NOW).execute(
        tenant_id=tenant
    )


async def test_a_confirmed_absence_on_someone_already_visited_says_the_engine_was_slow():
    """**La boucle du geste se referme ici.**

    Quelqu'un est allé voir Sondet pendant que les seuils comptaient encore, et il y avait bien
    quelque chose. C'est la définition exacte de *« un humain a vu avant le moteur »* — en plus
    fort que l'inquiétude, puisque le déclarant ne s'est pas contenté de ressentir.

    Sans cette mesure, le geste entrait au journal depuis G-1 et la calibration ne le voyait pas :
    les églises les plus fraternelles restaient celles dont on ne mesurait jamais la lenteur."""
    tenant, sondet = uuid4(), uuid4()
    signals = FakeSignals()
    ouvert = _NOW - timedelta(days=5)
    _closed_absence(
        signals, tenant=tenant, member=sondet,
        outcome=SignalOutcome.FOLLOWED, opened_at=ouvert,
    )
    signals.gestures = [(sondet, ouvert - timedelta(days=3))]

    truth = await _truth(signals, tenant)

    assert truth.missed_detections == 1


async def test_a_visit_followed_by_nothing_to_report_is_just_ordinary_friendship():
    """**Le garde qui empêche de faire baisser les seuils sur du vide.**

    Une visite suivie d'un cas clos sur « j'ai pris contact, tout allait bien » n'est pas une
    détection manquée : c'est quelqu'un qui est passé voir un ami. Compter ça dirait au moteur
    qu'il est trop lent chaque fois que l'église se porte bien."""
    tenant, sondet = uuid4(), uuid4()
    signals = FakeSignals()
    ouvert = _NOW - timedelta(days=5)
    _closed_absence(
        signals, tenant=tenant, member=sondet,
        outcome=SignalOutcome.NOTHING_TO_REPORT, opened_at=ouvert,
    )
    signals.gestures = [(sondet, ouvert - timedelta(days=3))]

    truth = await _truth(signals, tenant)

    assert truth.missed_detections == 0


async def test_a_visit_too_old_no_longer_explains_todays_silence():
    """La fenêtre est celle du bloc de restitution, importée et non réécrite.

    Le responsable ne doit pas lire une visite que la calibration ignore, ni l'inverse : deux
    constantes auraient divergé, et l'écart aurait été invisible des deux côtés."""
    tenant, sondet = uuid4(), uuid4()
    signals = FakeSignals()
    ouvert = _NOW - timedelta(days=5)
    _closed_absence(
        signals, tenant=tenant, member=sondet,
        outcome=SignalOutcome.FOLLOWED, opened_at=ouvert,
    )
    signals.gestures = [(sondet, ouvert - GESTURE_PRECEDES_WINDOW - timedelta(days=1))]

    truth = await _truth(signals, tenant)

    assert truth.missed_detections == 0


async def test_three_visits_before_one_case_are_one_missed_detection_not_three():
    """C'est **un cas** qu'on a manqué, pas trois. Le rapprochement est un `EXISTS`, pas un compte.

    Et le nombre de visites n'est attaché à personne : ce serait le compteur d'engagement que le
    produit s'interdit depuis le début."""
    tenant, sondet = uuid4(), uuid4()
    signals = FakeSignals()
    ouvert = _NOW - timedelta(days=5)
    _closed_absence(
        signals, tenant=tenant, member=sondet,
        outcome=SignalOutcome.FOLLOWED, opened_at=ouvert,
    )
    signals.gestures = [(sondet, ouvert - timedelta(days=d)) for d in (2, 5, 9)]

    truth = await _truth(signals, tenant)

    assert truth.missed_detections == 1


# --- La commande --------------------------------------------------------------------------


async def test_declaring_a_gesture_on_oneself_is_refused():
    """Un geste se pose **pour un autre**. Ce qu'on fait pour soi a déjà ses portes."""
    tenant, jean = uuid4(), uuid4()
    intake, signals = _engine()
    command = DeclareGesture(
        intake, signals,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        clock=lambda: _NOW,
    )

    with pytest.raises(SelfGestureError):
        await command.execute(
            actor_account_id=jean, subject_account_id=jean,
            tenant_id=tenant, gesture=GestureKind.VISIT,
        )


async def test_a_gesture_is_refused_on_someone_who_asked_us_to_stop():
    """Cette parole est absorbante : aucune bonne intention ne la reprend, pas même une visite."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _ = _engine(signals)
    case = _case(signals, tenant=tenant, member=sondet)
    case.close(
        outcome=SignalOutcome.DO_NOT_CONTACT, at=_NOW, closed_by_account_id=uuid4()
    )
    command = DeclareGesture(
        intake, signals,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        clock=lambda: _NOW,
    )

    with pytest.raises(ConcernRefusedError):
        await command.execute(
            actor_account_id=jean, subject_account_id=sondet,
            tenant_id=tenant, gesture=GestureKind.CALL,
        )


async def test_the_acknowledgement_says_thank_you_and_nothing_else():
    """Ni compteur, ni récapitulatif, ni « c'est le 4ᵉ ce mois-ci ».

    Un geste qu'on félicite devient un geste qu'on pose pour être félicité — et le produit a déjà
    tranché que la contrepartie est ailleurs : personne ne rappellera Sondet pour rien."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _ = _engine(signals)
    _case(signals, tenant=tenant, member=sondet)
    command = DeclareGesture(
        intake, signals,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        clock=lambda: _NOW,
    )

    ack = await command.execute(
        actor_account_id=jean, subject_account_id=sondet,
        tenant_id=tenant, gesture=GestureKind.HELP,
    )

    assert ack.message == "Merci."
    assert not hasattr(ack, "count")
