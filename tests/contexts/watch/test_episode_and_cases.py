"""L'épisode, et la file du responsable.

Awa a été absente en janvier ; Jean l'a appelée, elle allait mal, il a fermé le cas le 3 février.
Elle redécroche en mars. Sans mémoire, le nouveau cas s'affiche exactement comme le premier — et
Jean rappelle en ouvrant par « je vois que tu n'es pas venue », alors qu'il lui a parlé six
semaines plus tôt. C'est le moment précis où l'outil cesse d'être du soin.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.my_cases import CloseCase, ListMyCases, SeeCase
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.errors import (
    CaseNotFoundError,
    HumanClosureRequiredError,
    NotYourCaseError,
)
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from tests.contexts.watch.fakes import FakeSignals, case_acts_for

_JAN = datetime(2026, 1, 12, tzinfo=UTC)
_FEB = datetime(2026, 2, 3, tzinfo=UTC)
_MAR = datetime(2026, 3, 20, tzinfo=UTC)


async def _open(signals, *, subject, tenant, owner=None, at=_MAR, origin="absence"):
    await signals.open_case(
        subject_id=subject, tenant_id=tenant, origin=origin,
        reason="Sans nouvelles depuis 4 semaines.", opened_at=at,
        expires_at=None, source_ref=uuid4(), held=False, owner_account_id=owner,
    )


def _closed(*, tenant, subject, outcome, closed_at, owner=None) -> Signal:
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=subject, origin=CasePriority.ABSENCE,
        reason="Sans nouvelles depuis 4 semaines.", opened_at=_JAN,
        status=SignalStatus.ASSIGNED, owner_account_id=owner,
    )
    case.close(outcome=outcome, at=closed_at, closed_by_account_id=owner or uuid4())
    return case


# --- L'épisode ------------------------------------------------------------------------------


async def test_a_first_case_opens_its_own_episode():
    signals, awa, tenant = FakeSignals(), uuid4(), uuid4()

    await _open(signals, subject=awa, tenant=tenant)

    (case,) = signals.rows
    assert case.episode_id == case.id
    assert case.occurrence_number == 1
    assert case.is_reopening is False
    assert case.previous_case_note is None


async def test_a_reopening_carries_the_sentence():
    """« Cas précédent clos le 3 février — repris contact, situation suivie. »"""
    signals, awa, tenant, jean = FakeSignals(), uuid4(), uuid4(), uuid4()
    first = _closed(
        tenant=tenant, subject=awa, outcome=SignalOutcome.FOLLOWED,
        closed_at=_FEB, owner=jean,
    )
    signals.rows.append(first)

    await _open(signals, subject=awa, tenant=tenant, owner=jean)

    second = signals.rows[-1]
    assert second.occurrence_number == 2
    assert second.episode_id == first.episode_id  # la même chaîne
    assert (
        second.previous_case_note
        == "Cas précédent clos le 3 février — repris contact, situation suivie."
    )
    # La raison d'aujourd'hui reste celle d'aujourd'hui : la phrase s'ajoute, elle ne remplace pas.
    assert second.reason == "Sans nouvelles depuis 4 semaines."


async def test_the_first_of_the_month_reads_as_a_date_someone_would_say():
    signals, awa, tenant = FakeSignals(), uuid4(), uuid4()
    signals.rows.append(
        _closed(
            tenant=tenant, subject=awa, outcome=SignalOutcome.RESTORED,
            closed_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
    )

    await _open(signals, subject=awa, tenant=tenant)

    assert "1er avril" in signals.rows[-1].previous_case_note


async def test_the_counter_keeps_climbing_across_the_chain():
    """Le troisième cas d'affilée ne doit pas s'afficher comme le premier."""
    signals, awa, tenant = FakeSignals(), uuid4(), uuid4()
    signals.rows.append(
        _closed(tenant=tenant, subject=awa, outcome=SignalOutcome.NO_RETURN, closed_at=_FEB)
    )
    await _open(signals, subject=awa, tenant=tenant, at=_MAR)
    signals.rows[-1].close(
        outcome=SignalOutcome.FOLLOWED, at=_MAR + timedelta(days=5),
        closed_by_account_id=uuid4(),
    )

    await _open(signals, subject=awa, tenant=tenant, at=_MAR + timedelta(days=40))

    assert signals.rows[-1].occurrence_number == 3


async def test_a_retracted_case_transmits_nothing():
    """Un cas devenu **faux** n'a rien résolu : lui faire porter une issue serait un mensonge."""
    signals, awa, tenant = FakeSignals(), uuid4(), uuid4()
    retracted = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=awa, origin=CasePriority.ABSENCE,
        reason="Sans nouvelles.", opened_at=_JAN,
    )
    retracted.retract(at=_FEB)
    signals.rows.append(retracted)

    await _open(signals, subject=awa, tenant=tenant)

    second = signals.rows[-1]
    assert second.occurrence_number == 1
    assert second.previous_case_note is None


def test_every_outcome_can_be_spoken():
    """Une issue sans libellé ferait planter la phrase au pire moment — à la réouverture."""
    for outcome in SignalOutcome:
        case = Signal(
            id=uuid4(), tenant_id=uuid4(), subject_id=uuid4(), origin=CasePriority.ABSENCE,
            reason="peu importe", opened_at=_JAN,
            previous_outcome=outcome, previous_closed_at=_FEB,
        )
        assert case.previous_case_note.startswith("Cas précédent clos le 3 février — ")


# --- La file du responsable -------------------------------------------------------------------


async def test_my_file_is_ordered_by_urgency_then_by_age():
    """Le plus urgent d'abord ; à origine égale, le décrochage le plus frais."""
    signals, jean, tenant = FakeSignals(), uuid4(), uuid4()
    await _open(signals, subject=uuid4(), tenant=tenant, owner=jean, origin="absence")
    await _open(signals, subject=uuid4(), tenant=tenant, owner=jean, origin="declared")
    await _open(signals, subject=uuid4(), tenant=tenant, owner=jean, origin="concern")

    mine = await ListMyCases(signals).execute(account_id=jean, tenant_id=tenant)

    assert [c.priority for c in mine] == ["declared", "concern", "absence"]


async def test_a_held_case_is_not_in_the_file():
    """Il est détecté, pas encore sur ses épaules. L'afficher ferait mentir le plafond."""
    signals, jean, tenant = FakeSignals(), uuid4(), uuid4()
    await signals.open_case(
        subject_id=uuid4(), tenant_id=tenant, origin="absence", reason="silence",
        opened_at=_MAR, expires_at=None, source_ref=uuid4(), held=True,
        owner_account_id=jean,
    )

    assert await ListMyCases(signals).execute(account_id=jean, tenant_id=tenant) == []


async def test_the_file_carries_the_reopening_sentence():
    """Sans elle, la mémoire existe en base et n'arrive jamais devant les yeux de quelqu'un."""
    signals, awa, jean, tenant = FakeSignals(), uuid4(), uuid4(), uuid4()
    signals.rows.append(
        _closed(
            tenant=tenant, subject=awa, outcome=SignalOutcome.FOLLOWED,
            closed_at=_FEB, owner=jean,
        )
    )
    await _open(signals, subject=awa, tenant=tenant, owner=jean)

    (case,) = await ListMyCases(signals).execute(account_id=jean, tenant_id=tenant)

    assert "3 février" in case.previous_case_note
    assert case.occurrence_number == 2


async def test_opening_a_case_stamps_the_metric_that_anticipates_abandonment():
    signals, jean, tenant = FakeSignals(), uuid4(), uuid4()
    await _open(signals, subject=uuid4(), tenant=tenant, owner=jean)
    case = signals.rows[0]

    await SeeCase(signals, case_acts_for(signals, clock=lambda: _MAR), clock=lambda: _MAR).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    assert case.first_seen_at == _MAR


async def test_seeing_a_case_twice_never_moves_the_first_time():
    signals, jean, tenant = FakeSignals(), uuid4(), uuid4()
    await _open(signals, subject=uuid4(), tenant=tenant, owner=jean)
    case = signals.rows[0]
    see = SeeCase(signals, case_acts_for(signals, clock=lambda: _MAR), clock=lambda: _MAR)

    await see.execute(signal_id=case.id, tenant_id=tenant, actor_account_id=jean)
    later = lambda: _MAR + timedelta(days=3)  # noqa: E731 — une horloge, pas une fonction métier
    command = SeeCase(signals, case_acts_for(signals, clock=later), clock=later)
    await command.execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    assert case.first_seen_at == _MAR


# --- La clôture ---------------------------------------------------------------------------------


async def test_closing_records_who_did_it():
    """C'est ce qui distingue une clôture d'un nettoyage de file."""
    signals, jean, tenant = FakeSignals(), uuid4(), uuid4()
    await _open(signals, subject=uuid4(), tenant=tenant, owner=jean)
    case = signals.rows[0]

    command = CloseCase(
        signals, case_acts_for(signals, clock=lambda: _MAR), clock=lambda: _MAR
    )
    await command.execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
        outcome=SignalOutcome.FOLLOWED,
    )

    assert case.status is SignalStatus.CLOSED
    assert case.closed_by_account_id == jean


async def test_nobody_closes_a_case_confided_to_someone_else():
    """Deux responsables sur la même personne, c'est le double appel du même soir."""
    signals, jean, marie, tenant = FakeSignals(), uuid4(), uuid4(), uuid4()
    await _open(signals, subject=uuid4(), tenant=tenant, owner=jean)
    case = signals.rows[0]

    with pytest.raises(NotYourCaseError):
        command = CloseCase(
            signals, case_acts_for(signals, clock=lambda: _MAR), clock=lambda: _MAR
        )
        await command.execute(
            signal_id=case.id, tenant_id=tenant, actor_account_id=marie,
            outcome=SignalOutcome.FOLLOWED,
        )

    assert case.is_live is True


async def test_an_unowned_case_can_be_taken():
    """Un cas que personne ne porte est justement le trou qu'on veut voir se combler."""
    signals, marie, tenant = FakeSignals(), uuid4(), uuid4()
    await _open(signals, subject=uuid4(), tenant=tenant, owner=None)
    case = signals.rows[0]

    command = CloseCase(
        signals, case_acts_for(signals, clock=lambda: _MAR), clock=lambda: _MAR
    )
    await command.execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=marie,
        outcome=SignalOutcome.FOLLOWED,
    )

    assert case.closed_by_account_id == marie


async def test_a_case_from_another_church_does_not_exist_here():
    signals, jean, tenant = FakeSignals(), uuid4(), uuid4()
    await _open(signals, subject=uuid4(), tenant=uuid4(), owner=jean)
    case = signals.rows[0]

    with pytest.raises(CaseNotFoundError):
        command = CloseCase(
            signals, case_acts_for(signals, clock=lambda: _MAR), clock=lambda: _MAR
        )
        await command.execute(
            signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
            outcome=SignalOutcome.FOLLOWED,
        )


async def test_the_service_cannot_bypass_the_aggregate():
    """La règle de clôture vit dans l'agrégat : ce service ne saurait pas la contourner.

    Une issue absorbante ferme la porte à clé — et le cas déjà clos n'a plus de transition."""
    signals, jean, tenant = FakeSignals(), uuid4(), uuid4()
    await _open(signals, subject=uuid4(), tenant=tenant, owner=jean)
    case = signals.rows[0]
    close = CloseCase(signals, case_acts_for(signals, clock=lambda: _MAR), clock=lambda: _MAR)
    await close.execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
        outcome=SignalOutcome.DECEASED,
    )

    with pytest.raises(Exception) as raised:
        await close.execute(
            signal_id=case.id, tenant_id=tenant, actor_account_id=jean,
            outcome=SignalOutcome.FOLLOWED,
        )

    assert not isinstance(raised.value, HumanClosureRequiredError)  # bien l'absorbant
