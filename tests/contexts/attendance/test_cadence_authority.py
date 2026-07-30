"""Qui a le droit de déclarer un rythme, d'acquitter une occurrence, de suspendre l'église.

Ces commandes existaient sans aucune garde : leur docstring renvoyait l'autorisation « à la
couche interface, câblée ultérieurement ». Elles n'étaient appelées par personne, donc le report
ne coûtait rien — jusqu'au jour où on branche une surface. C'est le genre de dette qui ne se
paie qu'une fois, au pire moment.

**L'acquittement est la surface d'échappatoire du module.** Il retire une occurrence du
dénominateur de couverture : celui qui peut la poser doit être celui qui répond du groupe, pas
n'importe qui sachant pointer une présence.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.attendance.application.commands.manage_cadence import (
    AcknowledgeOccurrence,
    DeclareCadence,
    SuspendChurch,
)
from app.contexts.attendance.domain.cadence import (
    AcknowledgementReason,
    CadenceFrequency,
    SuspensionReason,
)
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.iam.domain.permissions import Permission

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


class _Groups:
    def __init__(self, tenant):
        self._tenant = tenant

    async def get(self, group_id):
        from types import SimpleNamespace

        return SimpleNamespace(id=group_id, tenant_id=self._tenant, path=f"/{group_id}/")


class _Access:
    """Enregistre ce qui a été **exigé**, et refuse si l'acteur n'est pas dans la liste."""

    def __init__(self, allowed=()):
        self.allowed = set(allowed)
        self.demanded: list[Permission] = []

    async def ensure_can(self, *, actor_account_id, group, permission):
        self.demanded.append(permission)
        if actor_account_id not in self.allowed:
            raise UnauthorizedGroupActionError("Non autorisé.", details={})

    async def ensure_church_wide(self, *, actor_account_id, tenant_id, permission):
        self.demanded.append(permission)
        if actor_account_id not in self.allowed:
            raise UnauthorizedGroupActionError("Non autorisé.", details={})


class _Cadences:
    def __init__(self):
        self.rows = []

    async def add(self, cadence):
        self.rows.append(cadence)

    async def get_active_by_group(self, group_id):
        return next((c for c in self.rows if c.group_id == group_id), None)


class _Acks:
    def __init__(self):
        self.rows = []

    async def add(self, ack):
        self.rows.append(ack)

    async def get_for(self, group_id, occurrence_date):
        return next(
            (
                a
                for a in self.rows
                if a.group_id == group_id and a.occurrence_date == occurrence_date
            ),
            None,
        )


class _Suspensions:
    def __init__(self):
        self.rows = []

    async def add(self, suspension):
        self.rows.append(suspension)


async def _declare(cadences, access, *, actor, tenant, group):
    return await DeclareCadence(
        cadences, _Groups(tenant), access, clock=lambda: _NOW
    ).execute(
        actor_account_id=actor, tenant_id=tenant, group_id=group,
        frequency=CadenceFrequency.WEEKLY, anchor_date=_NOW, active_from=_NOW, weekday=2,
    )


async def _acknowledge(acks, access, *, actor, tenant, group):
    return await AcknowledgeOccurrence(
        acks, _Groups(tenant), access, clock=lambda: _NOW
    ).execute(
        actor_account_id=actor, tenant_id=tenant, group_id=group,
        occurrence_date=_NOW, reason=AcknowledgementReason.HOLIDAY,
    )


# --- La cadence -------------------------------------------------------------------------------


async def test_the_group_leader_declares_the_rhythm():
    leader, tenant, group = uuid4(), uuid4(), uuid4()
    cadences, access = _Cadences(), _Access({leader})

    await _declare(cadences, access, actor=leader, tenant=tenant, group=group)

    assert len(cadences.rows) == 1
    assert access.demanded == [Permission.MANAGE_GROUP]


async def test_a_stranger_declares_nothing():
    tenant, group = uuid4(), uuid4()
    cadences, access = _Cadences(), _Access()

    with pytest.raises(UnauthorizedGroupActionError):
        await _declare(cadences, access, actor=uuid4(), tenant=tenant, group=group)

    assert cadences.rows == []


# --- L'acquittement : la surface d'échappatoire -----------------------------------------------


async def test_acknowledging_demands_responsibility_for_the_group():
    """Pas `RECORD_ATTENDANCE` : acquitter **retire une occurrence du dénominateur**.

    Le confier à quiconque sait pointer ouvrirait la porte à vider sa couverture sans jamais
    tenir de rencontre — et le trou disparaîtrait des écrans au lieu d'y monter."""
    leader, tenant, group = uuid4(), uuid4(), uuid4()
    acks, access = _Acks(), _Access({leader})

    await _acknowledge(acks, access, actor=leader, tenant=tenant, group=group)

    assert access.demanded == [Permission.MANAGE_GROUP]
    assert Permission.RECORD_ATTENDANCE not in access.demanded


async def test_a_stranger_cannot_silence_an_occurrence():
    tenant, group = uuid4(), uuid4()
    acks, access = _Acks(), _Access()

    with pytest.raises(UnauthorizedGroupActionError):
        await _acknowledge(acks, access, actor=uuid4(), tenant=tenant, group=group)

    assert acks.rows == []


async def test_acknowledging_twice_stays_idempotent_under_authority():
    """Un responsable qui tape deux fois n'a pas à se demander s'il a créé un doublon."""
    leader, tenant, group = uuid4(), uuid4(), uuid4()
    acks, access = _Acks(), _Access({leader})

    first = await _acknowledge(acks, access, actor=leader, tenant=tenant, group=group)
    second = await _acknowledge(acks, access, actor=leader, tenant=tenant, group=group)

    assert first.id == second.id
    assert len(acks.rows) == 1


# --- La suspension : une décision d'église ----------------------------------------------------


async def test_suspending_the_church_is_not_a_group_decision():
    """Elle acquitte **tous** les groupes : elle ne se prend pas depuis l'un d'eux."""
    pastor, tenant = uuid4(), uuid4()
    suspensions, access = _Suspensions(), _Access({pastor})

    await SuspendChurch(suspensions, access, clock=lambda: _NOW).execute(
        actor_account_id=pastor, tenant_id=tenant, reason=SuspensionReason.HOLIDAY,
        from_date=_NOW, to_date=_NOW,
    )

    assert len(suspensions.rows) == 1


async def test_a_group_leader_cannot_suspend_the_whole_church():
    tenant = uuid4()
    suspensions, access = _Suspensions(), _Access()

    with pytest.raises(UnauthorizedGroupActionError):
        await SuspendChurch(suspensions, access, clock=lambda: _NOW).execute(
            actor_account_id=uuid4(), tenant_id=tenant, reason=SuspensionReason.HOLIDAY,
            from_date=_NOW, to_date=_NOW,
        )

    assert suspensions.rows == []


async def test_authority_is_checked_before_anything_is_written():
    """Un refus ne doit laisser aucune trace — ni cadence, ni validation partielle."""
    tenant, group = uuid4(), uuid4()
    cadences, access = _Cadences(), _Access()

    with pytest.raises(UnauthorizedGroupActionError):
        # Cadence hebdomadaire **sans jour de semaine** : invalide *et* non autorisée. C'est
        # l'autorisation qui doit parler la première, sinon le message d'erreur révèle à un
        # inconnu ce qui existe derrière la porte.
        await DeclareCadence(
            cadences, _Groups(tenant), access, clock=lambda: _NOW
        ).execute(
            actor_account_id=uuid4(), tenant_id=tenant, group_id=group,
            frequency=CadenceFrequency.WEEKLY, anchor_date=_NOW, active_from=_NOW,
        )

    assert cadences.rows == []
