"""Le seuil — où la veille commence, et où elle ne commence pas.

*La capsule va partout. La veille s'engage là où un référent existe.*
"""

from datetime import UTC, datetime
from uuid import uuid4

from app.contexts.iam.domain.enums import AccountCreationSource, MembershipStatus
from app.contexts.iam.domain.repositories import AccountRepository
from app.contexts.mission.application.threshold import CrossTheThreshold
from app.contexts.mission.domain.aggregates import MissionLink
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.self_declaration import (
    DeclarationKind,
    SelfDeclarationV1,
)
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.facts import ConsentScope, FactKind
from app.contexts.watch.domain.referent import ReferentOrigin
from app.contexts.watch.domain.registry import MISSION, default_registry
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


# --- fakes -------------------------------------------------------------------------------


class _Accounts(AccountRepository):
    def __init__(self, rows=()):
        self.rows = list(rows)

    async def add(self, account):
        self.rows.append(account)

    async def get_by_id(self, account_id):
        return next((a for a in self.rows if a.id == account_id), None)

    async def get_by_phone(self, phone):
        return next((a for a in self.rows if a.phone_number == phone), None)


class _Enrollment:
    def __init__(self):
        self.enrolled = []

    async def enroll(self, *, account, membership, creation_source, actor_account_id):
        self.enrolled.append((account, membership, creation_source))


class _Overrides:
    def __init__(self):
        self.rows = []

    async def add(self, override):
        self.rows.append(override)

    async def save(self, override):
        pass

    async def active_for(self, person_id, tenant_id):
        return [o for o in self.rows if o.person_id == person_id and o.is_active]


class _Groups:
    def __init__(self, leaders=None):
        self._leaders = leaders or {}

    async def active_memberships(self, account_id, tenant_id):
        return []

    async def active_leader_of(self, group_id, tenant_id):
        return self._leaders.get(group_id)

    async def pastor_of_branch(self, group_id, tenant_id):
        return None


def _link(*, tenant, inviter=None, group=None) -> MissionLink:
    return MissionLink(
        id=uuid4(),
        tenant_id=tenant,
        code="ABCD1234",
        inviter_account_id=inviter,
        inviter_group_id=group,
        created_at=_NOW,
        message=None,
        media_urls=[],
        place_label=None,
        latitude=None,
        longitude=None,
        expires_at=None,
    )


def _engine():
    ledger, signals = FakeLedger(), FakeSignals()
    interpreters = InterpreterRegistry()
    interpreters.register(SelfDeclarationV1())
    store = AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions())
    return (
        Intake(ledger, default_registry(), interpreters, store, signals),
        signals,
        ledger,
    )


def _threshold(*, accounts=None, enrollment=None, overrides=None, groups=None, intake=None):
    return CrossTheThreshold(
        accounts or _Accounts(),
        enrollment or _Enrollment(),
        overrides or _Overrides(),
        groups or _Groups(),
        intake,
    )


# --- La personne existe dès l'acceptation ------------------------------------------------


async def test_accepting_creates_a_person_not_a_parallel_aggregate():
    """Dès qu'un contact existe, c'est quelqu'un — avec un statut, pas une fiche à part."""
    tenant, inviter = uuid4(), uuid4()
    enrollment = _Enrollment()

    crossed = await _threshold(enrollment=enrollment).execute(
        link=_link(tenant=tenant, inviter=inviter),
        name="Awa Traoré", phone="+2250700000001", now=_NOW,
    )

    (account, membership, source) = enrollment.enrolled[0]
    assert account.id == crossed.account_id
    assert account.first_name == "Awa" and account.last_name == "Traoré"
    # Le premier maillon de la chaîne de statuts, pas un sous-membre.
    assert membership.status is MembershipStatus.INVITED
    assert source is AccountCreationSource.MISSION_CAPSULE
    assert crossed.reused_existing is False


async def test_a_known_person_is_never_duplicated():
    """Lui fabriquer un second compte effacerait justement l'histoire qu'on veut garder."""
    from app.contexts.iam.domain.aggregates import Account
    from app.contexts.iam.domain.enums import AccountStatus

    tenant = uuid4()
    known = Account(
        id=uuid4(), phone_number="+2250700000002", status=AccountStatus.ACTIVE,
        first_name="Koffi", last_name="N'Da",
    )
    accounts, enrollment = _Accounts([known]), _Enrollment()

    crossed = await _threshold(accounts=accounts, enrollment=enrollment).execute(
        link=_link(tenant=tenant), name="Koffi", phone="+2250700000002", now=_NOW,
    )

    assert crossed.account_id == known.id
    assert crossed.reused_existing is True
    assert enrollment.enrolled == []  # aucun second compte


# --- Le référent : l'inviteur, par la cascade déjà construite -----------------------------


async def test_the_inviter_becomes_the_referent():
    """Aucune ligne n'a été ajoutée au résolveur : c'est le cas pour lequel `INVITER` existe."""
    tenant, inviter = uuid4(), uuid4()
    overrides = _Overrides()

    crossed = await _threshold(overrides=overrides).execute(
        link=_link(tenant=tenant, inviter=inviter), name="Awa", phone=None, now=_NOW,
    )

    (override,) = overrides.rows
    assert override.person_id == crossed.account_id
    assert override.referent_person_id == inviter
    assert override.origin is ReferentOrigin.INVITER


async def test_a_group_capsule_hands_the_link_to_the_group_leader():
    tenant, group, leader = uuid4(), uuid4(), uuid4()
    overrides = _Overrides()

    await _threshold(overrides=overrides, groups=_Groups({group: leader})).execute(
        link=_link(tenant=tenant, group=group), name="Awa", phone=None, now=_NOW,
    )

    assert overrides.rows[0].referent_person_id == leader


async def test_a_capsule_without_a_reachable_inviter_leaves_a_dated_gap():
    """La personne entre quand même — mais sans référent, et **c'est une donnée**.

    On ne fabrique pas un lien qui n'existe pas : c'est ce trou que la couverture doit voir."""
    tenant, group = uuid4(), uuid4()
    overrides = _Overrides()

    await _threshold(overrides=overrides, groups=_Groups({})).execute(
        link=_link(tenant=tenant, group=group), name="Awa", phone=None, now=_NOW,
    )

    assert overrides.rows == []


# --- Le fait : c'est elle qui a tendu la main en retour ------------------------------------


async def test_accepting_opens_a_declared_case_with_its_consent():
    """Le consentement n'est pas une case cochée : c'est le geste de laisser un contact."""
    tenant = uuid4()
    intake, signals, ledger = _engine()

    crossed = await _threshold(intake=intake).execute(
        link=_link(tenant=tenant, inviter=uuid4()), name="Awa", phone=None, now=_NOW,
    )

    (fact,) = ledger.rows
    assert fact.kind is FactKind.SELF_DECLARATION
    assert fact.source == MISSION
    assert fact.payload["kind"] == DeclarationKind.CAPSULE_ACCEPTED.value
    assert fact.consent is not None
    assert fact.consent.scope is ConsentScope.BE_WATCHED

    (case,) = signals.rows
    assert case.subject_id == crossed.account_id
    # Exempt du plafond, toujours : on ne fait pas attendre quelqu'un qui a levé la main.
    assert case.origin is CasePriority.DECLARED
    assert "invitation" in case.reason


async def test_a_reaction_never_reaches_the_ledger():
    """Une réaction anonyme est une graine. On n'a pas à la ficher.

    La mission n'est enregistrée que pour `SELF_DECLARATION` — le registre le refuse."""
    registry = default_registry()

    assert registry.accepts(MISSION, FactKind.SELF_DECLARATION) is True
    assert registry.accepts(MISSION, FactKind.GRATITUDE_DEPOSITED) is False
    assert registry.accepts(MISSION, FactKind.PRESENCE_RECORDED) is False


async def test_choosing_a_rhythm_opens_no_case():
    """Choisir sa cadence pose une échéance, pas un cas — elle attend le worker."""
    from app.contexts.watch.application.interpretation import WatchStateView
    from app.contexts.watch.domain.facts import Fact, SubjectKind

    fact = Fact(
        fact_id=uuid4(), tenant_id=uuid4(), occurred_at=_NOW, recorded_at=_NOW,
        source=MISSION, kind=FactKind.SELF_DECLARATION,
        subject_kind=SubjectKind.PERSON, subject_id=uuid4(),
        payload={"kind": DeclarationKind.RHYTHM.value, "cadence": "monthly"},
    )

    assert SelfDeclarationV1().interpret(fact, WatchStateView()) == []
