"""La machine à états du `Signal` — ce qui est refusé, et pourquoi ça compte.

Ces règles ne sont pas des validations que l'application pense à appeler : elles sont dans les
transitions. Une transition qui n'existe pas ne peut pas être tentée.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.arbitration import ArbitrationPolicy, arbitrate
from app.contexts.watch.application.interpretation import OpenCaseView, WatchStateView
from app.contexts.watch.domain.effects import (
    SYSTEM_CLOSURE_CAUSES,
    CasePriority,
    EnrichCase,
    ExtinguishCause,
    OpenCase,
)
from app.contexts.watch.domain.errors import (
    AbsorbingOutcomeError,
    HumanClosureRequiredError,
    InvalidSignalTransitionError,
)
from app.contexts.watch.domain.signal import (
    ABSORBING_OUTCOMES,
    Signal,
    SignalOutcome,
    SignalStatus,
)

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


def _signal(*, origin=CasePriority.ANNOUNCEMENT, status=SignalStatus.OPEN, subject=None):
    return Signal(
        id=uuid4(), tenant_id=uuid4(), subject_id=subject or uuid4(),
        origin=origin, reason="deuil annoncé le 2026-05-01", opened_at=_NOW, status=status,
    )


# --- La clôture est un acte humain ------------------------------------------------------------


def test_closing_a_case_requires_a_human():
    """Sans cette règle, le premier réflexe d'exploitation serait de « nettoyer » la file."""
    signal = _signal()

    with pytest.raises(HumanClosureRequiredError):
        signal.close(outcome=SignalOutcome.FOLLOWED, at=_NOW)

    assert signal.status is SignalStatus.OPEN  # rien n'a bougé


def test_a_system_cause_closes_without_a_human():
    """Le cas n'était pas réel : on ne demande pas de fermer à la main une erreur du système."""
    signal = _signal()

    signal.close(
        outcome=SignalOutcome.EXPLAINED_BY_ANNOUNCEMENT,
        at=_NOW,
        cause=ExtinguishCause.EXPLAINED_BY_ANNOUNCEMENT,
    )

    assert signal.status is SignalStatus.CLOSED
    assert signal.closed_by_account_id is None


def test_a_return_closes_the_neutralization_but_never_the_case():
    """« On peut être présent et endeuillé. »

    Venir une fois au culte explique le silence — ça ne dit pas que le deuil est passé. Fermer
    le soin parce que la personne est là, ce serait confondre « elle est venue » et « elle va
    bien »."""
    assert ExtinguishCause.RETURNED not in SYSTEM_CLOSURE_CAUSES

    signal = _signal()
    with pytest.raises(HumanClosureRequiredError):
        signal.close(outcome=SignalOutcome.RESTORED, at=_NOW, cause=ExtinguishCause.RETURNED)

    assert signal.status is SignalStatus.OPEN  # le cas reste ouvert, et c'est voulu


def test_there_is_no_such_thing_as_extinguishing_by_life_sign():
    """Un signe de vie n'éteint pas un cas — il l'éclaire.

    Déposer une reconnaissance prouve qu'on est vivant et engagé, pas qu'on est revenu en
    cellule. La cause n'existe donc pas au vocabulaire : elle ne peut pas être invoquée par
    distraction. Ce que fait un signe de vie est décrit par `EnrichCase(annotation, downgrade)`."""
    assert not hasattr(ExtinguishCause, "LIFE_SIGN")
    assert SYSTEM_CLOSURE_CAUSES == {
        ExtinguishCause.EXPLAINED_BY_ANNOUNCEMENT,
        ExtinguishCause.DECEASED,
    }


def test_a_life_sign_enriches_and_downgrades_instead_of_closing():
    """« Absente depuis 4 semaines. A déposé un sujet de reconnaissance le 12 avril. »"""
    enrichment = EnrichCase(
        subject_id=uuid4(),
        reason="signe de vie",
        origin=CasePriority.ABSENCE,
        annotation="A déposé un sujet de reconnaissance le 12 avril.",
        downgrade=True,
    )

    assert enrichment.downgrade is True
    assert "reconnaissance" in enrichment.annotation


# --- Les absorbants ----------------------------------------------------------------------------


def test_an_absorbing_outcome_has_no_way_out():
    for outcome in ABSORBING_OUTCOMES:
        signal = _signal()
        signal.close(outcome=outcome, at=_NOW, closed_by_account_id=uuid4())
        with pytest.raises(AbsorbingOutcomeError):
            signal.retract(at=_NOW + timedelta(days=1))


def test_do_not_contact_is_absorbing():
    """« Ne me contactez plus » est une parole qu'aucun algorithme ne peut reprendre."""
    assert SignalOutcome.DO_NOT_CONTACT in ABSORBING_OUTCOMES


# --- Les transitions qui n'existent pas --------------------------------------------------------


def test_a_closed_case_does_not_reopen():
    signal = _signal()
    signal.close(outcome=SignalOutcome.FOLLOWED, at=_NOW, closed_by_account_id=uuid4())

    with pytest.raises(InvalidSignalTransitionError):
        signal.assign(owner_account_id=uuid4())


def test_contact_cannot_start_before_assignment():
    signal = _signal()
    with pytest.raises(InvalidSignalTransitionError):
        signal.start_contact()


def test_a_held_case_becomes_visible_when_capacity_frees():
    signal = _signal(status=SignalStatus.HELD)
    assert signal.is_held is True

    signal.release()

    assert signal.status is SignalStatus.OPEN


# --- Rétraction ≠ clôture -----------------------------------------------------------------------


def test_a_retraction_is_not_a_resolution():
    """Un signal devenu faux n'a rien résolu : il ne doit pas figurer comme un succès."""
    signal = _signal()

    signal.retract(at=_NOW)

    assert signal.status is SignalStatus.RETRACTED
    assert signal.counts_as_resolved is False
    assert signal.outcome is None


def test_a_closure_counts_as_resolved():
    signal = _signal()
    signal.close(outcome=SignalOutcome.RESTORED, at=_NOW, closed_by_account_id=uuid4())
    assert signal.counts_as_resolved is True


# --- La raison est immuable ---------------------------------------------------------------------


def test_the_reason_is_written_once_and_never_rewritten():
    """Un motif reformulé six semaines plus tard ne dit plus la même chose."""
    signal = _signal()
    before = signal.reason

    signal.enrich(source_ref=uuid4(), expires_at=_NOW + timedelta(days=40))

    assert signal.reason == before
    assert not hasattr(Signal, "reason.setter")


def test_enriching_adds_a_source_and_pushes_the_deadline_back():
    signal = _signal()
    first, second = uuid4(), uuid4()

    assert signal.enrich(source_ref=first, expires_at=_NOW + timedelta(days=20)) is True
    assert signal.enrich(source_ref=second, expires_at=_NOW + timedelta(days=40)) is True
    # Une échéance plus courte ne raccourcit rien, et une source déjà connue ne change rien.
    assert signal.enrich(source_ref=second, expires_at=_NOW + timedelta(days=5)) is False

    assert signal.source_refs == [first, second]
    assert signal.expires_at == _NOW + timedelta(days=40)


def test_gestures_are_counted_per_case_never_per_member():
    """Un compteur par personne deviendrait un classement des bons et des mauvais."""
    signal = _signal()
    signal.record_gesture()
    signal.record_gesture()
    assert signal.gestures_count == 2
    assert not hasattr(signal, "member_gestures")


# --- Arbitrage : fusion et plafond --------------------------------------------------------------


def test_a_second_case_on_the_same_person_enriches_instead_of_duplicating():
    """Sinon deux responsables appellent la même personne le même soir, chacun se croyant seul."""
    person = uuid4()
    state = WatchStateView(
        open_cases=(
            OpenCaseView(id=uuid4(), subject_id=person, owner_id=None, origin="announcement"),
        )
    )
    proposed = [
        OpenCase(
            subject_id=person, reason="maladie", origin=CasePriority.ANNOUNCEMENT,
            opened_at=_NOW, expires_at=_NOW + timedelta(days=30),
        )
    ]

    decided = arbitrate(proposed, state)

    assert len(decided.admitted) == 1
    assert isinstance(decided.admitted[0], EnrichCase)


def test_the_cap_holds_the_surplus_instead_of_dropping_it():
    """Un responsable noyé ne traite pas plus de cas — il les ignore tous.

    Tant que `Referent` n'existe pas, tous les cas sans propriétaire partagent le même budget.
    C'est volontairement le côté prudent : on ne fait pas semblant d'avoir réparti la charge."""
    saturated = tuple(
        OpenCaseView(id=uuid4(), subject_id=uuid4(), owner_id=None, origin="absence")
        for _ in range(2)
    )
    state = WatchStateView(open_cases=saturated)
    newcomer = uuid4()  # personne sans cas : il faudrait en ouvrir un
    proposed = [
        OpenCase(
            subject_id=newcomer, reason="silence", origin=CasePriority.ABSENCE, opened_at=_NOW
        )
    ]

    decided = arbitrate(proposed, state, policy=ArbitrationPolicy(open_cases_cap=2))

    assert decided.admitted == ()
    assert decided.held == tuple(proposed)  # retenu, pas perdu — réévalué chaque nuit
    assert decided.dropped == ()


def test_a_declared_case_never_waits_behind_the_cap():
    """On ne fait pas attendre quelqu'un qui a levé la main pour lui-même."""
    owner = uuid4()
    saturated = tuple(
        OpenCaseView(id=uuid4(), subject_id=uuid4(), owner_id=owner, origin="absence")
        for _ in range(9)
    )
    asker = uuid4()
    state = WatchStateView(open_cases=saturated)
    proposed = [
        OpenCase(
            subject_id=asker, reason="A demandé qu'on l'appelle.",
            origin=CasePriority.DECLARED, opened_at=_NOW,
        )
    ]

    decided = arbitrate(proposed, state, policy=ArbitrationPolicy(open_cases_cap=1))

    assert decided.admitted == tuple(proposed)
    assert decided.held == ()


def test_a_held_case_does_not_weigh_on_its_owner_yet():
    """Un cas retenu n'est pas sur les épaules du responsable : il ne consomme pas son budget."""
    owner = uuid4()
    state = WatchStateView(
        open_cases=(
            OpenCaseView(
                id=uuid4(), subject_id=uuid4(), owner_id=owner,
                origin="absence", is_held=True,
            ),
        )
    )
    assert state.open_cases_of_owner(owner) == 0


def test_declared_comes_before_everything_else():
    """La priorité vient de l'origine du dire, jamais d'une gravité supposée."""
    state = WatchStateView()
    absence = OpenCase(
        subject_id=uuid4(), reason="silence", origin=CasePriority.ABSENCE, opened_at=_NOW
    )
    declared = OpenCase(
        subject_id=uuid4(), reason="a demandé", origin=CasePriority.DECLARED, opened_at=_NOW
    )
    announcement = OpenCase(
        subject_id=uuid4(), reason="deuil", origin=CasePriority.ANNOUNCEMENT, opened_at=_NOW
    )

    decided = arbitrate([absence, announcement, declared], state)

    assert [e.origin for e in decided.admitted] == [
        CasePriority.DECLARED,
        CasePriority.ANNOUNCEMENT,
        CasePriority.ABSENCE,
    ]
