"""La pipeline de bout en bout : un fait entre, un effet sort — et le rejeu redonne le même état.

Ce fichier remplace les tests d'effets écrits avant le moteur : les règles n'ont pas changé, le
chemin si. Les Annonces n'écrivent plus rien ; elles émettent, et l'engine décide.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.announcements.application.watch_effects import (
    EmitAnnouncementFacts,
    build_fact,
    fact_id_for,
)
from app.contexts.announcements.domain.aggregates import (
    Announcement,
    SubjectDraft,
    attach_subjects,
)
from app.contexts.announcements.domain.enums import AnnouncementCategory
from app.contexts.attendance.application.return_detection import DetectReturn
from app.contexts.attendance.domain.enums import AbsenceOutcome, AbsenceReason, AbsenceSource
from app.contexts.attendance.domain.planned_absence import PlannedAbsence
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.life_event_announced import (
    LifeEventAnnouncedV1,
)
from app.contexts.watch.application.interpreters.presence_recorded import PresenceRecordedV1
from app.contexts.watch.application.projections import RebuildProjections
from app.contexts.watch.domain.effects import EffectKind
from app.contexts.watch.domain.errors import FactKindNotAllowedError, InvalidPayloadError
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import ANNOUNCEMENTS, ATTENDANCE, default_registry
from app.contexts.watch.domain.role_rules import SubjectRole
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
Cat, Role = AnnouncementCategory, SubjectRole


def _interpreters() -> InterpreterRegistry:
    registry = InterpreterRegistry()
    registry.register(LifeEventAnnouncedV1())
    registry.register(PresenceRecordedV1())
    return registry


def _engine(*, absences=None, exclusions=None, ledger=None, signals=None, policy=None):
    absences = absences if absences is not None else FakeAbsences()
    exclusions = exclusions if exclusions is not None else FakeExclusions()
    ledger = ledger if ledger is not None else FakeLedger()
    signals = signals if signals is not None else FakeSignals()
    store = AttendanceNeutralizationStore(absences, exclusions)
    interpreters = _interpreters()
    intake = Intake(ledger, default_registry(), interpreters, store, signals, policy=policy)
    rebuild = RebuildProjections(ledger, interpreters, store, signals, policy=policy)
    return intake, rebuild, absences, exclusions, ledger


def _announcement(category, *, tenant, author, occurred_at=None, now=_NOW) -> Announcement:
    return Announcement.publish(
        id=uuid4(), tenant_id=tenant, category=category, scope_group_id=None,
        title="T", body=None, author_account_id=author, now=now, occurred_at=occurred_at,
    )


async def _announce(intake, announcement, drafts, *, now=_NOW):
    subjects = attach_subjects(announcement, drafts, now=now)
    emitter = EmitAnnouncementFacts(intake, clock=lambda: now)
    await emitter.execute(announcement=announcement, subjects=subjects)
    return subjects


def _presence_fact(*, tenant, person, gathering, occurred_at, recorded_at=_NOW) -> Fact:
    return Fact(
        fact_id=uuid4(), tenant_id=tenant, occurred_at=occurred_at, recorded_at=recorded_at,
        source=ATTENDANCE, kind=FactKind.PRESENCE_RECORDED,
        subject_kind=SubjectKind.PERSON, subject_id=person,
        payload={"gathering_id": str(gathering)},
    )


# --- La source propose, l'engine décide --------------------------------------------------------


async def test_a_travel_announcement_neutralizes_through_the_ledger():
    tenant, traveler, author = uuid4(), uuid4(), uuid4()
    intake, _, absences, _, ledger = _engine()
    travel = _announcement(Cat.TRAVEL, tenant=tenant, author=author)

    await _announce(
        intake, travel,
        [SubjectDraft(account_id=traveler, role=Role.TRAVELER, declared_duration_days=30)],
    )

    # Le fait est au journal, scellé à sa place.
    (fact,) = ledger.rows
    assert fact.kind is FactKind.LIFE_EVENT_ANNOUNCED
    assert fact.seq == 1

    # Et l'effet est écrit là où le roster et M7 le lisent déjà.
    (absence,) = absences.rows
    assert absence.source is AbsenceSource.ANNOUNCEMENT
    assert absence.reason is AbsenceReason.TRAVEL
    assert absence.to_date == _NOW + timedelta(days=30)
    assert absence.covers(_NOW + timedelta(days=10)) is True


async def test_the_announcement_context_writes_nothing_itself():
    """Sans intake branché, publier ne touche à rien : la source ne sait plus écrire."""
    tenant, traveler, author = uuid4(), uuid4(), uuid4()
    absences = FakeAbsences()
    travel = _announcement(Cat.TRAVEL, tenant=tenant, author=author)
    subjects = attach_subjects(
        travel,
        [SubjectDraft(account_id=traveler, role=Role.TRAVELER, declared_duration_days=30)],
        now=_NOW,
    )

    await EmitAnnouncementFacts(None, clock=lambda: _NOW).execute(
        announcement=travel, subjects=subjects
    )

    assert absences.rows == []


async def test_a_death_excludes_and_closes_what_was_running():
    tenant, person, author = uuid4(), uuid4(), uuid4()
    intake, _, absences, exclusions, _ = _engine()

    sickness = _announcement(Cat.SICKNESS, tenant=tenant, author=author)
    subjects = attach_subjects(
        sickness, [SubjectDraft(account_id=person, role=Role.SICK)], now=_NOW
    )
    subjects[0].grant(now=_NOW)  # le malade a accepté d'être nommé
    await EmitAnnouncementFacts(intake, clock=lambda: _NOW).execute(
        announcement=sickness, subjects=subjects
    )
    assert absences.rows[0].is_open is True

    death = _announcement(Cat.DEATH, tenant=tenant, author=author)
    await _announce(intake, death, [SubjectDraft(account_id=person, role=Role.DECEASED)])

    assert absences.rows[0].outcome is AbsenceOutcome.DECEASED
    assert await exclusions.excluded_account_ids(tenant) == {person}


async def test_nothing_enters_on_someone_removed_from_the_watch():
    """L'absorbant se tient à la porte : aucune source, jamais."""
    tenant, person, author = uuid4(), uuid4(), uuid4()
    intake, _, absences, _, ledger = _engine()

    death = _announcement(Cat.DEATH, tenant=tenant, author=author)
    await _announce(intake, death, [SubjectDraft(account_id=person, role=Role.DECEASED)])

    late = _announcement(Cat.TRAVEL, tenant=tenant, author=author)
    await _announce(
        intake, late,
        [SubjectDraft(account_id=person, role=Role.TRAVELER, declared_duration_days=15)],
    )

    assert absences.rows == []
    assert len(ledger.rows) == 1  # le second fait n'est même pas entré au journal


async def test_two_neutralizations_extend_they_never_add_up():
    tenant, person, author = uuid4(), uuid4(), uuid4()
    intake, _, absences, _, _ = _engine()

    first = _announcement(Cat.TRAVEL, tenant=tenant, author=author)
    await _announce(
        intake, first,
        [SubjectDraft(account_id=person, role=Role.TRAVELER, declared_duration_days=10)],
    )
    second = _announcement(Cat.SICKNESS, tenant=tenant, author=author)
    subjects = attach_subjects(
        second, [SubjectDraft(account_id=person, role=Role.SICK)], now=_NOW
    )
    subjects[0].grant(now=_NOW)
    await EmitAnnouncementFacts(intake, clock=lambda: _NOW).execute(
        announcement=second, subjects=subjects
    )

    assert len(absences.rows) == 1  # une seule période, pas deux qui s'empilent
    assert absences.rows[0].to_date == _NOW + timedelta(days=30)  # la plus lointaine


async def test_the_bereaved_finally_gets_a_case():
    """Le manque le plus long du produit : la famille endeuillée ne recevait rien."""
    tenant, widow, author = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _, absences, _, ledger = _engine(signals=signals)
    death = _announcement(Cat.DEATH, tenant=tenant, author=author)

    subjects = attach_subjects(
        death, [SubjectDraft(account_id=widow, role=Role.BEREAVED)], now=_NOW
    )
    result = await intake.submit(build_fact(death, subjects[0], recorded_at=_NOW))

    assert result.materialization.written == (EffectKind.OPEN_CASE,)
    # Le deuil n'excuse pas l'absence : aucun effet sur le roster, mais un cas ouvert sur elle.
    assert absences.rows == []
    assert len(ledger.rows) == 1


# --- Le consentement : rien n'entre avant l'accord ---------------------------------------------


async def test_a_sick_subject_emits_nothing_before_consenting():
    tenant, sick, author = uuid4(), uuid4(), uuid4()
    intake, _, absences, _, ledger = _engine()
    sickness = _announcement(Cat.SICKNESS, tenant=tenant, author=author)

    await _announce(intake, sickness, [SubjectDraft(account_id=sick, role=Role.SICK)])

    assert ledger.rows == []  # pas même un fait : il n'y a rien à filtrer en aval
    assert absences.rows == []


async def test_granting_consent_dates_the_effect_from_the_event():
    """Accepter le 1ᵉʳ mai une maladie survenue le 12 avril neutralise depuis le 12 avril."""
    tenant, sick, author = uuid4(), uuid4(), uuid4()
    fell_ill = datetime(2026, 4, 12, tzinfo=UTC)
    intake, _, absences, _, _ = _engine()

    sickness = _announcement(Cat.SICKNESS, tenant=tenant, author=author, occurred_at=fell_ill)
    subjects = attach_subjects(
        sickness, [SubjectDraft(account_id=sick, role=Role.SICK)], now=_NOW
    )
    subjects[0].grant(now=_NOW)
    await EmitAnnouncementFacts(intake, clock=lambda: _NOW).execute(
        announcement=sickness, subjects=subjects
    )

    (absence,) = absences.rows
    assert absence.from_date == fell_ill
    assert absence.to_date == fell_ill + timedelta(days=30)


# --- Le retour ---------------------------------------------------------------------------------


async def test_a_presence_fact_closes_the_neutralization():
    tenant, traveler, author, gathering = uuid4(), uuid4(), uuid4(), uuid4()
    intake, _, absences, _, _ = _engine()
    travel = _announcement(Cat.TRAVEL, tenant=tenant, author=author)
    await _announce(
        intake, travel,
        [SubjectDraft(account_id=traveler, role=Role.TRAVELER, declared_duration_days=60)],
    )

    came_back = _NOW + timedelta(days=12)
    await DetectReturn(intake).on_positive_presence(
        account_id=traveler, tenant_id=tenant, occurred_at=came_back,
        gathering_id=gathering, recorded_at=came_back + timedelta(days=3),
    )

    absence = absences.rows[0]
    assert absence.outcome is AbsenceOutcome.RETURNED
    assert absence.returned_at == came_back  # daté de la rencontre, pas de la saisie
    # La fenêtre se raccourcit : les rencontres manquées avant le retour restent excusées.
    assert absence.covers(_NOW + timedelta(days=5)) is True
    assert absence.covers(_NOW + timedelta(days=20)) is False


async def test_an_announcement_is_not_a_source_of_presence():
    """Réagir au fil n'est pas revenir. L'asymétrie est dans le registre, pas dans une règle."""
    intake, _, _, _, _ = _engine()

    with pytest.raises(FactKindNotAllowedError):
        await intake.submit(
            Fact(
                fact_id=uuid4(), tenant_id=uuid4(), occurred_at=_NOW, recorded_at=_NOW,
                source=ANNOUNCEMENTS, kind=FactKind.PRESENCE_RECORDED,
                subject_kind=SubjectKind.PERSON, subject_id=uuid4(),
            )
        )


async def test_a_life_event_without_its_required_payload_is_refused():
    intake, _, _, _, _ = _engine()

    with pytest.raises(InvalidPayloadError):
        await intake.submit(
            Fact(
                fact_id=uuid4(), tenant_id=uuid4(), occurred_at=_NOW, recorded_at=_NOW,
                source=ANNOUNCEMENTS, kind=FactKind.LIFE_EVENT_ANNOUNCED,
                subject_kind=SubjectKind.PERSON, subject_id=uuid4(),
                payload={"announcement_id": str(uuid4())},  # le rôle manque
            )
        )


# --- Idempotence et déterminisme ---------------------------------------------------------------


async def test_the_same_announcement_never_enters_twice():
    """`fact_id` est dérivé de (annonce, personne) : rejouer une publication ne duplique rien."""
    tenant, traveler, author = uuid4(), uuid4(), uuid4()
    intake, _, absences, _, ledger = _engine()
    travel = _announcement(Cat.TRAVEL, tenant=tenant, author=author)
    drafts = [SubjectDraft(account_id=traveler, role=Role.TRAVELER, declared_duration_days=30)]

    await _announce(intake, travel, drafts)
    await _announce(intake, travel, drafts)
    await _announce(intake, travel, drafts)

    assert len(ledger.rows) == 1
    assert len(absences.rows) == 1
    assert fact_id_for(travel.id, traveler) == ledger.rows[0].fact_id


async def test_replaying_the_ledger_rebuilds_the_same_state():
    """L'invariant de déterminisme : l'état n'est qu'une projection du journal."""
    tenant, traveler, deceased, author = uuid4(), uuid4(), uuid4(), uuid4()
    intake, rebuild, absences, exclusions, _ = _engine()

    travel = _announcement(Cat.TRAVEL, tenant=tenant, author=author)
    await _announce(
        intake, travel,
        [SubjectDraft(account_id=traveler, role=Role.TRAVELER, declared_duration_days=30)],
    )
    death = _announcement(Cat.DEATH, tenant=tenant, author=author)
    await _announce(intake, death, [SubjectDraft(account_id=deceased, role=Role.DECEASED)])

    before = (
        sorted((a.account_id, a.from_date, a.to_date) for a in absences.rows),
        await exclusions.excluded_account_ids(tenant),
    )

    report = await rebuild.execute(tenant_id=tenant)

    after = (
        sorted((a.account_id, a.from_date, a.to_date) for a in absences.rows),
        await exclusions.excluded_account_ids(tenant),
    )
    assert after == before
    assert report.facts == 2


async def test_coming_back_does_not_close_the_grief():
    """Le cas le plus facile à casser sans s'en apercevoir.

    L'endeuillée vient au culte : son silence n'était pas un silence, mais son deuil n'est pas
    passé pour autant. La neutralisation se ferme, le cas de soin reste ouvert — quelqu'un doit
    encore aller vers elle."""
    tenant, widow, author, gathering = uuid4(), uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    intake, _, _, _, _ = _engine(signals=signals)

    death = _announcement(Cat.DEATH, tenant=tenant, author=author)
    await _announce(intake, death, [SubjectDraft(account_id=widow, role=Role.BEREAVED)])
    assert len(await signals.live_cases(tenant)) == 1

    await DetectReturn(intake).on_positive_presence(
        account_id=widow, tenant_id=tenant, occurred_at=_NOW + timedelta(days=10),
        gathering_id=gathering, recorded_at=_NOW + timedelta(days=10),
    )

    assert len(await signals.live_cases(tenant)) == 1  # toujours ouvert


async def test_replaying_opens_retroactively_what_could_not_be_written_before():
    """La promesse du ledger, vérifiée : un fait garde son sens jusqu'à ce qu'on sache l'écrire.

    On simule l'état d'avant le bloc 2 — le moteur ingère sans savoir matérialiser un cas — puis
    on rejoue avec le store branché. Le cas de l'endeuillée s'ouvre, six mois plus tard s'il
    le faut, sans qu'on ait rien eu à conserver d'autre que le journal."""
    tenant, widow, author = uuid4(), uuid4(), uuid4()
    ledger = FakeLedger()
    absences, exclusions = FakeAbsences(), FakeExclusions()
    store = AttendanceNeutralizationStore(absences, exclusions)

    # Avant : pas de SignalStore. Le fait entre, la proposition est différée.
    aveugle = Intake(ledger, default_registry(), _interpreters(), store, None)
    death = _announcement(Cat.DEATH, tenant=tenant, author=author)
    await _announce(aveugle, death, [SubjectDraft(account_id=widow, role=Role.BEREAVED)])
    assert len(ledger.rows) == 1

    # Après : on rejoue le même journal, cette fois avec de quoi écrire.
    signals = FakeSignals()
    report = await RebuildProjections(
        ledger, _interpreters(), store, signals
    ).execute(tenant_id=tenant)

    assert report.facts == 1
    cases = await signals.live_cases(tenant)
    assert len(cases) == 1 and cases[0][1] == widow


async def test_a_rebuild_never_erases_what_a_member_declared():
    """La parole du membre n'est pas une projection — une reconstruction ne peut pas l'effacer."""
    tenant, member, traveler, author = uuid4(), uuid4(), uuid4(), uuid4()
    absences = FakeAbsences()
    await absences.add(
        PlannedAbsence(
            id=uuid4(), account_id=member, tenant_id=tenant, reason=AbsenceReason.TRAVEL,
            from_date=_NOW, to_date=_NOW + timedelta(days=40),
            declared_by_account_id=member, declared_at=_NOW,
        )
    )
    intake, rebuild, _, _, _ = _engine(absences=absences)
    travel = _announcement(Cat.TRAVEL, tenant=tenant, author=author)
    await _announce(
        intake, travel,
        [SubjectDraft(account_id=traveler, role=Role.TRAVELER, declared_duration_days=30)],
    )

    await rebuild.execute(tenant_id=tenant)

    declared = [a for a in absences.rows if a.source is AbsenceSource.SELF_DECLARED]
    assert len(declared) == 1 and declared[0].account_id == member


# --- Ce que le responsable lit, et dans quelle langue ------------------------------------


@pytest.mark.parametrize(
    ("role", "attendu"),
    [
        (Role.BEREAVED, "Deuil annoncé le 1er mai."),
        (Role.SICK, "Maladie annoncée le 1er mai."),
        (Role.NEW_PARENT, "Naissance annoncée le 1er mai."),
        (Role.NEWLYWED, "Mariage annoncé le 1er mai."),
        (Role.TRAVELER, "Voyage annoncé le 1er mai."),
        (Role.DECEASED, "Décès annoncé le 1er mai."),
    ],
)
def test_the_motive_is_written_in_the_language_of_the_person_who_reads_it(role, attendu):
    """**Le motif d'un cas est la première chose qu'un responsable lit avant d'appeler.**

    Sur un deuil sans cas préexistant, cette phrase *est* le motif — écrite à l'ouverture et
    jamais réécrite. Elle a rendu `bereaved annoncé le 2026-07-30` jusqu'au 02/08/2026 : une
    valeur d'enum anglaise et une date ISO, sur l'écran d'un responsable de cellule à Abidjan.

    Chaque rôle porte son propre accord — un gabarit unique aurait fini par écrire « naissance
    annoncé » à quelqu'un qui vient d'avoir un enfant."""
    from app.contexts.watch.application.interpreters.life_event_announced import _reason

    assert _reason(role, _NOW) == attendu


def test_every_role_has_a_sentence():
    """Ajouter un rôle sans sa phrase ferait retomber le produit dans le code d'état."""
    from app.contexts.watch.application.interpreters.life_event_announced import _ROLE_REASONS

    assert set(_ROLE_REASONS) == set(Role)
