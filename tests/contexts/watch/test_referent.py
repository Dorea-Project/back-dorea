"""Le module Referent — cascade, lien primaire dérivé, trous datés.

Le fil rouge : **le référent peut être nul, le propriétaire d'un cas jamais.** Confondre les
deux ferait valoir la couverture 100 % mécaniquement, et la métrique la plus vendable du produit
ne mesurerait plus rien.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.designate_referent import (
    DesignateReferent,
    EndReferentDesignation,
)
from app.contexts.watch.application.referent_ports import (
    GroupDirectory,
    GroupTypePolicyRepository,
    InviterDirectory,
    PeopleDirectory,
    PrimaryGroupOverrideRepository,
    ReferentHistoryRepository,
    ReferentOverrideRepository,
)
from app.contexts.watch.application.referent_resolution import (
    ObserveReferentChange,
    ResolveReferent,
    ResolveSignalOwner,
)
from app.contexts.watch.domain.errors import IneligibleReferentError, SelfReferentError
from app.contexts.watch.domain.referent import (
    GroupTypePolicy,
    MembershipCandidate,
    ReferentChangeCause,
    ReferentOrigin,
    gap_duration,
    pick_primary_group,
)
from tests.contexts.watch.fakes import FakeExclusions

_NOW = datetime(2026, 5, 1, tzinfo=UTC)

# Le défaut livré : ordonné par **durabilité du lien**, pas par intensité.
DEFAULT_POLICIES = {
    "cellule": GroupTypePolicy("cellule", True, 1),
    "ministere": GroupTypePolicy("ministere", True, 2),
    "classe": GroupTypePolicy("classe", True, 3),
}


# --- fakes -------------------------------------------------------------------------------------


class _Policies(GroupTypePolicyRepository):
    def __init__(self, policies=None):
        self._p = policies if policies is not None else DEFAULT_POLICIES

    async def all_for(self, tenant_id):
        return self._p


class _Groups(GroupDirectory):
    def __init__(self, memberships=(), leaders=None):
        self._m = list(memberships)
        self._leaders = leaders or {}

    async def active_memberships(self, account_id, tenant_id):
        return list(self._m)

    async def active_leader_of(self, group_id, tenant_id):
        return self._leaders.get(group_id)


class _People(PeopleDirectory):
    def __init__(self, eligible=(), admin=None, pastor=None):
        self._eligible = set(eligible)
        self._admin, self._pastor = admin, pastor

    async def is_eligible(self, account_id, tenant_id):
        return account_id in self._eligible

    async def church_admin(self, tenant_id):
        return self._admin

    async def pastor(self, tenant_id):
        return self._pastor


class _Inviters(InviterDirectory):
    def __init__(self, inviter=None):
        self._inviter = inviter

    async def inviter_of(self, account_id, tenant_id):
        return self._inviter


class _Overrides(ReferentOverrideRepository):
    def __init__(self, rows=()):
        self.rows = list(rows)

    async def add(self, override):
        self.rows.append(override)

    async def save(self, override):
        pass  # agrégat muté en mémoire

    async def active_for(self, person_id, tenant_id):
        return [o for o in self.rows if o.person_id == person_id and o.is_active]


class _PrimaryOverrides(PrimaryGroupOverrideRepository):
    def __init__(self, row=None):
        self.row = row

    async def add(self, override):
        self.row = override

    async def active_for(self, person_id, tenant_id):
        return self.row


class _History(ReferentHistoryRepository):
    def __init__(self):
        self.rows = []

    async def append(self, entry):
        self.rows.append(entry)

    async def last_for(self, person_id, tenant_id, *, before=None):
        matching = [e for e in self.rows if e.person_id == person_id]
        return matching[-1] if matching else None


def _cell(joined_at=_NOW, group_id=None):
    return MembershipCandidate(group_id or uuid4(), "cellule", joined_at)


def _resolver(*, memberships=(), leaders=None, eligible=(), overrides=None,
              primary=None, inviter=None, exclusions=None, policies=None):
    return ResolveReferent(
        overrides or _Overrides(),
        _PrimaryOverrides(primary),
        _Policies(policies),
        _Groups(memberships, leaders),
        _People(eligible),
        _Inviters(inviter),
        exclusions,
    )


# --- Le rang est une donnée, pas une constante ---------------------------------------------------


def test_the_resolver_knows_no_group_type_name():
    """Le rang vit en table. Enrichir `GroupType` est une insertion de ligne, pas du code.

    On inspecte les **littéraux** du module de résolution : aucun ne doit être le nom d'un type
    de groupe. C'est ce qui garantit que faire bouger l'énumération ne peut pas casser R."""
    import ast
    import inspect

    from app.contexts.groups.domain.enums import GroupType
    from app.contexts.watch.domain import referent

    tree = ast.parse(inspect.getsource(referent))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    known = {t.value for t in GroupType} | {t.name for t in GroupType}

    assert literals & known == set()


def test_durability_orders_the_link_not_intensity():
    """Une classe d'intégration s'achève ; un ministère dure. Le lien durable gagne."""
    classe = MembershipCandidate(uuid4(), "classe", _NOW)
    ministere = MembershipCandidate(uuid4(), "ministere", _NOW)
    cellule = MembershipCandidate(uuid4(), "cellule", _NOW)

    chosen = pick_primary_group([classe, ministere, cellule], DEFAULT_POLICIES)

    assert chosen is cellule


def test_a_type_that_bears_no_veille_cannot_found_a_link():
    """Le garde-fou est en place **avant** le risque : il attend juste sa cible."""
    policies = dict(DEFAULT_POLICIES)
    policies["commission"] = GroupTypePolicy("commission", bears_veille=False, primacy_rank=9)
    commission_only = [MembershipCandidate(uuid4(), "commission", _NOW)]

    assert pick_primary_group(commission_only, policies) is None


def test_an_unknown_group_type_is_ignored_not_crashing():
    """L'enum peut bouger sans que le résolveur casse — c'est tout l'intérêt de la table."""
    inconnu = [MembershipCandidate(uuid4(), "type_ajoute_demain", _NOW)]
    assert pick_primary_group(inconnu, DEFAULT_POLICIES) is None


def test_ties_are_broken_deterministically():
    """Sans le troisième critère, deux exécutions divergent — et la rejouabilité tombe."""
    older = MembershipCandidate(uuid4(), "cellule", _NOW - timedelta(days=100))
    newer = MembershipCandidate(uuid4(), "cellule", _NOW)
    assert pick_primary_group([newer, older], DEFAULT_POLICIES) is older

    same_day_a = MembershipCandidate(uuid4(), "cellule", _NOW)
    same_day_b = MembershipCandidate(uuid4(), "cellule", _NOW)
    first = pick_primary_group([same_day_a, same_day_b], DEFAULT_POLICIES)
    second = pick_primary_group([same_day_b, same_day_a], DEFAULT_POLICIES)
    assert first is not None and first.group_id == second.group_id


def test_a_primary_override_wins_while_the_membership_holds():
    cellule = _cell()
    ministere = MembershipCandidate(uuid4(), "ministere", _NOW)

    chosen = pick_primary_group(
        [cellule, ministere], DEFAULT_POLICIES, override_group_id=ministere.group_id
    )
    assert chosen is ministere

    # Mais un override qui pointe un groupe qu'on a quitté ne vaut plus rien.
    orphan = pick_primary_group([cellule], DEFAULT_POLICIES, override_group_id=uuid4())
    assert orphan is cellule


# --- La cascade ---------------------------------------------------------------------------------


async def test_the_group_lead_is_a_computed_pointer():
    """Remplacer Jean par Paul change le référent de tout le groupe — **sans une écriture**."""
    person, jean, paul, tenant = uuid4(), uuid4(), uuid4(), uuid4()
    cellule = _cell()
    leaders = {cellule.group_id: jean}
    resolver = _resolver(
        memberships=[cellule], leaders=leaders, eligible={jean, paul}
    )

    first = await resolver.execute(person_id=person, tenant_id=tenant, at=_NOW)
    assert first is not None and first.referent_person_id == jean

    leaders[cellule.group_id] = paul  # le seul changement : le rôle, ailleurs

    second = await resolver.execute(person_id=person, tenant_id=tenant, at=_NOW)
    assert second is not None and second.referent_person_id == paul
    assert second.origin is ReferentOrigin.GROUP_LEAD


async def test_a_manual_designation_beats_the_group_lead():
    """Une décision humaine délibérée tient jusqu'à ce qu'un humain la lève."""
    person, jean, marie, tenant = uuid4(), uuid4(), uuid4(), uuid4()
    cellule = _cell()
    overrides = _Overrides()
    resolver = _resolver(
        memberships=[cellule],
        leaders={cellule.group_id: jean},
        eligible={jean, marie},
        overrides=overrides,
    )
    await DesignateReferent(
        overrides, _History(), _People({jean, marie}), resolver,
        id_factory=uuid4, clock=lambda: _NOW,
    ).execute(
        person_id=person, referent_person_id=marie, tenant_id=tenant,
        by_account_id=uuid4(),
    )

    resolved = await resolver.execute(person_id=person, tenant_id=tenant, at=_NOW)

    assert resolved is not None
    assert resolved.referent_person_id == marie
    assert resolved.origin is ReferentOrigin.MANUAL


async def test_an_ineligible_referent_does_not_block_the_cascade():
    """Le responsable a quitté l'église : on continue de descendre, on ne s'arrête pas là."""
    person, parti, inviteur, tenant = uuid4(), uuid4(), uuid4(), uuid4()
    cellule = _cell()
    resolver = _resolver(
        memberships=[cellule],
        leaders={cellule.group_id: parti},
        eligible={inviteur},  # `parti` n'est plus éligible
        inviter=inviteur,
    )

    resolved = await resolver.execute(person_id=person, tenant_id=tenant, at=_NOW)

    assert resolved is not None
    assert resolved.referent_person_id == inviteur
    assert resolved.origin is ReferentOrigin.INVITER


async def test_nobody_is_their_own_referent():
    """Sinon la couverture se remplirait de solitudes."""
    person, tenant = uuid4(), uuid4()
    cellule = _cell()
    resolver = _resolver(
        memberships=[cellule], leaders={cellule.group_id: person}, eligible={person}
    )

    assert await resolver.execute(person_id=person, tenant_id=tenant, at=_NOW) is None


async def test_a_gap_is_data_not_an_error():
    """« Personne ne connaît cette personne » est la donnée la plus utile du module."""
    resolver = _resolver()
    assert await resolver.execute(person_id=uuid4(), tenant_id=uuid4(), at=_NOW) is None


async def test_a_deceased_person_is_not_a_coverage_gap():
    """Un défunt sort du dénominateur — il n'est pas quelqu'un qu'on aurait négligé."""
    person, jean, tenant = uuid4(), uuid4(), uuid4()
    cellule = _cell()
    exclusions = FakeExclusions()

    from app.contexts.attendance.domain.enums import WatchExclusionReason
    from app.contexts.attendance.domain.watch_exclusion import WatchExclusion
    from app.contexts.watch.infrastructure.neutralization_store import (
        AttendanceNeutralizationStore,
    )
    from tests.contexts.watch.fakes import FakeAbsences

    await exclusions.add(
        WatchExclusion(
            id=uuid4(), account_id=person, tenant_id=tenant,
            reason=WatchExclusionReason.DECEASED, excluded_at=_NOW,
            declared_by_account_id=uuid4(),
        )
    )
    resolver = _resolver(
        memberships=[cellule],
        leaders={cellule.group_id: jean},
        eligible={jean},
        exclusions=AttendanceNeutralizationStore(FakeAbsences(), exclusions),
    )

    assert await resolver.execute(person_id=person, tenant_id=tenant, at=_NOW) is None


# --- Le propriétaire de signal n'est JAMAIS nul ---------------------------------------------------


async def test_the_signal_owner_is_the_referent_when_there_is_one():
    person, jean, tenant = uuid4(), uuid4(), uuid4()
    cellule = _cell()
    resolver = _resolver(
        memberships=[cellule], leaders={cellule.group_id: jean}, eligible={jean}
    )
    owner = await ResolveSignalOwner(resolver, _People({jean})).execute(
        person_id=person, tenant_id=tenant, at=_NOW
    )

    assert owner is not None
    assert owner.account_id == jean
    assert owner.is_escalated is False  # pas d'escalade : c'est bien son référent


async def test_a_gap_escalates_with_a_stored_reason():
    """Un pasteur qui reçoit un cas inexplicable l'ignore. Le motif voyage avec le signal."""
    person, admin, tenant = uuid4(), uuid4(), uuid4()
    resolver = _resolver()  # aucun groupe, aucun référent
    people = _People(eligible=set(), admin=admin)

    owner = await ResolveSignalOwner(resolver, people).execute(
        person_id=person, tenant_id=tenant, at=_NOW
    )

    assert owner is not None
    assert owner.account_id == admin
    assert owner.is_escalated is True
    assert "aucun groupe" in owner.escalation_reason


async def test_a_group_without_a_leader_escalates_with_its_own_reason():
    person, admin, tenant = uuid4(), uuid4(), uuid4()
    cellule = _cell()
    resolver = _resolver(memberships=[cellule], leaders={})  # groupe sans responsable
    people = _People(eligible=set(), admin=admin)

    owner = await ResolveSignalOwner(resolver, people).execute(
        person_id=person, tenant_id=tenant, at=_NOW
    )

    assert owner is not None
    assert "responsable actif" in owner.escalation_reason


async def test_escalation_never_fills_the_referent():
    """Si l'escalade remplissait le référent, la couverture vaudrait 100 % pour rien."""
    person, admin, tenant = uuid4(), uuid4(), uuid4()
    resolver = _resolver()
    people = _People(eligible=set(), admin=admin)

    owner = await ResolveSignalOwner(resolver, people).execute(
        person_id=person, tenant_id=tenant, at=_NOW
    )
    referent = await resolver.execute(person_id=person, tenant_id=tenant, at=_NOW)

    assert owner is not None and owner.account_id == admin
    assert referent is None  # le trou reste un trou


# --- Les trous sont datés ----------------------------------------------------------------


async def test_a_gap_is_dated_so_that_it_becomes_actionable():
    """« Sans référent » ne dit rien. « Sans référent depuis quatre mois » se traite."""
    person, jean, tenant = uuid4(), uuid4(), uuid4()
    cellule = _cell()
    leaders = {cellule.group_id: jean}
    history = _History()
    resolver = _resolver(memberships=[cellule], leaders=leaders, eligible={jean})
    observer = ObserveReferentChange(resolver, history, id_factory=uuid4)

    await observer.execute(
        person_id=person, tenant_id=tenant, at=_NOW,
        cause=ReferentChangeCause.JOINED_GROUP,
    )
    leaders.pop(cellule.group_id)  # le responsable s'en va
    depart = _NOW + timedelta(days=3)
    await observer.execute(
        person_id=person, tenant_id=tenant, at=depart,
        cause=ReferentChangeCause.LEADER_CHANGED,
    )

    last = await history.last_for(person, tenant)
    assert last is not None and last.is_gap
    assert gap_duration(last, depart + timedelta(days=120)) == timedelta(days=120)


async def test_an_unchanged_link_writes_nothing():
    """On n'écrit pas de bruit : l'historique doit rester lisible."""
    person, jean, tenant = uuid4(), uuid4(), uuid4()
    cellule = _cell()
    history = _History()
    resolver = _resolver(
        memberships=[cellule], leaders={cellule.group_id: jean}, eligible={jean}
    )
    observer = ObserveReferentChange(resolver, history, id_factory=uuid4)

    await observer.execute(
        person_id=person, tenant_id=tenant, at=_NOW,
        cause=ReferentChangeCause.JOINED_GROUP,
    )
    await observer.execute(
        person_id=person, tenant_id=tenant, at=_NOW + timedelta(days=1),
        cause=ReferentChangeCause.JOINED_GROUP,
    )

    assert len(history.rows) == 1


# --- La désignation est explicite --------------------------------------------------------


async def test_designating_refuses_oneself_and_the_ineligible():
    person, tenant = uuid4(), uuid4()
    overrides, history = _Overrides(), _History()
    resolver = _resolver(overrides=overrides)
    command = DesignateReferent(
        overrides, history, _People(set()), resolver, id_factory=uuid4, clock=lambda: _NOW
    )

    with pytest.raises(SelfReferentError):
        await command.execute(
            person_id=person, referent_person_id=person, tenant_id=tenant,
            by_account_id=uuid4(),
        )
    with pytest.raises(IneligibleReferentError):
        await command.execute(
            person_id=person, referent_person_id=uuid4(), tenant_id=tenant,
            by_account_id=uuid4(),
        )


async def test_ending_a_designation_lets_the_cascade_take_over_again():
    person, jean, marie, tenant = uuid4(), uuid4(), uuid4(), uuid4()
    cellule = _cell()
    overrides, history = _Overrides(), _History()
    resolver = _resolver(
        memberships=[cellule],
        leaders={cellule.group_id: jean},
        eligible={jean, marie},
        overrides=overrides,
    )
    await DesignateReferent(
        overrides, history, _People({jean, marie}), resolver,
        id_factory=uuid4, clock=lambda: _NOW,
    ).execute(
        person_id=person, referent_person_id=marie, tenant_id=tenant,
        by_account_id=uuid4(),
    )

    await EndReferentDesignation(
        overrides, history, resolver, id_factory=uuid4, clock=lambda: _NOW
    ).execute(person_id=person, tenant_id=tenant)

    resolved = await resolver.execute(person_id=person, tenant_id=tenant, at=_NOW)
    assert resolved is not None and resolved.referent_person_id == jean
