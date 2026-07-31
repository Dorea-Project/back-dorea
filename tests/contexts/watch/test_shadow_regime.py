"""Le rodage — *Dorea s'accorde à votre église avant de parler*.

Une église qui installe Dorea n'a jamais vu ses propres seuils. Lui envoyer des cas dès le premier
jour, c'est lui demander de faire confiance à des nombres que personne n'a mesurés chez elle — et
le premier faux positif coûte plus cher que les dix vrais qui suivront.

`SHADOW` n'éteint rien : le pipeline tourne entier, tout est détecté, journalisé et **écrit**. Seule
la sortie est retenue. C'est la différence entre « Dorea ne fonctionne pas encore » et « Dorea
observe » — et c'est pourquoi il réutilise le canal `HELD` au lieu d'inventer un état.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.self_declaration import SelfDeclarationV1
from app.contexts.watch.application.release_held import ReleaseHeldCases
from app.contexts.watch.application.shadow_report import BuildShadowReport
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.parameters import DEFAULTS
from app.contexts.watch.domain.regime import DEFAULT_REGIME, HeldReason, TenantRegime
from app.contexts.watch.domain.registry import MISSION, default_registry
from app.contexts.watch.domain.signal import SignalStatus
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


class _Regimes:
    """Le dépôt du régime — **l'absence de décision vaut `SHADOW`**, comme le vrai."""

    def __init__(self, regime=None):
        self._chosen = regime

    async def regime_of(self, tenant_id):
        return self._chosen or DEFAULT_REGIME

    async def set_regime(self, *, tenant_id, regime, at, by_account_id):
        self._chosen = regime


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


def _engine(*, regime=None, signals=None, ledger=None):
    interpreters = InterpreterRegistry()
    interpreters.register(SelfDeclarationV1())
    signals = signals if signals is not None else FakeSignals()
    ledger = ledger if ledger is not None else FakeLedger()
    intake = Intake(
        ledger, default_registry(), interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals, None, None, None, _Regimes(regime),
    )
    return intake, signals, ledger


def _call_me(tenant, member):
    """« Appelez-moi » — une parole **déclarée**, celle qui sort toujours du plafond."""
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=MISSION, kind=FactKind.SELF_DECLARATION,
        subject_kind=SubjectKind.PERSON, subject_id=member,
        payload={"kind": "contact_request"},
        consent=ConsentProof(given_by=member, scope=ConsentScope.BE_WATCHED, given_at=_NOW),
    )


# --- Le défaut n'est pas neutre ----------------------------------------------------------


async def test_a_church_that_never_decided_is_observing():
    """**Aucune église ne se met à parler par oubli.**

    L'absence de ligne vaut `SHADOW` : le rodage ne dépend ni d'un provisionnement, ni d'un
    backfill. Un défaut « émettre » aurait exigé qu'on pense à insérer une ligne, et le jour où
    quelqu'un l'oublierait, une église découvrirait Dorea par un cas envoyé à un responsable qui
    ne l'attendait pas."""
    assert DEFAULT_REGIME is TenantRegime.SHADOW
    assert await _Regimes().regime_of(uuid4()) is TenantRegime.SHADOW


# --- Tout est détecté, rien n'est émis ---------------------------------------------------


async def test_in_shadow_everything_is_detected_and_written():
    """Le pipeline tourne **entier** : ce n'est pas un interrupteur qui éteint la détection."""
    tenant, member = uuid4(), uuid4()
    intake, signals, ledger = _engine()

    await intake.submit(_call_me(tenant, member))

    assert len(ledger.rows) == 1  # le fait est au journal
    (case,) = signals.rows  # le cas est écrit
    assert case.status is SignalStatus.HELD  # mais retenu
    assert case.held_reason == HeldReason.SHADOW.value  # et on sait pourquoi


async def test_in_shadow_nothing_reaches_a_responsable():
    tenant, member, lead = uuid4(), uuid4(), uuid4()
    intake, signals, _ = _engine()
    await intake.submit(_call_me(tenant, member))
    signals.rows[0].owner_account_id = lead

    assert await signals.cases_of_owner(account_id=lead, tenant_id=tenant) == []


async def test_even_the_declared_is_held_while_the_church_observes():
    """Retenir le déclaré peut surprendre — c'est pourtant le point.

    Une église qui n'a pas encore annoncé Dorea à ses responsables ne doit leur envoyer aucun cas,
    quelle qu'en soit l'origine. Le plafond, lui, laisse toujours passer le déclaré."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()

    result = await intake.submit(_call_me(tenant, member))

    assert result.arbitration.held  # retenu bien qu'il soit déclaré
    assert signals.rows[0].origin is CasePriority.DECLARED


async def test_a_church_that_speaks_emits_normally():
    """Le pendant : sans lui, le test précédent ne prouverait rien."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine(regime=TenantRegime.STEADY)

    await intake.submit(_call_me(tenant, member))

    assert signals.rows[0].status is not SignalStatus.HELD
    assert signals.rows[0].held_reason is None


# --- Le rodage n'est pas un plafond ------------------------------------------------------


async def test_the_nightly_pass_never_releases_what_the_shadow_holds():
    """**Le pire bug possible de ce module**, et il est fermé par un test.

    La passe nocturne relâche ce que le plafond retient. Si elle relâchait aussi ce que le rodage
    retient, une église en observation se mettrait à parler toute seule, pendant la nuit, sans que
    personne ne l'ait décidé."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()
    await intake.submit(_call_me(tenant, member))
    assert signals.rows[0].status is SignalStatus.HELD

    report = await ReleaseHeldCases(
        signals, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=tenant)

    assert report.released == 0
    assert signals.rows[0].status is SignalStatus.HELD
    assert signals.rows[0].held_reason == HeldReason.SHADOW.value


# --- Ce que le pasteur reçoit ------------------------------------------------------------


async def test_the_report_says_what_dorea_would_have_signalled():
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine()
    await intake.submit(_call_me(tenant, member))

    report = await BuildShadowReport(signals, _Regimes()).execute(tenant_id=tenant)

    assert report.is_observing is True
    assert report.count == 1
    (would,) = report.cases
    assert would.subject_id == member
    assert "appelle" in would.reason.lower() or "demandé" in would.reason.lower()


async def test_the_report_follows_the_order_the_cases_would_have_come_out_in():
    """Le pasteur lit la file telle qu'elle **aurait été**, pas un tas trié par insertion."""
    tenant = uuid4()
    intake, signals, _ = _engine()
    await intake.submit(_call_me(tenant, uuid4()))
    # Un cas d'absence détecté plus tôt, mais moins urgent que le déclaré.
    signals.rows.append(
        type(signals.rows[0])(
            id=uuid4(), tenant_id=tenant, subject_id=uuid4(),
            origin=CasePriority.ABSENCE, reason="Sans nouvelles — 3 rencontres.",
            opened_at=_NOW - timedelta(days=10), status=SignalStatus.HELD,
            owner_account_id=uuid4(), held_reason=HeldReason.SHADOW.value,
        )
    )

    report = await BuildShadowReport(signals, _Regimes()).execute(tenant_id=tenant)

    assert [c.origin for c in report.cases] == [
        CasePriority.DECLARED.value,
        CasePriority.ABSENCE.value,
    ]


async def test_a_church_that_speaks_has_no_shadow_report():
    """Ses cas sont sur des écrans : il n'y a rien à rendre en cachette."""
    tenant, member = uuid4(), uuid4()
    intake, signals, _ = _engine(regime=TenantRegime.STEADY)
    await intake.submit(_call_me(tenant, member))

    report = await BuildShadowReport(
        signals, _Regimes(TenantRegime.STEADY)
    ).execute(tenant_id=tenant)

    assert report.is_observing is False
    assert report.count == 0
