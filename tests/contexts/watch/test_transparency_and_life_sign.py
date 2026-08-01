"""La frontière de transparence, et le signe de vie.

Deux décisions produit du 30/07/2026, et elles se tiennent l'une l'autre.

**La frontière.** Le membre peut lister ce qui découle de ses propres actes ; il ne peut pas lister
ce qu'un tiers a ressenti à son sujet, parce que cette donnée décrit l'engagement du tiers. Ce n'est
pas une exception à la transparence — c'en aurait été une de plus, et une liste d'exceptions n'est
plus une promesse. C'est une frontière, et elle ne tient que grâce à sa contrepartie : un arrêt
d'urgence inconditionnel, qui n'exige de connaître aucun dossier.

**Le signe de vie.** Déposer une reconnaissance prouve qu'on est vivant, pas qu'on est revenu :
ça n'éteint jamais un cas que quelqu'un a vu. Mais sur un cas encore retenu, que personne n'avait
lu, ça le rétracte — faire appeler quelqu'un qui vient de donner de ses nouvelles serait le
contraire de ce qu'on cherche.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.arbitration import arbitrate
from app.contexts.watch.application.interpretation import (
    LiveCaseView,
    WatchStateView,
)
from app.contexts.watch.application.stop_contacting_me import StopContactingMe
from app.contexts.watch.domain.effects import (
    CasePriority,
    EnrichCase,
    ExtinguishCause,
    RetractHeld,
)
from app.contexts.watch.domain.facts import CASE_ACTS, Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import ATTENDANCE, WATCH_UI
from app.contexts.watch.domain.signal import (
    RetractionCause,
    Signal,
    SignalOutcome,
    SignalStatus,
)
from app.contexts.watch.domain.transparency import is_listable_to_subject
from tests.contexts.watch.fakes import FakeChecks, FakeSignals

_NOW = datetime(2026, 8, 6, tzinfo=UTC)


def _fact(kind, *, source=ATTENDANCE, subject=None):
    return Fact(
        fact_id=uuid4(), tenant_id=uuid4(), occurred_at=_NOW, recorded_at=_NOW,
        source=source, kind=kind, subject_kind=SubjectKind.PERSON,
        subject_id=subject or uuid4(), payload={},
    )


def _case(signals, *, tenant, subject, owner=None, status=SignalStatus.ASSIGNED):
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=subject, origin=CasePriority.ABSENCE,
        reason="Sans nouvelles.", opened_at=_NOW - timedelta(days=20),
        status=status, owner_account_id=owner or uuid4(),
    )
    signals.rows.append(case)
    return case


# --- La frontière : ce qui découle de ses propres actes ----------------------------------


def test_a_member_can_list_what_flows_from_his_own_acts():
    """Ses présences, ses paroles, ses demandes : c'est son histoire, elle lui appartient."""
    for kind in (
        FactKind.PRESENCE_RECORDED,
        FactKind.SELF_DECLARATION,
        FactKind.APPOINTMENT_REQUESTED,
        FactKind.GRATITUDE_DEPOSITED,
        FactKind.JOINED_GROUP,
        FactKind.LIFE_EVENT_ANNOUNCED,
    ):
        assert is_listable_to_subject(_fact(kind)) is True


def test_a_member_never_learns_that_someone_spoke_about_him():
    """« Je m'en occupe » décrit l'engagement de celui qui l'a posé, pas la personne.

    C'est la condition pour que ce canal existe sans devenir une délation — et l'escalade elle-même
    remonte au pasteur **à propos du responsable**, jamais du membre."""
    assert is_listable_to_subject(_fact(FactKind.THIRD_PARTY_CONCERN, source=WATCH_UI)) is False


def test_the_gestures_of_a_responsable_are_his_work_not_the_life_of_the_member():
    """« J'ai vu », « j'ai appelé », « je ferme » : le travail du responsable sur un cas."""
    for kind in CASE_ACTS:
        assert is_listable_to_subject(_fact(kind)) is False


def test_a_leaders_judgement_is_not_the_members_gesture():
    """Une qualification d'absence est un jugement posé sur elle, pas un acte d'elle."""
    assert is_listable_to_subject(_fact(FactKind.QUALIFICATION_SET)) is False
    assert is_listable_to_subject(_fact(FactKind.GROUP_TEMPERATURE)) is False


# --- Et sa contrepartie, qui rend la frontière tenable -----------------------------------


async def test_stopping_the_contact_needs_no_reason():
    """Exiger une justification pour qu'on cesse de vous contacter fait de la sortie une
    négociation. « Non » n'a jamais à s'expliquer."""
    tenant, member = uuid4(), uuid4()
    signals, checks = FakeSignals(), FakeChecks()
    case = _case(signals, tenant=tenant, subject=member)

    stopped = await StopContactingMe(signals, checks, clock=lambda: _NOW).execute(
        tenant_id=tenant, actor_account_id=member
    )

    assert stopped.had_open_case is True
    assert case.outcome is SignalOutcome.DO_NOT_CONTACT
    assert case.status is SignalStatus.CLOSED


async def test_the_stop_is_absorbing_and_nothing_reopens_it():
    """Une veille dont on ne peut pas sortir est un fichage."""
    tenant, member = uuid4(), uuid4()
    signals = FakeSignals()
    case = _case(signals, tenant=tenant, subject=member)
    await StopContactingMe(signals, None, clock=lambda: _NOW).execute(
        tenant_id=tenant, actor_account_id=member
    )

    assert case.is_absorbing is True
    assert member in await signals.do_not_contact_ids(tenant)


async def test_stopping_cancels_the_deadlines_that_were_already_posted():
    """Sans ça, la personne qui vient de demander qu'on cesse recevrait un rappel posé trois
    semaines plus tôt — et la parole qu'on s'était engagé à respecter serait démentie par une
    notification automatique."""
    tenant, member = uuid4(), uuid4()
    signals, checks = FakeSignals(), FakeChecks()
    _case(signals, tenant=tenant, subject=member)
    await checks.schedule(
        subject_id=member, tenant_id=tenant, kind="absence_watch", reason="…",
        due_at=_NOW + timedelta(days=7), at=_NOW,
    )

    await StopContactingMe(signals, checks, clock=lambda: _NOW).execute(
        tenant_id=tenant, actor_account_id=member
    )

    assert all(c["cancelled_at"] is not None for c in checks.rows)


async def test_someone_without_an_open_case_can_still_stop_everything():
    """On n'a pas besoin d'être signalé pour demander qu'on ne le soit jamais."""
    tenant, member = uuid4(), uuid4()
    signals, checks = FakeSignals(), FakeChecks()

    stopped = await StopContactingMe(signals, checks, clock=lambda: _NOW).execute(
        tenant_id=tenant, actor_account_id=member
    )

    assert stopped.had_open_case is False
    assert "ne vous contacterons plus" in stopped.message


# --- Le signe de vie ---------------------------------------------------------------------


def _life_sign(subject):
    return EnrichCase(
        subject_id=subject,
        reason="A déposé un sujet de reconnaissance.",
        origin=CasePriority.DECLARED,
        annotation="A déposé un sujet de reconnaissance.",
        downgrade=True,
        life_sign=True,
        at=_NOW,
    )


def _state(*, subject, held):
    return WatchStateView(
        live_cases=(
            LiveCaseView(
                id=uuid4(), subject_id=subject, owner_id=uuid4(),
                origin=CasePriority.ABSENCE.value, is_held=held,
            ),
        )
    )


def test_a_life_sign_on_an_open_case_enriches_and_never_closes():
    """Déposer une reconnaissance prouve qu'on est vivant — pas qu'on est revenu en cellule.

    Éteindre le cas là-dessus serait la même erreur que fermer un deuil parce que la personne est
    venue au culte : confondre une présence avec un état."""
    subject = uuid4()

    decided = arbitrate([_life_sign(subject)], _state(subject=subject, held=False))

    (effect,) = decided.admitted
    assert isinstance(effect, EnrichCase)
    assert effect.downgrade is True


def test_a_life_sign_on_a_held_case_retracts_it():
    """Personne ne l'avait vu, aucune promesse n'avait été faite : le retirer ne trahit rien.

    Et ça évite de faire appeler quelqu'un qui vient précisément de donner de ses nouvelles."""
    subject = uuid4()

    decided = arbitrate([_life_sign(subject)], _state(subject=subject, held=True))

    (effect,) = decided.admitted
    assert isinstance(effect, RetractHeld)


async def test_the_retraction_says_it_was_not_false_but_moot():
    """`RETRACTED` seul mélangeait deux choses : un cas faux et un cas sans objet."""
    tenant, member = uuid4(), uuid4()
    signals = FakeSignals()
    case = _case(signals, tenant=tenant, subject=member, status=SignalStatus.HELD)

    await signals.retract_held(subject_id=member, tenant_id=tenant, at=_NOW)

    assert case.status is SignalStatus.RETRACTED
    assert case.retraction_cause == RetractionCause.SUPERSEDED_BY_LIFE_SIGN.value
    assert case.counts_as_resolved is False  # hors des métriques de résolution


async def test_a_case_someone_has_seen_is_never_erased():
    """On n'efface pas ce qui a été lu : quelqu'un s'est peut-être déjà déplacé."""
    tenant, member = uuid4(), uuid4()
    signals = FakeSignals()
    case = _case(signals, tenant=tenant, subject=member, status=SignalStatus.ASSIGNED)

    await signals.retract_held(subject_id=member, tenant_id=tenant, at=_NOW)

    assert case.status is SignalStatus.ASSIGNED


def test_no_extinguish_cause_is_named_after_a_life_sign():
    """L'invariant qui empêche la tentation de revenir : il n'y a pas de forme pour le dire.

    Une cause « signe de vie » ferait du dépôt d'une reconnaissance une clôture système — la
    deuxième du produit, et celle qui affaiblirait la règle protégeant du nettoyage automatique."""
    assert not any(
        "life" in cause.value or "gratitude" in cause.value for cause in ExtinguishCause
    )
