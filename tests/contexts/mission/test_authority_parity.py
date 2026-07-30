"""Le périmètre d'autorisation **n'a pas bougé** en passant au `Signal`.

C'est le risque le plus discret de tout le raccordement : la règle d'hier était fine — inviteur
pour un chercheur personnel, responsable de groupe sinon — et elle correspond exactement à la
cascade `INVITER` / `GROUP_LEAD`. En basculant le geste sur le cas, il aurait été facile de
glisser vers « le propriétaire du cas peut agir », ce qui aurait ouvert l'accès à quiconque se
retrouve propriétaire par escalade ou par repli sur l'admin.

**À périmètre égal, pas plus large.** Ces tests énumèrent qui pouvait agir avant, vérifient que
c'est exactement qui peut agir maintenant, et — le plus important — que la propriété du cas ne
donne **aucun** droit qu'elle ne donnait pas.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.iam.domain.enums import RoleCode
from app.contexts.mission.application.commands.accompany import (
    AccompanySeeker,
    CloseSeeker,
)
from app.contexts.mission.domain.aggregates import Seeker
from app.contexts.mission.domain.enums import SeekerStatus
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.signal import Signal, SignalStatus
from tests.contexts.mission.test_mission import (
    _access,
    _cell,
    _FakeGroups,
    _FakeMemberships,
    _FakeSeekers,
    _member,
)
from tests.contexts.watch.fakes import FakeSignals

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _seeker(tenant, *, account=None, group=None) -> Seeker:
    return Seeker(
        id=uuid4(), tenant_id=tenant, link_id=uuid4(),
        inviter_account_id=account, inviter_group_id=group,
        name="Koffi", phone=None, status=SeekerStatus.ACCEPTED, created_at=_NOW,
        person_account_id=uuid4(),
    )


def _case_for(seeker, *, owner) -> FakeSignals:
    signals = FakeSignals()
    signals.rows.append(
        Signal(
            id=uuid4(), tenant_id=seeker.tenant_id, subject_id=seeker.person_account_id,
            origin=CasePriority.DECLARED, reason="…", opened_at=_NOW,
            status=SignalStatus.ASSIGNED if owner else SignalStatus.OPEN,
            owner_account_id=owner,
        )
    )
    return signals


def _commands(seeker, ms, groups, signals):
    return (
        AccompanySeeker(
            _FakeSeekers([seeker]), groups, _access(ms), signals, clock=lambda: _NOW
        ),
        CloseSeeker(
            _FakeSeekers([seeker]), groups, _access(ms), signals, clock=lambda: _NOW
        ),
    )


# --- Chercheur personnel : son inviteur, et lui seul ---------------------------------------


async def test_only_the_inviter_acts_on_a_personal_seeker():
    inviter, tenant = uuid4(), uuid4()
    seeker = _seeker(tenant, account=inviter)
    signals = _case_for(seeker, owner=inviter)
    accompany, close = _commands(seeker, _FakeMemberships(), _FakeGroups(), signals)

    assert await accompany.execute(actor_account_id=inviter, seeker_id=seeker.id)
    assert await close.execute(actor_account_id=inviter, seeker_id=seeker.id)


@pytest.mark.parametrize("command_index", [0, 1])
async def test_a_stranger_is_refused_on_both_gestures(command_index):
    inviter, tenant = uuid4(), uuid4()
    seeker = _seeker(tenant, account=inviter)
    signals = _case_for(seeker, owner=inviter)
    command = _commands(seeker, _FakeMemberships(), _FakeGroups(), signals)[command_index]

    with pytest.raises(UnauthorizedGroupActionError):
        await command.execute(actor_account_id=uuid4(), seeker_id=seeker.id)


async def test_owning_the_case_grants_nothing_it_did_not_grant_before():
    """**Le cœur du test.** Un pasteur devenu propriétaire du cas par escalade — ou l'admin sur
    lequel la résolution se replie quand aucun référent n'existe — n'a jamais eu le droit
    d'accompagner un chercheur personnel. Le raccordement ne le lui donne pas."""
    inviter, pastor, tenant = uuid4(), uuid4(), uuid4()
    seeker = _seeker(tenant, account=inviter)
    # Le cas appartient au pasteur : c'est exactement la situation qui pourrait élargir l'accès.
    signals = _case_for(seeker, owner=pastor)
    accompany, close = _commands(seeker, _FakeMemberships(), _FakeGroups(), signals)

    with pytest.raises(UnauthorizedGroupActionError):
        await accompany.execute(actor_account_id=pastor, seeker_id=seeker.id)
    with pytest.raises(UnauthorizedGroupActionError):
        await close.execute(actor_account_id=pastor, seeker_id=seeker.id)

    assert signals.rows[0].is_live is True  # rien n'a bougé


# --- Chercheur de groupe : un responsable du groupe ------------------------------------------


async def test_a_group_leader_acts_on_a_group_seeker():
    leader, tenant = uuid4(), uuid4()
    cell = _cell(tenant)
    seeker = _seeker(tenant, group=cell.id)
    ms = _FakeMemberships([_member(leader, tenant, (RoleCode.GROUP_LEADER, cell.id))])
    accompany, _ = _commands(seeker, ms, _FakeGroups([cell]), _case_for(seeker, owner=None))

    assert await accompany.execute(actor_account_id=leader, seeker_id=seeker.id)


async def test_a_leader_of_another_cell_is_refused():
    """L'autorité est **sur ce groupe-là**, pas sur le titre de responsable."""
    leader, tenant = uuid4(), uuid4()
    cell, other = _cell(tenant), _cell(tenant)
    seeker = _seeker(tenant, group=cell.id)
    ms = _FakeMemberships([_member(leader, tenant, (RoleCode.GROUP_LEADER, other.id))])
    accompany, _ = _commands(
        seeker, ms, _FakeGroups([cell, other]), _case_for(seeker, owner=None)
    )

    with pytest.raises(UnauthorizedGroupActionError):
        await accompany.execute(actor_account_id=leader, seeker_id=seeker.id)


async def test_an_unowned_case_still_refuses_a_stranger():
    """Dans la file de veille, un cas sans propriétaire est **prenable** — c'est le trou qu'on
    veut voir se combler. Ici non : le chercheur appartient à qui l'a amené, et cette porte-là
    ne s'ouvre pas parce que l'autre s'est ouverte."""
    tenant = uuid4()
    cell = _cell(tenant)
    seeker = _seeker(tenant, group=cell.id)
    accompany, _ = _commands(
        seeker, _FakeMemberships(), _FakeGroups([cell]), _case_for(seeker, owner=None)
    )

    with pytest.raises(UnauthorizedGroupActionError):
        await accompany.execute(actor_account_id=uuid4(), seeker_id=seeker.id)
