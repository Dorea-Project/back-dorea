"""La boucle froide — *elle observe et calibre ; elle ne décide jamais d'un cas*.

Ces tests ont deux moitiés très différentes, et la seconde est la plus importante.

La première vérifie l'arithmétique : ce que les responsables ont constaté remonte en verdicts, et
les verdicts produisent des propositions de seuil. La seconde vérifie les **interdits** — et elle
les vérifie *structurellement*, en lisant le paquet, pas en faisant confiance à un commentaire.

> Un interdit qu'aucun test ne tient est une intention, et les intentions ne survivent pas à la
> pression de livrer.
"""

import ast
import importlib
import pkgutil
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

import app.contexts.watch.calibration as calibration_pkg
from app.contexts.iam.domain.permissions import Permission
from app.contexts.watch.calibration.judge import (
    IGNORED_AFTER_DAYS,
    GroundTruth,
    OutcomeJudge,
)
from app.contexts.watch.calibration.ports import AbsenceEvidence
from app.contexts.watch.calibration.proposal import (
    BOUNDS,
    MIN_EVIDENCE,
    ApplyProposal,
    CalibrationProposal,
    ProposalStatus,
    Proposer,
)
from app.contexts.watch.calibration.review import (
    DecideOnProposal,
    ListProposals,
    ProposalNotFoundError,
    ProposalOutOfBoundsError,
    RunCalibrationPass,
)
from app.contexts.watch.calibration.simulator import Simulator
from app.contexts.watch.domain.effects import CasePriority, ExtinguishCause
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam
from app.contexts.watch.domain.regime import DEFAULT_REGIME, TenantRegime
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from tests.contexts.watch.fakes import FakeSignals

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


class _Params:
    """Lit **et** écrit — les deux ports, parce que la vraie implémentation les tient tous deux."""

    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]

    async def set_int(self, *, tenant_id, param, value):
        self._values[param] = value


class _Proposals:
    """Le dépôt — avec sa règle : **une seule en attente par `(église, paramètre)`**."""

    def __init__(self):
        self.rows = []

    async def add_all(self, proposals):
        waiting = {
            p.param for p in self.rows if p.status is ProposalStatus.PENDING
        }
        kept = []
        for proposal in proposals:
            if proposal.param in waiting:
                continue
            waiting.add(proposal.param)
            self.rows.append(proposal)
            kept.append(proposal)
        return kept

    async def pending(self, tenant_id):
        return [
            p
            for p in self.rows
            if p.tenant_id == tenant_id and p.status is ProposalStatus.PENDING
        ]

    async def get(self, *, proposal_id, tenant_id):
        return next(
            (p for p in self.rows if p.id == proposal_id and p.tenant_id == tenant_id),
            None,
        )

    async def save(self, proposal):
        self.rows = [proposal if p.id == proposal.id else p for p in self.rows]


class _Access:
    """La politique d'autorité. Elle dit non à qui n'est pas le propriétaire de l'église."""

    def __init__(self, allowed=None):
        self.allowed = allowed
        self.asked = []

    async def ensure_church_wide(self, *, actor_account_id, tenant_id, permission):
        self.asked.append(permission)
        if self.allowed is not None and actor_account_id != self.allowed:
            raise PermissionError("pas église-entière")


class _Regimes:
    def __init__(self, regime=None):
        self._chosen = regime

    async def regime_of(self, tenant_id):
        return self._chosen or DEFAULT_REGIME

    async def set_regime(self, *, tenant_id, regime, at, by_account_id):
        self._chosen = regime


def _closed(signals, *, tenant, origin, outcome, human=True):
    """Un cas fermé. `human=False` = clôture système, celle que la vérité terrain n'écoute pas."""
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=uuid4(), origin=origin,
        reason="…", opened_at=_NOW - timedelta(days=20),
    )
    case.close(
        outcome=outcome,
        at=_NOW - timedelta(days=1),
        closed_by_account_id=uuid4() if human else None,
        cause=None if human else ExtinguishCause.EXPLAINED_BY_ANNOUNCEMENT,
    )
    signals.rows.append(case)
    return case


def _borne(signals, *, tenant, owner, seen: bool, days_old=IGNORED_AFTER_DAYS + 1):
    """Un cas qui pèse sur les épaules de quelqu'un — ouvert par lui, ou jamais."""
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=uuid4(), origin=CasePriority.ABSENCE,
        reason="…", opened_at=_NOW - timedelta(days=days_old),
        status=SignalStatus.ASSIGNED, owner_account_id=owner,
        first_seen_at=_NOW - timedelta(days=1) if seen else None,
    )
    signals.rows.append(case)
    return case


def _judge(signals, params=None):
    return OutcomeJudge(signals, params or _Params(), clock=lambda: _NOW)


# --- Ce que les humains ont constaté ------------------------------------------------------


async def test_contact_taken_nothing_to_report_is_the_false_positive():
    """L'issue qui dit que la détection s'est trompée — et la seule.

    Toutes les autres décrivent une situation réelle qu'il a fallu porter, même celles qui
    finissent mal. « J'ai pris contact, tout allait bien » est le seul cas où quelqu'un a été
    dérangé pour rien."""
    signals, tenant = FakeSignals(), uuid4()
    _closed(signals, tenant=tenant, origin=CasePriority.ABSENCE,
            outcome=SignalOutcome.NOTHING_TO_REPORT)
    _closed(signals, tenant=tenant, origin=CasePriority.ABSENCE,
            outcome=SignalOutcome.FOLLOWED)

    truth = await _judge(signals).execute(tenant_id=tenant)

    verdict = truth.verdict_for(CasePriority.ABSENCE)
    assert (verdict.closed, verdict.confirmed, verdict.false_positives) == (2, 1, 1)
    assert verdict.precision == 0.5


async def test_a_system_closure_is_not_ground_truth():
    """Un cas éteint par une annonce n'a été **vérifié par personne**.

    Le compter ferait noter la machine par la machine : c'est le moteur qui a décidé que
    l'absence s'expliquait, et le ranger comme une détection juste — ou fausse — gonflerait ou
    creuserait la précision d'une église où pas un seul contact n'a eu lieu."""
    signals, tenant = FakeSignals(), uuid4()
    _closed(signals, tenant=tenant, origin=CasePriority.ABSENCE,
            outcome=SignalOutcome.EXPLAINED_BY_ANNOUNCEMENT, human=False)

    truth = await _judge(signals).execute(tenant_id=tenant)

    assert truth.by_origin == ()


async def test_a_confirmed_concern_says_a_human_saw_before_the_engine():
    """La seule mesure du produit qui dise « tu étais trop lent » plutôt que « tu criais ».

    Quelqu'un a signalé une inquiétude, elle s'est confirmée : les seuils n'avaient rien vu."""
    signals, tenant = FakeSignals(), uuid4()
    for _ in range(3):
        _closed(signals, tenant=tenant, origin=CasePriority.CONCERN,
                outcome=SignalOutcome.FOLLOWED)
    _closed(signals, tenant=tenant, origin=CasePriority.CONCERN,
            outcome=SignalOutcome.NOTHING_TO_REPORT)

    truth = await _judge(signals).execute(tenant_id=tenant)

    assert truth.missed_detections == 3  # l'intuition fausse n'en est pas une


async def test_precision_on_nothing_is_not_zero():
    """Zéro cas fermé ne veut pas dire zéro justesse : ça veut dire qu'on ne sait pas encore.

    Rendre `0.0` ferait descendre une moyenne et déclencherait des propositions sur du vide."""
    truth = await _judge(FakeSignals()).execute(tenant_id=uuid4())

    assert truth.by_origin == ()
    assert truth.ignored_rate is None


async def test_a_case_nobody_ever_opened_is_the_indicator_that_anticipates():
    """Le taux d'ignorés monte **avant** l'abandon, quand tout le reste a encore l'air normal :
    les cas traités le sont vite, et les autres ne sont simplement jamais ouverts."""
    signals, tenant, jean = FakeSignals(), uuid4(), uuid4()
    _borne(signals, tenant=tenant, owner=jean, seen=True)
    _borne(signals, tenant=tenant, owner=jean, seen=False)
    _borne(signals, tenant=tenant, owner=jean, seen=False)
    # Ouvert hier : trop récent pour qu'on l'appelle ignoré.
    _borne(signals, tenant=tenant, owner=jean, seen=False, days_old=1)

    truth = await _judge(signals).execute(tenant_id=tenant)

    assert (truth.ignored, truth.on_shoulders) == (2, 3)
    assert truth.ignored_rate == 2 / 3


# --- Ce que la boucle froide propose ------------------------------------------------------


async def test_a_detection_that_cries_too_loud_raises_its_own_threshold():
    signals, tenant = FakeSignals(), uuid4()
    for _ in range(6):
        _closed(signals, tenant=tenant, origin=CasePriority.ABSENCE,
                outcome=SignalOutcome.NOTHING_TO_REPORT)

    truth = await _judge(signals).execute(tenant_id=tenant)
    params = _Params()
    (proposal,) = await Proposer(params).execute(truth=truth)

    assert proposal.param is WatchParam.ABSENCE_OCCURRENCES_THRESHOLD
    assert proposal.proposed == DEFAULTS[WatchParam.ABSENCE_OCCURRENCES_THRESHOLD] + 1
    assert "6 cas d'absence sur 6" in proposal.evidence


async def test_an_overflowing_queue_lowers_the_cap_it_never_raises_it():
    """**Le contre-intuitif du module.** Une file qui déborde n'est pas un plafond trop bas.

    Remonter le plafond ferait disparaître l'indicateur en noyant le responsable — c'est-à-dire
    en supprimant exactement la protection dont l'indicateur signale le besoin."""
    signals, tenant, jean = FakeSignals(), uuid4(), uuid4()
    for _ in range(6):
        _borne(signals, tenant=tenant, owner=jean, seen=False)

    truth = await _judge(signals).execute(tenant_id=tenant)
    (proposal,) = await Proposer(_Params()).execute(truth=truth)

    assert proposal.param is WatchParam.OPEN_CASES_CAP
    assert proposal.proposed < proposal.current


async def test_a_noisy_detection_is_fixed_before_the_queue_is_touched():
    """Quand les deux symptômes sont là, on corrige la **cause**.

    Une file qui déborde de faux positifs se soigne au seuil de détection ; toucher au plafond
    d'abord reviendrait à traiter la fièvre en cassant le thermomètre."""
    signals, tenant, jean = FakeSignals(), uuid4(), uuid4()
    for _ in range(6):
        _closed(signals, tenant=tenant, origin=CasePriority.ABSENCE,
                outcome=SignalOutcome.NOTHING_TO_REPORT)
        _borne(signals, tenant=tenant, owner=jean, seen=False)

    truth = await _judge(signals).execute(tenant_id=tenant)
    proposals = await Proposer(_Params()).execute(truth=truth)

    assert [p.param for p in proposals] == [WatchParam.ABSENCE_OCCURRENCES_THRESHOLD]


async def test_it_proposes_nothing_on_a_handful_of_cases():
    """Calibrer sur trois cas fermés, c'est calibrer du bruit — et le faire avec assurance."""
    signals, tenant = FakeSignals(), uuid4()
    for _ in range(MIN_EVIDENCE - 1):
        _closed(signals, tenant=tenant, origin=CasePriority.ABSENCE,
                outcome=SignalOutcome.NOTHING_TO_REPORT)

    truth = await _judge(signals).execute(tenant_id=tenant)

    assert await Proposer(_Params()).execute(truth=truth) == []


# --- Ce qu'elle a le droit d'appliquer ----------------------------------------------------


def _proposal(tenant, *, param=WatchParam.OPEN_CASES_CAP, current=5, proposed=4):
    return CalibrationProposal(
        id=uuid4(), tenant_id=tenant, param=param, current=current,
        proposed=proposed, evidence="…",
    )


async def test_out_of_bounds_never_applies_alone_whatever_the_regime():
    """Ce qui empêche une dérive lente de mener quelque part où personne n'aurait accepté
    d'aller d'un coup."""
    low, _high = BOUNDS[WatchParam.OPEN_CASES_CAP]
    params, tenant = _Params(), uuid4()

    applied = await ApplyProposal(params, _Regimes(TenantRegime.STEADY)).execute(
        proposal=_proposal(tenant, proposed=low - 1), approved_by=uuid4()
    )

    assert applied.applied is False
    assert await params.get_int(tenant, WatchParam.OPEN_CASES_CAP) == DEFAULTS[
        WatchParam.OPEN_CASES_CAP
    ]


async def test_an_church_still_running_in_shadow_never_has_its_thresholds_moved():
    """Elle n'a pas encore accepté que Dorea parle : lui changer ses seuils dans le dos serait
    pire qu'inutile."""
    params, tenant = _Params(), uuid4()

    applied = await ApplyProposal(params, _Regimes()).execute(proposal=_proposal(tenant))

    assert applied.applied is False
    assert "approbation" in applied.reason


async def test_within_bounds_and_settled_it_applies_itself():
    params, tenant = _Params(), uuid4()

    applied = await ApplyProposal(params, _Regimes(TenantRegime.STEADY)).execute(
        proposal=_proposal(tenant, proposed=4)
    )

    assert applied.applied is True
    assert await params.get_int(tenant, WatchParam.OPEN_CASES_CAP) == 4


async def test_assisted_applies_what_a_human_approved():
    params, tenant = _Params(), uuid4()

    applied = await ApplyProposal(params, _Regimes(TenantRegime.ASSISTED)).execute(
        proposal=_proposal(tenant, proposed=4), approved_by=uuid4()
    )

    assert applied.applied is True


# --- La passe, et l'humain qui tranche ----------------------------------------------------


def _noisy(signals, tenant, *, count=6):
    for _ in range(count):
        _closed(signals, tenant=tenant, origin=CasePriority.ABSENCE,
                outcome=SignalOutcome.NOTHING_TO_REPORT)


def _pass(signals, proposals, *, regime=None, params=None):
    params = params or _Params()
    return RunCalibrationPass(
        _judge(signals, params),
        Proposer(params),
        proposals,
        ApplyProposal(params, _Regimes(regime), proposals, clock=lambda: _NOW),
    )


async def test_a_church_that_observes_only_gets_a_proposal_waiting():
    """En rodage, la boucle froide mesure et **n'applique rien** : l'église n'a pas encore
    accepté que Dorea parle, elle n'a certainement pas accepté qu'elle se règle seule."""
    signals, proposals, tenant, params = FakeSignals(), _Proposals(), uuid4(), _Params()
    _noisy(signals, tenant)

    result = await _pass(signals, proposals, params=params).execute(tenant_id=tenant)

    assert (result.proposed, result.applied) == (1, 0)
    assert len(await proposals.pending(tenant)) == 1
    assert await params.get_int(tenant, WatchParam.ABSENCE_OCCURRENCES_THRESHOLD) == (
        DEFAULTS[WatchParam.ABSENCE_OCCURRENCES_THRESHOLD]
    )


async def test_a_settled_church_moves_its_own_threshold_within_the_bounds():
    signals, proposals, tenant, params = FakeSignals(), _Proposals(), uuid4(), _Params()
    _noisy(signals, tenant)

    result = await _pass(
        signals, proposals, regime=TenantRegime.STEADY, params=params
    ).execute(tenant_id=tenant)

    assert (result.proposed, result.applied) == (1, 1)
    assert await params.get_int(tenant, WatchParam.ABSENCE_OCCURRENCES_THRESHOLD) == (
        DEFAULTS[WatchParam.ABSENCE_OCCURRENCES_THRESHOLD] + 1
    )


async def test_the_same_proposal_never_stacks_up_night_after_night():
    """Trente fois la même phrase, et l'écran du pasteur devient un endroit qu'on ferme sans
    lire. Une passe ne repropose rien tant qu'une décision est attendue sur le même seuil."""
    signals, proposals, tenant = FakeSignals(), _Proposals(), uuid4()
    _noisy(signals, tenant)
    cold = _pass(signals, proposals)

    first = await cold.execute(tenant_id=tenant)
    second = await cold.execute(tenant_id=tenant)

    assert (first.proposed, second.proposed) == (1, 0)
    assert len(await proposals.pending(tenant)) == 1


async def test_a_refusal_is_recorded_and_the_proposal_does_not_come_back():
    """**Un refus vaut autant qu'une acceptation.** Une proposition rejetée qui se represente
    chaque nuit est du harcèlement, et le pasteur apprend à tout accepter pour que ça s'arrête."""
    signals, proposals, tenant, pastor = FakeSignals(), _Proposals(), uuid4(), uuid4()
    _noisy(signals, tenant)
    await _pass(signals, proposals).execute(tenant_id=tenant)
    (waiting,) = await proposals.pending(tenant)
    params = _Params()

    decided = await DecideOnProposal(
        proposals,
        ApplyProposal(params, _Regimes(TenantRegime.ASSISTED), proposals),
        _Access(),
        clock=lambda: _NOW,
    ).execute(
        proposal_id=waiting.id, tenant_id=tenant, actor_account_id=pastor, accept=False
    )

    assert decided.status is ProposalStatus.REJECTED
    assert decided.decided_by_account_id == pastor  # datée et signée
    assert await proposals.pending(tenant) == []
    # Le seuil n'a pas bougé : refuser, c'est refuser.
    assert await params.get_int(tenant, WatchParam.ABSENCE_OCCURRENCES_THRESHOLD) == (
        DEFAULTS[WatchParam.ABSENCE_OCCURRENCES_THRESHOLD]
    )


async def test_a_decision_is_taken_once():
    signals, proposals, tenant, pastor = FakeSignals(), _Proposals(), uuid4(), uuid4()
    _noisy(signals, tenant)
    await _pass(signals, proposals).execute(tenant_id=tenant)
    (waiting,) = await proposals.pending(tenant)
    decide = DecideOnProposal(
        proposals,
        ApplyProposal(_Params(), _Regimes(TenantRegime.ASSISTED), proposals),
        _Access(),
        clock=lambda: _NOW,
    )
    await decide.execute(
        proposal_id=waiting.id, tenant_id=tenant, actor_account_id=pastor, accept=False
    )

    with pytest.raises(ProposalNotFoundError):
        await decide.execute(
            proposal_id=waiting.id, tenant_id=tenant, actor_account_id=pastor,
            accept=True,
        )


async def test_an_approved_proposal_out_of_bounds_says_so_instead_of_filing_itself():
    """Un écran qui range sans rien changer est pire qu'un écran qui dit non."""
    proposals, tenant, pastor = _Proposals(), uuid4(), uuid4()
    low, _high = BOUNDS[WatchParam.OPEN_CASES_CAP]
    await proposals.add_all([_proposal(tenant, proposed=low - 1)])
    (waiting,) = await proposals.pending(tenant)

    with pytest.raises(ProposalOutOfBoundsError):
        await DecideOnProposal(
            proposals,
            ApplyProposal(_Params(), _Regimes(TenantRegime.STEADY), proposals),
            _Access(),
            clock=lambda: _NOW,
        ).execute(
            proposal_id=waiting.id, tenant_id=tenant, actor_account_id=pastor,
            accept=True,
        )

    assert (await proposals.pending(tenant))[0].status is ProposalStatus.PENDING


async def test_changing_a_threshold_asks_the_authority_that_enrols_the_staff():
    """Changer un seuil de détection engage l'église entière : c'est de la gouvernance, la même
    famille que « laissez Dorea parler », pas une lecture pastorale."""
    proposals, access, tenant = _Proposals(), _Access(), uuid4()

    await ListProposals(proposals, access).execute(
        tenant_id=tenant, actor_account_id=uuid4()
    )

    assert access.asked == [Permission.MANAGE_STAFF]


# --- Ce que la proposition coûterait ------------------------------------------------------

_SINCE = _NOW - timedelta(days=30)


class _Evidence:
    """Les tirs d'absence, tels que le journal les porte : `occurrences`, `threshold`, l'issue."""

    def __init__(self, rows=()):
        self.rows = list(rows)

    async def absence_evidence(self, *, tenant_id, since):
        return self.rows


def _shot(occurrences, outcome=None, threshold=3):
    return AbsenceEvidence(
        occurrences=occurrences, threshold=threshold,
        outcome=outcome.value if outcome else None,
    )


async def test_raising_a_threshold_is_measured_exactly():
    """Vers le haut, le nouvel ensemble est un **sous-ensemble** de ce qui s'est ouvert — et pour
    ceux-là on sait déjà qu'aucune neutralisation ne courait. Rien à estimer."""
    evidence = _Evidence([
        _shot(3, SignalOutcome.NOTHING_TO_REPORT),
        _shot(3, SignalOutcome.NOTHING_TO_REPORT),
        _shot(3, SignalOutcome.FOLLOWED),
        _shot(5, SignalOutcome.FOLLOWED),
    ])

    result = await Simulator(evidence).execute(
        tenant_id=uuid4(), candidate=4, since=_SINCE
    )

    assert result.exact is True
    assert (result.opened_now, result.opened_then) == (4, 1)
    assert result.spared_noise == 2
    assert result.missed_real == 1  # le prix, et il est nommé


async def test_lowering_a_threshold_can_only_be_bounded():
    """Vers le bas, on ne sait pas qui un deuil ou un voyage aurait étouffé : le journal ne porte
    pas les neutralisations. Un nombre dont on ne sait plus s'il est une mesure ou une estimation
    finit toujours par être lu comme une mesure."""
    result = await Simulator(_Evidence([_shot(3, SignalOutcome.FOLLOWED)])).execute(
        tenant_id=uuid4(), candidate=2, since=_SINCE
    )

    assert result.exact is False
    assert "au plus" in result.sentence


async def test_a_case_still_alive_counts_for_nothing():
    """Personne ne sait encore ce qu'il valait, et on ne devine pas à la place de celui qui
    l'appellera."""
    result = await Simulator(_Evidence([_shot(2, None)])).execute(
        tenant_id=uuid4(), candidate=5, since=_SINCE
    )

    assert (result.spared_noise, result.missed_real) == (0, 0)


async def test_the_sentence_ends_on_what_is_lost():
    """L'ordre d'une phrase est ce qu'on en retient. Une proposition qui ne dit que ce qu'elle
    fait gagner est une publicité."""
    evidence = _Evidence([
        _shot(3, SignalOutcome.NOTHING_TO_REPORT),
        _shot(3, SignalOutcome.FOLLOWED),
    ])

    sentence = (
        await Simulator(evidence).execute(
            tenant_id=uuid4(), candidate=4, since=_SINCE
        )
    ).sentence

    assert sentence.index("rien à signaler") < sentence.index("confirmés")
    assert sentence.rstrip(".").endswith("qui se sont confirmés")


async def test_the_proposal_carries_what_it_would_cost():
    signals, tenant = FakeSignals(), uuid4()
    _noisy(signals, tenant)
    evidence = _Evidence([
        _shot(3, SignalOutcome.NOTHING_TO_REPORT),
        _shot(3, SignalOutcome.FOLLOWED),
    ])

    truth = await _judge(signals).execute(tenant_id=tenant)
    (proposal,) = await Proposer(_Params(), Simulator(evidence)).execute(truth=truth)

    assert "se sont fermés sur" in proposal.evidence  # la mesure rétrospective
    assert "ne se seraient pas ouverts" in proposal.evidence  # le contrefactuel


async def test_the_simulator_never_picks_the_candidate():
    """Il chiffre ; il ne choisit pas. Un simulateur qui choisirait arbitrerait en silence
    « moins de bruit contre des gens qu'on ne voit plus » — un compromis qui n'est pas le sien.

    La preuve est structurelle : la proposition vaut `+1` quelle que soit la simulation, y compris
    quand celle-ci dit que le seuil coûterait cher."""
    signals, tenant = FakeSignals(), uuid4()
    _noisy(signals, tenant)
    ruinous = _Evidence([_shot(3, SignalOutcome.FOLLOWED) for _ in range(20)])

    truth = await _judge(signals).execute(tenant_id=tenant)
    (proposal,) = await Proposer(_Params(), Simulator(ruinous)).execute(truth=truth)

    assert proposal.proposed == DEFAULTS[WatchParam.ABSENCE_OCCURRENCES_THRESHOLD] + 1
    assert "20 qui se sont confirmés" in proposal.evidence


async def test_the_cap_gets_no_invented_counterfactual():
    """Le plafond n'aurait pas empêché des cas d'exister, seulement retardé leur sortie. On
    n'écrit pas une phrase pour faire symétrique."""
    signals, tenant, jean = FakeSignals(), uuid4(), uuid4()
    for _ in range(6):
        _borne(signals, tenant=tenant, owner=jean, seen=False)

    truth = await _judge(signals).execute(tenant_id=tenant)
    (proposal,) = await Proposer(
        _Params(), Simulator(_Evidence([_shot(3, SignalOutcome.FOLLOWED)]))
    ).execute(truth=truth)

    assert proposal.param is WatchParam.OPEN_CASES_CAP
    assert "ne se seraient pas ouverts" not in proposal.evidence


# --- Les quatre interdits, lus dans le paquet ---------------------------------------------


def _calibration_sources() -> list[Path]:
    root = Path(calibration_pkg.__file__).parent
    return sorted(root.glob("*.py"))


def _calibration_modules():
    root = Path(calibration_pkg.__file__).parent
    return [
        importlib.import_module(f"{calibration_pkg.__name__}.{m.name}")
        for m in pkgutil.iter_modules([str(root)])
    ]


def test_interdict_one_no_calibration_object_carries_an_observed_person():
    """Le grain le plus fin est `(église, paramètre)`. Il n'y a pas de champ pour descendre.

    **La frontière est entre l'auteur et le sujet.** Une personne peut avoir *décidé* d'un
    réglage — c'est même exigé, une décision se signe. Aucune ne peut être *mesurée* : c'est le
    score par personne que le moteur s'interdit, et il a besoin d'un sujet pour exister.

    Ce test lit les dataclasses du paquet ; ajouter un `subject_id` à un agrégat de calibration
    demanderait de venir désactiver cette ligne, donc de le décider."""
    forbidden = {
        "subject_id", "person_id", "account_id", "owner_id", "owner_account_id",
        "member_id", "by_account_id", "closed_by_account_id", "responsible_id",
    }
    for module in _calibration_modules():
        for name in dir(module):
            obj = getattr(module, name)
            if not is_dataclass(obj) or getattr(obj, "__module__", "") != module.__name__:
                continue
            named = {f.name for f in fields(obj)}
            assert not (named & forbidden), f"{module.__name__}.{name}"


def test_interdict_four_the_only_person_named_is_the_one_who_signed():
    """Le corollaire du premier, plus dur : on n'énumère pas des noms interdits, on énumère les
    **trois seuls identifiants autorisés** — et un score par personne n'en fait pas partie.

    `decided_by_account_id` est le seul qui nomme quelqu'un, et il ne porte aucun nombre : c'est
    une signature. Attacher une mesure à une personne demanderait un quatrième champ, donc une
    ligne à venir ajouter ici."""
    allowed = {"tenant_id", "id", "decided_by_account_id"}
    for module in _calibration_modules():
        for name in dir(module):
            obj = getattr(module, name)
            if not is_dataclass(obj) or getattr(obj, "__module__", "") != module.__name__:
                continue
            for field in fields(obj):
                if "UUID" in str(field.type):
                    assert field.name in allowed, f"{module.__name__}.{name}.{field.name}"


def test_interdict_two_and_three_the_cold_loop_cannot_write():
    """Elle ne peut ni matérialiser un effet, ni faire entrer un fait inféré au journal.

    Ce n'est pas une consigne : les chemins d'écriture ne sont **pas importables** depuis ici, et
    ce test échoue à la première ligne d'import qui les ferait entrer."""
    write_paths = {
        "materialization", "projections", "intake", "ledger", "arbitration",
        "owner_assignment", "case_acts", "fire_checks",
    }
    for source in _calibration_sources():
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = getattr(node, "module", None) if isinstance(node, ast.ImportFrom) else None
            names = [module] if module else []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for dotted in filter(None, names):
                leaf = dotted.rsplit(".", 1)[-1]
                assert leaf not in write_paths, f"{source.name} importe {dotted}"


def test_the_only_thing_it_can_write_is_an_integer_for_a_church():
    """Tout son pouvoir d'écriture tient dans une signature — et elle est lisible d'un coup d'œil.

    Un port séparé plutôt qu'une méthode de plus sur le dépôt de lecture : la lecture est partout
    dans le moteur, l'écriture nulle part ailleurs."""
    from app.contexts.watch.calibration.ports import WatchParameterWriter

    assert [
        name for name in vars(WatchParameterWriter) if not name.startswith("_")
    ] == ["set_int"]


def test_ground_truth_is_the_church_and_nothing_smaller():
    """Le type lui-même n'a pas de place pour un responsable — comme `ConcernPrecision`."""
    named = {f.name for f in fields(GroundTruth)}

    assert "tenant_id" in named
    assert not any(n.startswith("by_owner") or n.endswith("_by_person") for n in named)
