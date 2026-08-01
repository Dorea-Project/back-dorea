"""Le signalement par un tiers — l'intuition du responsable, le « je pense à quelqu'un » du membre.

Jean sait déjà, et il n'a rien fait, parce que **savoir ne crée aucune obligation**. Le geste ne
transporte aucune information nouvelle : il convertit un savoir privé en un cas daté, attribué,
qu'il faudra fermer. Ces tests protègent surtout ce que le module **ne fait pas**.
"""

import ast
import pathlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.arbitration import ArbitrationPolicy, arbitrate
from app.contexts.watch.application.concern_watchdog import (
    EscalateStaleConcerns,
    GuardAgainstDumping,
    MeasureConcernPrecision,
)
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import (
    InterpreterRegistry,
    LiveCaseView,
    WatchStateView,
)
from app.contexts.watch.application.interpreters.third_party_concern import (
    SELF_ENGAGEMENT,
    SOMEONE_THINKS_OF_THEM,
    ThirdPartyConcernV1,
)
from app.contexts.watch.application.raise_concern import RaiseConcern
from app.contexts.watch.application.referent_resolution import SignalOwner
from app.contexts.watch.domain.concern import (
    NUANCE_LABELS,
    Nuance,
    forbidden_nuance,
)
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import (
    CasePriority,
    CoverageGap,
    OpenCase,
)
from app.contexts.watch.domain.errors import ConcernRefusedError, SelfConcernError
from app.contexts.watch.domain.facts import FactKind
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam
from app.contexts.watch.domain.registry import COMPANION, WATCH_UI, default_registry
from app.contexts.watch.domain.signal import (
    Signal,
    SignalOutcome,
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

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


class _Owners:
    """Doublure de `ResolveSignalOwner` — jamais nul, sauf église sans destinataire."""

    def __init__(self, owner=None):
        self.owner = owner

    async def execute(self, *, person_id, tenant_id, at):
        return SignalOwner(self.owner) if self.owner is not None else None


class _Gaps:
    def __init__(self):
        self.rows: list[CoverageGapRecord] = []

    async def record_once(self, record):
        if any(
            r.gap is record.gap and r.subject_id == record.subject_id and r.is_open
            for r in self.rows
        ):
            return False
        self.rows.append(record)
        return True

    async def open_gaps(self, tenant_id):
        return [r for r in self.rows if r.tenant_id == tenant_id and r.is_open]


class _Params:
    async def get_int(self, tenant_id, param):
        return DEFAULTS[param]


def _store(absences=None, exclusions=None):
    return AttendanceNeutralizationStore(
        absences or FakeAbsences(), exclusions or FakeExclusions()
    )


def _raise_concern(signals, *, owner=None, store=None, ledger=None):
    registry = InterpreterRegistry()
    registry.register(ThirdPartyConcernV1())
    store = store or _store()
    intake = Intake(ledger or FakeLedger(), default_registry(), registry, store, signals)
    return RaiseConcern(intake, _Owners(owner), signals, store, clock=lambda: _NOW)


def _concern_case(*, tenant, subject, owner, opened_at=_NOW, contacted=None) -> Signal:
    return Signal(
        id=uuid4(), tenant_id=tenant, subject_id=subject, origin=CasePriority.CONCERN,
        reason=SOMEONE_THINKS_OF_THEM, opened_at=opened_at,
        status=SignalStatus.ASSIGNED, owner_account_id=owner, first_contact_at=contacted,
    )


# --- Bloc 1 : un seul fait, un vocabulaire fermé ------------------------------------------------


def test_there_is_only_one_kind_for_both_gestures():
    """L'intuition du responsable et le signalement du membre sont le **même** geste.

    Deux `FactKind` auraient divergé dans six mois : le cas du responsable n'est que le cas
    général replié sur lui-même, et c'est la résolution du propriétaire qui les réunit."""
    assert not hasattr(FactKind, "LEADER_INTUITION")
    assert FactKind.THIRD_PARTY_CONCERN in FactKind


def test_both_surfaces_speak_the_same_kind_for_this_gesture():
    """Un seul `FactKind` pour l'inquiétude, quelle que soit la surface d'où elle part.

    Le compagnon en porte un second — le sujet de reconnaissance — et l'écran du responsable ne
    l'aura jamais : c'est une parole à la **première personne**, et un responsable qui pourrait
    déposer « elle va bien » à la place de quelqu'un ferait taire un cas avec son impression."""
    registry = default_registry()
    for surface in (WATCH_UI, COMPANION):
        assert registry.accepts(surface, FactKind.THIRD_PARTY_CONCERN) is True
        # Aucune clé obligatoire : la nuance est optionnelle, et le propriétaire peut
        # légitimement manquer. Ce vide est la spécification, pas un oubli.
        assert registry.get(surface).required_payload_keys == frozenset()

    assert registry.get(WATCH_UI).kinds == frozenset({FactKind.THIRD_PARTY_CONCERN})
    assert registry.accepts(WATCH_UI, FactKind.GRATITUDE_DEPOSITED) is False


def test_no_nuance_describes_a_supposed_inner_state():
    """« M'a semblé triste », « paraît déprimé » : c'est une supposition, pas une observation.

    Écrite et conservée, elle devient une note sur quelqu'un — la même ligne que le vocabulaire
    proscrit du ledger. Le grillage balaie l'enum entier, donc l'oubli est impossible."""
    for nuance, label in NUANCE_LABELS.items():
        assert not forbidden_nuance(nuance.value), nuance
        assert not forbidden_nuance(label), label

    # Le grillage attrape bien ce qu'il vise, sinon il ne protégerait rien.
    assert forbidden_nuance("seems_sad")
    assert forbidden_nuance("m'a semblé triste")


def test_there_is_no_free_text_anywhere_in_the_body():
    """Un champ libre sur une personne devient une fiche, et il survit à qui l'a écrite."""
    from app.contexts.watch.interface.schemas import RaiseConcernBody

    assert set(RaiseConcernBody.model_fields) == {"subject_account_id", "nuance"}


# --- Bloc 2 : le rôle de l'émetteur se dissout dans la résolution du propriétaire ---------------


async def test_the_emitter_who_owns_the_case_engages_himself():
    """« Je m'en occupe » déclare quelque chose **sur soi**, pas sur la personne.

    C'est ce qui règle le problème du diagnostic par construction : il n'y a rien à écrire sur
    quelqu'un, donc rien qui puisse devenir une fiche."""
    signals = FakeSignals()
    jean, awa, tenant = uuid4(), uuid4(), uuid4()

    await _raise_concern(signals, owner=jean).execute(
        emitter_account_id=jean, subject_account_id=awa, tenant_id=tenant
    )

    (case,) = signals.rows
    assert case.reason == SELF_ENGAGEMENT
    assert case.owner_account_id == jean
    assert case.status is SignalStatus.ASSIGNED  # le cas est sur ses épaules, daté


async def test_a_concern_from_someone_else_lands_on_the_referent():
    """Le cas revient au référent — et le déclarant n'est **jamais** nommé."""
    signals = FakeSignals()
    marie, jean, awa, tenant = uuid4(), uuid4(), uuid4(), uuid4()

    await _raise_concern(signals, owner=jean).execute(
        emitter_account_id=marie, subject_account_id=awa, tenant_id=tenant
    )

    (case,) = signals.rows
    assert case.reason == SOMEONE_THINKS_OF_THEM
    assert case.owner_account_id == jean
    assert str(marie) not in case.reason


async def test_the_nuance_travels_as_a_quote_for_whoever_comes_next():
    """Sans elle, celui qui reprend le cas après un transfert reçoit un cas **muet**."""
    signals = FakeSignals()
    marie, jean, awa, tenant = uuid4(), uuid4(), uuid4(), uuid4()

    await _raise_concern(signals, owner=jean).execute(
        emitter_account_id=marie, subject_account_id=awa, tenant_id=tenant,
        nuance=Nuance.NO_NEWS,
    )

    (case,) = signals.rows
    assert NUANCE_LABELS[Nuance.NO_NEWS] in case.reason


async def test_a_concern_still_enters_when_the_church_has_no_recipient():
    """Perdre l'inquiétude parce que l'église n'a configuré personne serait le faux silence.

    Le trou, lui, est consigné ailleurs — par la résolution du propriétaire."""
    signals = FakeSignals()
    marie, awa, tenant = uuid4(), uuid4(), uuid4()

    await _raise_concern(signals, owner=None).execute(
        emitter_account_id=marie, subject_account_id=awa, tenant_id=tenant
    )

    (case,) = signals.rows
    assert case.owner_account_id is None
    assert case.status is SignalStatus.OPEN


async def test_a_concern_on_someone_who_already_has_a_case_annotates_it():
    """Une personne n'a jamais deux cas — mais on doit voir que quelqu'un a pensé à elle."""
    signals = FakeSignals()
    marie, jean, awa, tenant = uuid4(), uuid4(), uuid4(), uuid4()
    signals.rows.append(
        Signal(
            id=uuid4(), tenant_id=tenant, subject_id=awa, origin=CasePriority.ABSENCE,
            reason="Sans nouvelles depuis 4 semaines.", opened_at=_NOW,
        )
    )

    await _raise_concern(signals, owner=jean).execute(
        emitter_account_id=marie, subject_account_id=awa, tenant_id=tenant
    )

    (case,) = signals.rows
    assert case.reason == "Sans nouvelles depuis 4 semaines."  # jamais réécrite
    assert any(SOMEONE_THINKS_OF_THEM in a for a in case.annotations)


# --- Bloc 3 : la non-rétention du déclarant -----------------------------------------------------


async def test_the_case_carries_nothing_that_names_the_declarant():
    """C'est ce qui sépare une **passation** d'une dénonciation.

    L'identité sert à l'intake — le fait exige une preuve de consentement à porter le souci
    d'autrui — puis elle n'est plus jointe à rien."""
    signals = FakeSignals()
    marie, jean, awa, tenant = uuid4(), uuid4(), uuid4(), uuid4()

    await _raise_concern(signals, owner=jean).execute(
        emitter_account_id=marie, subject_account_id=awa, tenant_id=tenant,
        nuance=Nuance.SOMETHING_CHANGED,
    )

    (case,) = signals.rows
    stored = " ".join([case.reason, *case.annotations, str(case.owner_account_id)])
    assert str(marie) not in stored
    assert not hasattr(case, "declared_by_account_id")
    assert not hasattr(case, "emitter_account_id")


def test_the_interpreter_reduces_the_declarant_to_a_boolean():
    """Le seul usage de son identité dans tout l'aval est un test d'égalité.

    Vérifié sur l'arbre syntaxique, pas par une lecture : `given_by` n'apparaît qu'une fois, et
    rien de ce qui est renvoyé ne permet de la reconstituer."""
    source = pathlib.Path(
        "app/contexts/watch/application/interpreters/third_party_concern.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "given_by"
    ]
    assert len(reads) == 1


def test_the_two_sentences_are_fixed_and_name_nobody():
    """L'interpreter ne sait pas écrire un nom — seulement choisir entre deux phrases."""
    for sentence in (SELF_ENGAGEMENT, SOMEONE_THINKS_OF_THEM):
        assert "{" not in sentence and "%s" not in sentence


# --- Bloc 4 (§4) : ce qui ne peut pas être émis --------------------------------------------------


async def test_signalling_yourself_is_a_declaration_not_a_concern():
    """Sinon sa propre demande d'aide entrerait dans le plafond, dont elle est exemptée."""
    signals = FakeSignals()
    jean, tenant = uuid4(), uuid4()

    with pytest.raises(SelfConcernError):
        await _raise_concern(signals, owner=jean).execute(
            emitter_account_id=jean, subject_account_id=jean, tenant_id=tenant
        )

    assert signals.rows == []


async def test_do_not_contact_blocks_the_emission():
    """« Ne me contactez plus » est une parole qu'aucune bonne intention ne reprend."""
    signals = FakeSignals()
    marie, awa, tenant = uuid4(), uuid4(), uuid4()
    closed = _concern_case(tenant=tenant, subject=awa, owner=marie)
    closed.close(outcome=SignalOutcome.DO_NOT_CONTACT, at=_NOW, closed_by_account_id=marie)
    signals.rows.append(closed)

    with pytest.raises(ConcernRefusedError):
        await _raise_concern(signals, owner=marie).execute(
            emitter_account_id=marie, subject_account_id=awa, tenant_id=tenant
        )


async def test_a_person_withdrawn_from_the_watch_receives_nothing():
    signals = FakeSignals()
    exclusions = FakeExclusions()
    marie, awa, tenant = uuid4(), uuid4(), uuid4()

    class _Excluded:
        account_id = awa
        tenant_id = tenant

    exclusions.rows.append(_Excluded())

    with pytest.raises(ConcernRefusedError):
        await _raise_concern(
            signals, owner=marie, store=_store(exclusions=exclusions)
        ).execute(emitter_account_id=marie, subject_account_id=awa, tenant_id=tenant)


# --- §6 : le plafond s'applique à cette origine, contrairement au déclaré ------------------------


def test_a_concern_waits_behind_the_cap_unlike_a_self_declaration():
    """Le déversoir : dix taps en trente secondes, conscience tranquille, personne d'appelé.

    Celui qui demande de l'aide passe devant tout ; celui qui s'organise reste dans la file."""
    jean = uuid4()
    saturated = tuple(
        LiveCaseView(id=uuid4(), subject_id=uuid4(), owner_id=jean, origin="absence")
        for _ in range(5)
    )
    state = WatchStateView(live_cases=saturated)
    concern = OpenCase(
        subject_id=uuid4(), reason=SELF_ENGAGEMENT, origin=CasePriority.CONCERN,
        opened_at=_NOW, owner_account_id=jean,
    )
    declared = OpenCase(
        subject_id=uuid4(), reason="A demandé qu'on l'appelle.",
        origin=CasePriority.DECLARED, opened_at=_NOW,
    )

    decided = arbitrate([concern, declared], state, policy=ArbitrationPolicy(open_cases_cap=5))

    assert decided.admitted == (declared,)
    assert decided.held == (concern,)  # retenu, pas perdu — réévalué chaque nuit


def test_a_third_party_word_outranks_a_computed_absence():
    """La priorité vient de l'origine du **dire**. Une parole vaut plus qu'un calcul."""
    state = WatchStateView()
    absence = OpenCase(
        subject_id=uuid4(), reason="silence", origin=CasePriority.ABSENCE, opened_at=_NOW
    )
    concern = OpenCase(
        subject_id=uuid4(), reason=SOMEONE_THINKS_OF_THEM,
        origin=CasePriority.CONCERN, opened_at=_NOW,
    )

    decided = arbitrate([absence, concern], state)

    assert [e.origin for e in decided.admitted] == [
        CasePriority.CONCERN,
        CasePriority.ABSENCE,
    ]


# --- Bloc 6 : l'escalade change de sujet ---------------------------------------------------------


async def test_the_escalation_targets_the_leader_never_the_member():
    """La seule source du produit où l'escalade change de sujet.

    Le pasteur n'a aucune base pour agir sur Awa — il sait seulement que Jean a ressenti quelque
    chose. Le problème n'est plus la personne, c'est l'engagement non tenu, et l'action du
    pasteur est d'appeler Jean."""
    signals, gaps = FakeSignals(), _Gaps()
    jean, awa, tenant = uuid4(), uuid4(), uuid4()
    late = _NOW - timedelta(days=DEFAULTS[WatchParam.CONCERN_ESCALATION_DAYS] + 2)
    signals.rows.append(_concern_case(tenant=tenant, subject=awa, owner=jean, opened_at=late))

    escalated = await EscalateStaleConcerns(
        signals, gaps, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant)

    assert escalated == [jean]
    (gap,) = gaps.rows
    assert gap.subject_id == jean  # le responsable
    assert gap.subject_id != awa
    assert gap.gap is CoverageGap.ENGAGEMENT_NOT_KEPT


async def test_the_escalation_is_worded_as_a_need_for_help():
    """Un responsable qui ne tient pas ses engagements est le plus souvent un responsable
    débordé. Jamais un reproche."""
    signals, gaps = FakeSignals(), _Gaps()
    jean, tenant = uuid4(), uuid4()
    late = _NOW - timedelta(days=20)
    signals.rows.append(
        _concern_case(tenant=tenant, subject=uuid4(), owner=jean, opened_at=late)
    )

    await EscalateStaleConcerns(signals, gaps, _Params(), clock=lambda: _NOW).execute(
        tenant_id=tenant
    )

    assert "besoin d'aide" in gaps.rows[0].reason


async def test_a_concern_already_contacted_never_escalates():
    """Un engagement tenu tard reste un engagement tenu."""
    signals, gaps = FakeSignals(), _Gaps()
    jean, tenant = uuid4(), uuid4()
    signals.rows.append(
        _concern_case(
            tenant=tenant, subject=uuid4(), owner=jean,
            opened_at=_NOW - timedelta(days=30), contacted=_NOW - timedelta(days=29),
        )
    )

    escalated = await EscalateStaleConcerns(
        signals, gaps, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant)

    assert escalated == []


async def test_an_unowned_concern_accuses_nobody():
    """Sans propriétaire il n'y a pas d'engagement à ne pas tenir : c'est un trou de couverture,
    déjà consigné ailleurs."""
    signals, gaps = FakeSignals(), _Gaps()
    tenant = uuid4()
    signals.rows.append(
        _concern_case(
            tenant=tenant, subject=uuid4(), owner=None,
            opened_at=_NOW - timedelta(days=30),
        )
    )

    assert await EscalateStaleConcerns(
        signals, gaps, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant) == []


async def test_the_same_leader_is_not_reported_every_night():
    """Un défaut qui se répète devient du bruit, et le bruit se désapprend en trois semaines."""
    signals, gaps = FakeSignals(), _Gaps()
    jean, tenant = uuid4(), uuid4()
    for _ in range(3):
        signals.rows.append(
            _concern_case(
                tenant=tenant, subject=uuid4(), owner=jean,
                opened_at=_NOW - timedelta(days=30),
            )
        )
    escalate = EscalateStaleConcerns(signals, gaps, _Params(), clock=lambda: _NOW)

    await escalate.execute(tenant_id=tenant)
    await escalate.execute(tenant_id=tenant)

    assert len(gaps.rows) == 1


# --- Bloc 7 : le garde-fou est un ratio, jamais un volume ---------------------------------------


async def test_ten_concerns_and_ten_contacts_is_excellence_not_an_alert():
    """Un seuil sur le volume punirait exactement les meilleurs responsables."""
    signals, gaps = FakeSignals(), _Gaps()
    jean, tenant = uuid4(), uuid4()
    for _ in range(10):
        signals.rows.append(
            _concern_case(tenant=tenant, subject=uuid4(), owner=jean, contacted=_NOW)
        )

    flagged = await GuardAgainstDumping(
        signals, gaps, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant)

    assert flagged == []
    assert gaps.rows == []


async def test_signalling_a_lot_and_contacting_nobody_raises_a_call_for_help():
    signals, gaps = FakeSignals(), _Gaps()
    jean, tenant = uuid4(), uuid4()
    for _ in range(10):
        signals.rows.append(_concern_case(tenant=tenant, subject=uuid4(), owner=jean))

    flagged = await GuardAgainstDumping(
        signals, gaps, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant)

    assert flagged == [jean]
    assert gaps.rows[0].gap is CoverageGap.LEADER_OVERLOADED
    assert "besoin d'aide" in gaps.rows[0].reason


async def test_a_low_ratio_on_two_cases_says_nothing_yet():
    """En dessous du plancher de lisibilité, le ratio porte sur trop peu pour vouloir dire."""
    signals, gaps = FakeSignals(), _Gaps()
    jean, tenant = uuid4(), uuid4()
    for _ in range(2):
        signals.rows.append(_concern_case(tenant=tenant, subject=uuid4(), owner=jean))

    assert await GuardAgainstDumping(
        signals, gaps, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant) == []


# --- Bloc 8 : la calibration s'arrête au tenant ---------------------------------------------------


async def test_precision_is_measured_for_a_church_never_for_a_person():
    """« Jean a raison 70 % du temps » est un score sur quelqu'un — la frontière du moteur.

    On apprend sur les **seuils** d'une église, jamais sur une personne."""
    signals, tenant, jean = FakeSignals(), uuid4(), uuid4()
    right = _concern_case(tenant=tenant, subject=uuid4(), owner=jean)
    right.close(outcome=SignalOutcome.FOLLOWED, at=_NOW, closed_by_account_id=jean)
    wrong = _concern_case(tenant=tenant, subject=uuid4(), owner=jean)
    wrong.close(outcome=SignalOutcome.NOTHING_TO_REPORT, at=_NOW, closed_by_account_id=jean)
    signals.rows += [right, wrong]

    measure = await MeasureConcernPrecision(signals, _Params(), clock=lambda: _NOW).execute(
        tenant_id=tenant
    )

    assert measure.closed == 2
    assert measure.confirmed == 1
    assert measure.precision == 0.5
    # Rien ne descend à la personne : le type lui-même n'a pas de place pour le faire.
    assert not hasattr(measure, "owner_id")
    assert not hasattr(measure, "by_owner")


async def test_precision_on_zero_closed_cases_is_not_a_number():
    """Un taux calculé sur rien est un mensonge qu'on affiche avec assurance."""
    measure = await MeasureConcernPrecision(
        FakeSignals(), _Params(), clock=lambda: _NOW
    ).execute(tenant_id=uuid4())

    assert measure.closed == 0
    assert measure.precision is None


def test_the_vocabulary_can_say_that_an_intuition_was_wrong():
    """Sans cette issue, la calibration mesurerait le vide : aucune autre ne dit
    « j'ai pris contact, tout allait bien »."""
    assert SignalOutcome.NOTHING_TO_REPORT in SignalOutcome
