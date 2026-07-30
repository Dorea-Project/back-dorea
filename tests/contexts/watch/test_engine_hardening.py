"""Ce qui rend le moteur sûr plutôt que juste — lot 2, partie corrections.

Trois défauts, et aucun ne se voyait :

1. **la reprojection perdait toutes les échéances.** Elle construisait sa matérialisation sans
   store d'échéances ; chaque `ScheduleCheck` retombait donc en « différé », et « différé » était
   jeté par tous les appelants. Une église rejouée n'avait plus une seule relance programmée, et on
   l'aurait découvert des semaines plus tard, sur les gens dont on n'a plus de nouvelles ;
2. **un effet proposé que rien n'écrit ne disait rien.** Le silence est précisément ce que ce
   module existe pour empêcher : il ne peut pas être son propre mode de défaillance ;
3. **le défunt pouvait être l'auteur déclaré de sa propre exclusion**, par le repli « à défaut, le
   sujet » de la matérialisation.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.intake import Intake, warn_if_disconnected
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.life_event_announced import (
    LifeEventAnnouncedV1,
)
from app.contexts.watch.application.interpreters.self_declaration import SelfDeclarationV1
from app.contexts.watch.application.materialization import DEFERRED_COUNTS
from app.contexts.watch.application.projections import RebuildProjections
from app.contexts.watch.domain.effects import EffectKind
from app.contexts.watch.domain.errors import (
    ActorRequiredError,
    InvalidPayloadError,
    ReplayWouldEraseHumanActsError,
)
from app.contexts.watch.domain.facts import (
    ACTOR_KEY,
    ACTOR_REQUIRED,
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.registry import (
    ANNOUNCEMENTS,
    MISSION,
    RegisteredSource,
    SourceRegistry,
    default_registry,
)
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeChecks,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


def _interpreters() -> InterpreterRegistry:
    registry = InterpreterRegistry()
    registry.register(SelfDeclarationV1())
    registry.register(LifeEventAnnouncedV1())
    return registry


def _rhythm_fact(*, tenant, member, every_days=7):
    """« Prenez de mes nouvelles tous les sept jours » — la parole qui pose une échéance."""
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=MISSION, kind=FactKind.SELF_DECLARATION,
        subject_kind=SubjectKind.PERSON, subject_id=member,
        payload={"kind": "rhythm", "every_days": every_days},
        consent=None,
    )


def _contact_request_fact(*, tenant, member):
    """« Appelez-moi » — la parole qui ouvre un cas, celle sur laquelle un humain agira."""
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
        source=MISSION, kind=FactKind.SELF_DECLARATION,
        subject_kind=SubjectKind.PERSON, subject_id=member,
        payload={"kind": "contact_request"},
    )


def _consented(fact):
    """Une auto-déclaration n'entre pas sans preuve de consentement — c'est un type, pas un flag."""
    return replace(
        fact,
        consent=ConsentProof(
            given_by=fact.subject_id, scope=ConsentScope.BE_WATCHED, given_at=_NOW
        ),
    )


def _engine(*, checks=None, ledger=None):
    ledger = ledger if ledger is not None else FakeLedger()
    signals, absences, exclusions = FakeSignals(), FakeAbsences(), FakeExclusions()
    store = AttendanceNeutralizationStore(absences, exclusions)
    interpreters = _interpreters()
    intake = Intake(
        ledger, default_registry(), interpreters, store, signals, checks
    )
    return intake, ledger, store, signals, interpreters


# --- 1. La reprojection ne perd plus les échéances ---------------------------------------


async def test_a_reprojection_reposes_the_deadlines_instead_of_losing_them():
    """Le rejeu doit reconstruire les échéances, pas les effacer.

    C'est la garantie qui permettra à la détection d'absence d'exister : elle reposera entièrement
    sur des échéances, et une reprojection est justement ce qu'on lance quand quelque chose est
    déjà cassé. Une reprojection qui décapite la veille est plus dangereuse que le défaut qu'elle
    répare."""
    tenant, member = uuid4(), uuid4()
    checks = FakeChecks()
    intake, ledger, store, signals, interpreters = _engine(checks=checks)

    await intake.submit(_consented(_rhythm_fact(tenant=tenant, member=member)))
    assert len(checks.rows) == 1  # l'échéance est posée

    await RebuildProjections(
        ledger, interpreters, store, signals, None, checks
    ).execute(tenant_id=tenant)

    assert len(checks.rows) == 1  # et toujours là après le rejeu
    assert checks.rows[0]["due_at"] == _NOW + timedelta(days=7)
    assert checks.rows[0]["cancelled_at"] is None


async def test_a_reprojection_without_its_check_store_is_loud_about_it(caplog):
    """Le piège exact d'avant : la même reprojection, assemblée sans store d'échéances.

    Elle perd toujours l'échéance — c'est la conséquence d'un mauvais assemblage, pas une règle
    qu'on peut cacher — mais elle ne peut plus le faire sans le dire."""
    tenant, member = uuid4(), uuid4()
    checks = FakeChecks()
    intake, ledger, store, signals, interpreters = _engine(checks=checks)
    await intake.submit(_consented(_rhythm_fact(tenant=tenant, member=member)))

    with caplog.at_level("WARNING"):
        report = await RebuildProjections(
            ledger, interpreters, store, signals, None, None
        ).execute(tenant_id=tenant)

    assert report.deferred == 1
    assert any("non matérialisé" in r.message for r in caplog.records)


async def test_a_reprojection_never_refires_a_deadline_that_already_fell():
    """Ce qui a tiré est de l'**histoire** : la pose est une projection, le tir est un acte.

    Sans cette distinction, chaque reprojection reposerait les échéances déjà tombées — elles
    retomberaient, et la personne serait relancée une seconde fois pour un silence qu'on a déjà
    constaté."""
    tenant, member = uuid4(), uuid4()
    checks = FakeChecks()
    intake, ledger, store, signals, interpreters = _engine(checks=checks)

    await intake.submit(_consented(_rhythm_fact(tenant=tenant, member=member)))
    await checks.mark_fired(check_id=checks.rows[0]["id"], at=_NOW + timedelta(days=7))

    await RebuildProjections(
        ledger, interpreters, store, signals, None, checks
    ).execute(tenant_id=tenant)

    assert len(checks.rows) == 1
    assert checks.rows[0]["fired_at"] is not None  # l'histoire est intacte
    assert await checks.pending_count(tenant_id=tenant, now=_NOW + timedelta(days=30)) == 0


# --- 1bis. Un rejeu n'efface pas ce que des humains ont fait -----------------------------


async def test_a_replay_refuses_to_erase_what_a_responsable_has_done():
    """Le journal porte des faits ; « j'ai appelé » est un **acte**, et il n'y est pas.

    Rejouer effacerait les issues des responsables, le premier regard, le premier contact, les
    gestes comptés, la chaîne d'épisode et les consolations déjà remises. Détruire la trace du soin
    au nom de la réparation est le pire échange possible."""
    tenant, member = uuid4(), uuid4()
    checks = FakeChecks()
    intake, ledger, store, signals, interpreters = _engine(checks=checks)
    await intake.submit(_consented(_contact_request_fact(tenant=tenant, member=member)))

    case = signals.rows[0]
    case.record_contact_attempt(at=_NOW + timedelta(days=1))  # quelqu'un a appelé

    with pytest.raises(ReplayWouldEraseHumanActsError) as refusal:
        await RebuildProjections(
            ledger, interpreters, store, signals, None, checks
        ).execute(tenant_id=tenant)

    assert refusal.value.details["contacted"] == 1
    assert signals.rows  # et rien n'a été effacé : le refus précède la purge


async def test_a_replay_proceeds_when_nobody_has_acted_yet():
    """Une église où personne n'a encore rien fait se rejoue librement — c'est le cas courant."""
    tenant, member = uuid4(), uuid4()
    checks = FakeChecks()
    intake, ledger, store, signals, interpreters = _engine(checks=checks)
    await intake.submit(_consented(_rhythm_fact(tenant=tenant, member=member)))

    report = await RebuildProjections(
        ledger, interpreters, store, signals, None, checks
    ).execute(tenant_id=tenant)

    assert report.facts == 1


async def test_forcing_a_replay_is_a_signature_not_a_convenience():
    """On peut forcer — en sachant ce qu'on perd. Le drapeau existe pour que ce soit un choix."""
    tenant, member = uuid4(), uuid4()
    checks = FakeChecks()
    intake, ledger, store, signals, interpreters = _engine(checks=checks)
    await intake.submit(_consented(_contact_request_fact(tenant=tenant, member=member)))
    signals.rows[0].record_contact_attempt(at=_NOW + timedelta(days=1))

    report = await RebuildProjections(
        ledger, interpreters, store, signals, None, checks
    ).execute(tenant_id=tenant, force=True)

    assert report.facts == 1
    assert signals.rows[0].first_contact_at is None  # l'acte est bien perdu : c'était le marché


async def test_the_replay_follows_the_written_order_not_the_dates():
    """Le rejeu suit `seq`, l'ordre **total** — pas `occurred_at`, qui peut remonter le temps.

    Le flux vient trié de la base et n'est plus retrié en mémoire : trier suppose d'avoir tout
    chargé, ce que le flux existe précisément pour éviter. Il faut donc que l'ordre du flux soit
    le bon, et une saisie tardive est le cas qui le prouve."""
    tenant, member = uuid4(), uuid4()
    checks = FakeChecks()
    intake, ledger, *_ = _engine(checks=checks)

    # Le second fait est enregistré après, mais daté d'avant : les dates mentent, `seq` non.
    await intake.submit(_consented(_rhythm_fact(tenant=tenant, member=member, every_days=7)))
    late = replace(
        _consented(_rhythm_fact(tenant=tenant, member=member, every_days=3)),
        occurred_at=_NOW - timedelta(days=10),
    )
    await intake.submit(late)

    seen = [f.seq async for f in ledger.stream(tenant)]

    assert seen == sorted(seen)
    assert [f.occurred_at for f in ledger.rows] != sorted(f.occurred_at for f in ledger.rows)


# --- 2. Un effet que rien n'écrit ne peut pas être silencieux ----------------------------


async def test_a_deferred_effect_is_never_silent(caplog):
    """Le moteur ne peut pas avoir le silence pour mode de défaillance.

    L'engine renvoyait déjà la liste des différés — et tous ses appelants la jetaient. C'est ainsi
    que la reprojection a perdu les échéances tout ce temps, sans une ligne de journal."""
    tenant, member = uuid4(), uuid4()
    before = DEFERRED_COUNTS.get(EffectKind.SCHEDULE_CHECK, 0)
    intake, *_ = _engine(checks=None)  # le store d'échéances n'est pas branché

    with caplog.at_level("WARNING"):
        result = await intake.submit(_consented(_rhythm_fact(tenant=tenant, member=member)))

    assert result.materialization.deferred == (EffectKind.SCHEDULE_CHECK,)
    assert DEFERRED_COUNTS[EffectKind.SCHEDULE_CHECK] == before + 1
    assert any("non matérialisé" in r.message for r in caplog.records)


def test_a_source_built_without_an_intake_says_so(caplog):
    """Le plus silencieux des défauts d'assemblage : une source entière qui se tait sans erreur."""
    with caplog.at_level("WARNING"):
        warn_if_disconnected("appointments", None)

    assert any("n'émettra aucun fait" in r.message for r in caplog.records)


# --- 3. L'acteur d'un retrait de la veille -----------------------------------------------


def test_every_source_that_can_remove_someone_names_the_actor():
    """Invariant balayant : aucun kind capable d'exclure n'entre sans son acteur.

    Le contrôle est à l'enregistrement, donc au **démarrage** — pas à la revue de code, et pas un
    jour chez un client."""
    registry = default_registry()
    for source in registry.sources:
        for kind in source.kinds:
            if kind in ACTOR_REQUIRED:
                assert ACTOR_KEY in source.required_payload_keys, (
                    f"{source.id} peut retirer quelqu'un de la veille sans dire qui l'a fait"
                )


def test_registering_a_removing_source_without_an_actor_fails_at_startup():
    with pytest.raises(ActorRequiredError):
        SourceRegistry().register(
            RegisteredSource(
                id="un_greffon_futur",
                kinds=frozenset({FactKind.LIFE_EVENT_ANNOUNCED}),
                required_payload_keys=frozenset({"announcement_id", "role"}),
            )
        )


async def test_a_death_announcement_without_an_actor_is_refused_at_the_door():
    """Refusé à l'intake, pas corrigé en aval : le défunt ne déclare pas son propre retrait."""
    tenant, member = uuid4(), uuid4()
    intake, *_ = _engine()

    with pytest.raises(InvalidPayloadError):
        await intake.submit(
            Fact(
                fact_id=uuid4(), tenant_id=tenant, occurred_at=_NOW, recorded_at=_NOW,
                source=ANNOUNCEMENTS, kind=FactKind.LIFE_EVENT_ANNOUNCED,
                subject_kind=SubjectKind.PERSON, subject_id=member,
                payload={"announcement_id": str(uuid4()), "role": "deceased"},
            )
        )
