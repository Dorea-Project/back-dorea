"""Les invariants du moteur de veille — la suite qui doit tourner sur **tout** greffon.

Ces tests ne vérifient pas un comportement : ils vérifient que certaines choses restent
**impossibles**. Un développeur futur, bien intentionné, voudra un jour croiser les dons avec la
présence, ou signaler les membres inactifs sur l'application. Ce fichier est ce qui l'arrête.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

import pytest

from app.contexts.watch.application.arbitration import arbitrate
from app.contexts.watch.application.interpretation import (
    InterpreterRegistry,
    NeutralizationView,
    WatchStateView,
)
from app.contexts.watch.application.interpreters.life_event_announced import (
    LifeEventAnnouncedV1,
)
from app.contexts.watch.application.interpreters.presence_recorded import PresenceRecordedV1
from app.contexts.watch.domain.effects import (
    CasePriority,
    ExcludeForever,
    ExclusionCause,
    Extinguish,
    ExtinguishCause,
    Neutralise,
    OpenCase,
)
from app.contexts.watch.domain.errors import (
    ForbiddenFactKindError,
    SourceNotRegisteredError,
)
from app.contexts.watch.domain.facts import (
    CONSENT_REQUIRED,
    Fact,
    FactKind,
    SubjectKind,
    forbidden_reason,
)
from app.contexts.watch.domain.registry import (
    ANNOUNCEMENTS,
    RegisteredSource,
    SourceRegistry,
    default_registry,
)
from app.contexts.watch.domain.role_rules import SubjectRole

_NOW = datetime(2026, 5, 1, tzinfo=UTC)


def _fact(kind, subject, *, payload=None, occurred_at=_NOW, recorded_at=_NOW, source=ANNOUNCEMENTS):
    return Fact(
        fact_id=uuid4(),
        tenant_id=uuid4(),
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        source=source,
        kind=kind,
        subject_kind=SubjectKind.PERSON,
        subject_id=subject,
        payload=payload or {},
    )


# --- Invariant 1 : aucun fait d'inaction ------------------------------------------------------


def test_no_fact_kind_describes_an_inaction():
    """L'asymétrie parole / silence n'est pas une règle : c'est l'absence du type.

    Le silence de quelqu'un ne peut pas entrer dans le moteur, parce qu'aucune source ne dispose
    d'une forme pour le dire."""
    for kind in FactKind:
        assert forbidden_reason(kind.value) is None, kind

    for tentation in ("did_not_react", "member_inactive_on_app", "unread_message", "never_opened"):
        assert forbidden_reason(tentation) == "inaction"


def test_registering_an_inaction_kind_fails_at_startup():
    """La tentation échoue à l'enregistrement — pas à la revue de code, pas en production.

    On simule ici le kind qu'un développeur futur voudra ajouter à l'enum : le registre le
    refuse avant même que l'application ne démarre."""

    class _TentationFuture(StrEnum):
        MEMBER_INACTIVE_ON_APP = "member_inactive_on_app"

    with pytest.raises(ForbiddenFactKindError):
        SourceRegistry().register(
            RegisteredSource(
                id="analytics",
                kinds=frozenset({_TentationFuture.MEMBER_INACTIVE_ON_APP}),  # type: ignore[arg-type]
            )
        )


# --- Invariants 2 et 3 : ni argent, ni inférence ----------------------------------------------


def test_no_fact_kind_can_carry_usage_telemetry():
    """Le complément indispensable de « inaction » : interdire de la **dériver d'une fréquence**.

    Sans cette famille, `COMPANION_OPENED` passerait — et « il l'ouvre moins souvent »
    redeviendrait un signal, déguisé en donnée positive. Ouvrir une application n'est pas un
    acte de vie ; ne pas l'ouvrir n'est pas un silence."""
    for kind in FactKind:
        assert forbidden_reason(kind.value) != "télémétrie", kind

    for tentation in (
        "companion_opened",
        "app_session_start",
        "member_last_seen",
        "screen_view_recorded",
        "activity_ping",
    ):
        assert forbidden_reason(tentation) == "télémétrie", tentation


def test_no_fact_kind_can_carry_money():
    for kind in FactKind:
        assert forbidden_reason(kind.value) != "financier", kind
    assert forbidden_reason("donation_received") == "financier"
    assert forbidden_reason("tithe_recorded") == "financier"


def test_no_fact_kind_can_carry_an_ai_inference_about_a_person():
    for kind in FactKind:
        assert forbidden_reason(kind.value) != "inféré", kind
    assert forbidden_reason("sentiment_analyzed") == "inféré"
    assert forbidden_reason("risk_score_predicted") == "inféré"


def test_the_group_companion_speaks_of_a_group_never_of_a_person():
    """Le compagnon collectif existe **parce que** son sujet est un groupe.

    Il n'y a pas de donnée individuelle à protéger : il n'y en a jamais eu."""
    fact = Fact(
        fact_id=uuid4(), tenant_id=uuid4(), occurred_at=_NOW, recorded_at=_NOW,
        source="companion", kind=FactKind.GROUP_TEMPERATURE,
        subject_kind=SubjectKind.GROUP, subject_id=uuid4(),
    )
    assert fact.is_about_person is False


# --- Invariant 14 : source non enregistrée ----------------------------------------------------


def test_a_fact_from_an_unregistered_source_is_rejected():
    """Ajouter n'est pas modifier : une source inconnue n'a pas voix au chapitre."""
    with pytest.raises(SourceNotRegisteredError):
        default_registry().get("un_greffon_qui_ne_s_est_pas_declare")


def test_a_registered_source_only_says_what_it_declared():
    registry = default_registry()
    assert registry.accepts(ANNOUNCEMENTS, FactKind.LIFE_EVENT_ANNOUNCED) is True
    # Les annonces ne sont pas une source de présence : c'est ce qui interdit qu'une réaction
    # au fil vaille un retour.
    assert registry.accepts(ANNOUNCEMENTS, FactKind.PRESENCE_RECORDED) is False


def test_the_consent_bearing_kinds_are_the_intimate_ones():
    assert FactKind.THIRD_PARTY_CONCERN in CONSENT_REQUIRED
    assert FactKind.SELF_DECLARATION in CONSENT_REQUIRED
    # L'annonce n'y est pas : son accord est une garde **en amont**, dans le contexte Annonces.
    # Un rôle intime sans accord n'émet simplement jamais de fait.
    assert FactKind.LIFE_EVENT_ANNOUNCED not in CONSENT_REQUIRED


# --- Invariant 4 : l'exclusion est absorbante --------------------------------------------------


def test_no_effect_survives_arbitration_on_an_excluded_person():
    """Testé à l'arbitrage, un seul endroit — donc valable pour tout greffon, présent et futur."""
    person = uuid4()
    state = WatchStateView(excluded_subject_ids=frozenset({person}))
    effects = [
        Neutralise(
            subject_id=person, reason="voyage", starts_at=_NOW,
            expected_return_at=_NOW + timedelta(days=30),
        ),
        OpenCase(
            subject_id=person, reason="deuil",
            origin=CasePriority.ANNOUNCEMENT, opened_at=_NOW,
        ),
    ]

    decided = arbitrate(effects, state)

    assert decided.admitted == ()
    assert [why for _, why in decided.dropped] == ["subject_excluded", "subject_excluded"]


def test_the_exclusion_itself_is_never_dropped():
    """Sinon on ne pourrait jamais exclure deux fois, ni reconstruire l'état par rejeu."""
    person = uuid4()
    state = WatchStateView(excluded_subject_ids=frozenset({person}))
    exclusion = ExcludeForever(
        subject_id=person, reason="décès", cause=ExclusionCause.DECEASED, at=_NOW
    )

    decided = arbitrate([exclusion], state)

    assert decided.admitted == (exclusion,)


# --- Les interpreters sont purs ----------------------------------------------------------------


def test_an_interpreter_proposes_and_never_writes():
    """Un interpreter n'a aucune dépendance : ni dépôt, ni horloge. C'est ce qui le rend rejouable.

    Le décès **absorbe** — il éteint ce qui courait et retire, rien d'autre n'est évalué."""
    person = uuid4()
    fact = _fact(
        FactKind.LIFE_EVENT_ANNOUNCED,
        person,
        payload={"announcement_id": str(uuid4()), "role": SubjectRole.DECEASED.value},
    )

    proposed = LifeEventAnnouncedV1().interpret(fact, WatchStateView())

    kinds = [type(e).__name__ for e in proposed]
    assert kinds == ["Extinguish", "ExcludeForever"]
    assert not any(isinstance(e, Neutralise) for e in proposed)


def test_the_bereaved_case_is_proposed_even_though_nothing_can_write_it_yet():
    """Le ledger fait qu'on ne perd rien : la proposition existe, elle attend le `Signal`.

    Le jour où l'objet arrivera, une reprojection ouvrira ces cas rétroactivement."""
    fact = _fact(
        FactKind.LIFE_EVENT_ANNOUNCED,
        uuid4(),
        payload={"announcement_id": str(uuid4()), "role": SubjectRole.BEREAVED.value},
    )

    proposed = LifeEventAnnouncedV1().interpret(fact, WatchStateView())

    assert [type(e).__name__ for e in proposed] == ["OpenCase"]
    # Le deuil n'excuse pas l'absence : aucune neutralisation n'est proposée.
    assert not any(isinstance(e, Neutralise) for e in proposed)


def test_a_presence_older_than_the_neutralization_is_not_a_return():
    person = uuid4()
    state = WatchStateView(
        open_neutralizations=(
            NeutralizationView(
                id=uuid4(), subject_id=person,
                starts_at=_NOW, expected_return_at=_NOW + timedelta(days=30),
            ),
        )
    )
    before = _fact(
        FactKind.PRESENCE_RECORDED, person, occurred_at=_NOW - timedelta(days=2),
        source="attendance",
    )

    assert PresenceRecordedV1().interpret(before, state) == []


def test_a_presence_after_the_start_closes_and_remembers():
    person = uuid4()
    state = WatchStateView(
        open_neutralizations=(
            NeutralizationView(
                id=uuid4(), subject_id=person,
                starts_at=_NOW, expected_return_at=_NOW + timedelta(days=30),
            ),
        )
    )
    back = _fact(
        FactKind.PRESENCE_RECORDED, person, occurred_at=_NOW + timedelta(days=12),
        source="attendance",
    )

    proposed = PresenceRecordedV1().interpret(back, state)

    extinguish = next(e for e in proposed if isinstance(e, Extinguish))
    assert extinguish.cause is ExtinguishCause.RETURNED
    assert extinguish.at == _NOW + timedelta(days=12)  # daté de la rencontre, pas de la saisie
    assert any(type(e).__name__ == "RecordMemory" for e in proposed)


# --- Versionnement : le passé ne change jamais de sens -----------------------------------------


def test_an_older_fact_keeps_the_interpreter_it_entered_with():
    """Publier une V2 ne réécrit pas le sens de ce qui est déjà au ledger."""

    class _V2:
        kind = FactKind.LIFE_EVENT_ANNOUNCED
        version = 2
        effective_from = datetime(2026, 6, 1, tzinfo=UTC)

        def interpret(self, fact, state):
            return []

    registry = InterpreterRegistry()
    registry.register(LifeEventAnnouncedV1())
    registry.register(_V2())

    ancien = _fact(FactKind.LIFE_EVENT_ANNOUNCED, uuid4(), recorded_at=_NOW)
    nouveau = _fact(
        FactKind.LIFE_EVENT_ANNOUNCED, uuid4(), recorded_at=datetime(2026, 7, 1, tzinfo=UTC)
    )

    assert registry.for_fact(ancien).version == 1
    assert registry.for_fact(nouveau).version == 2


def test_a_fact_without_an_interpreter_is_kept_not_lost():
    """Un kind sans interpreter ne fait pas tomber l'intake : le fait reste au journal.

    Le jour où l'interpreter arrive, une reprojection lui donne rétroactivement son sens."""
    registry = InterpreterRegistry()
    registry.register(LifeEventAnnouncedV1())

    orphelin = _fact(FactKind.GRATITUDE_DEPOSITED, uuid4(), source="gratitude")

    assert registry.interpret(orphelin, WatchStateView()) == []
