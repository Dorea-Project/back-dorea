"""La relève des retenus — « retenu ≠ perdu » n'est vrai que si quelque chose les relâche.

Le plafond de débit protège le responsable : au-delà de N cas ouverts, il ne reçoit plus rien de
nouveau. Sans cette passe, la protection devenait un oubli — `Signal.release()` n'était appelé de
nulle part, et un cas retenu le restait indéfiniment. Le produit aurait détecté quelque chose que
personne n'aurait jamais vu.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.release_held import ReleaseHeldCases
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam
from app.contexts.watch.domain.signal import Signal, SignalStatus
from tests.contexts.watch.fakes import FakeSignals

_NOW = datetime(2026, 8, 2, tzinfo=UTC)


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


def _case(signals, *, tenant, owner, status, origin=CasePriority.ABSENCE, days_ago=1):
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=uuid4(), origin=origin,
        reason="Sans nouvelles.", opened_at=_NOW - timedelta(days=days_ago),
        status=status, owner_account_id=owner,
    )
    signals.rows.append(case)
    return case


def _release(signals, **params):
    return ReleaseHeldCases(signals, _Params(**params), clock=lambda: _NOW)


async def test_a_held_case_comes_out_when_the_cap_frees_up():
    tenant, lead = uuid4(), uuid4()
    signals = FakeSignals()
    _case(signals, tenant=tenant, owner=lead, status=SignalStatus.ASSIGNED)
    held = _case(signals, tenant=tenant, owner=lead, status=SignalStatus.HELD)

    report = await _release(signals).execute(tenant_id=tenant)

    assert report.released == 1
    assert report.still_held == 0
    # Il va **directement** chez son destinataire : le faire passer par OPEN le rendrait
    # « prenable » par n'importe quel responsable de la portée.
    assert held.status is SignalStatus.ASSIGNED
    assert held.owner_account_id == lead


async def test_the_cap_is_respected_or_it_would_not_be_a_cap():
    """Relâcher au-delà du plafond, c'est le supprimer une nuit sur deux — et noyer celui
    qu'il protège."""
    tenant, lead = uuid4(), uuid4()
    signals = FakeSignals()
    for _ in range(4):
        _case(signals, tenant=tenant, owner=lead, status=SignalStatus.ASSIGNED)
    for _ in range(3):
        _case(signals, tenant=tenant, owner=lead, status=SignalStatus.HELD)

    report = await _release(signals, **{WatchParam.OPEN_CASES_CAP: 5}).execute(
        tenant_id=tenant
    )

    assert report.released == 1  # une seule place était libre
    assert report.still_held == 2
    assert report.has_backlog is True


async def test_the_order_is_the_arbitration_order_not_the_storage_order():
    """L'origine du dire d'abord, puis le plus ancien. La passe n'invente aucune priorité."""
    tenant, lead = uuid4(), uuid4()
    signals = FakeSignals()
    absence = _case(
        signals, tenant=tenant, owner=lead, status=SignalStatus.HELD,
        origin=CasePriority.ABSENCE, days_ago=30,
    )
    concern = _case(
        signals, tenant=tenant, owner=lead, status=SignalStatus.HELD,
        origin=CasePriority.CONCERN, days_ago=1,
    )

    await _release(signals, **{WatchParam.OPEN_CASES_CAP: 1}).execute(tenant_id=tenant)

    # La parole d'un tiers passe devant une absence calculée, même plus ancienne.
    assert concern.status is SignalStatus.ASSIGNED
    assert absence.status is SignalStatus.HELD


async def test_each_owner_has_his_own_budget():
    """Le plafond pèse par responsable : la file de l'un ne bloque pas celle de l'autre."""
    tenant, busy, free = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    for _ in range(5):
        _case(signals, tenant=tenant, owner=busy, status=SignalStatus.ASSIGNED)
    blocked = _case(signals, tenant=tenant, owner=busy, status=SignalStatus.HELD)
    released = _case(signals, tenant=tenant, owner=free, status=SignalStatus.HELD)

    report = await _release(signals).execute(tenant_id=tenant)

    assert report.released == 1
    assert released.status is SignalStatus.ASSIGNED
    assert blocked.status is SignalStatus.HELD


async def test_a_permanent_backlog_is_said_never_swallowed():
    """Un arriéré permanent n'est pas un problème de plafond : c'est une détection trop bavarde.

    On remonte alors le seuil de détection — jamais le plafond, sinon on noie le responsable pour
    faire disparaître un indicateur."""
    tenant, lead = uuid4(), uuid4()
    signals = FakeSignals()
    for _ in range(5):
        _case(signals, tenant=tenant, owner=lead, status=SignalStatus.ASSIGNED)
    for _ in range(8):
        _case(signals, tenant=tenant, owner=lead, status=SignalStatus.HELD)

    report = await _release(signals).execute(tenant_id=tenant)

    assert report.released == 0
    assert report.still_held == 8
