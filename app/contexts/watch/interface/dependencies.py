"""Assemblage du moteur de veille.

Le registre des sources et celui des interpreters sont construits **une fois** au chargement du
module : ce sont des structures, pas de l'état. C'est aussi ce qui fait que l'ajout d'un kind de
forme interdite fait échouer le démarrage de l'application — et pas une requête, un jour, chez
un client.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import Depends

from app.api.deps import DbSession
from app.contexts.attendance.infrastructure.persistence.absence_repository import (
    SqlPlannedAbsenceRepository,
    SqlWatchExclusionRepository,
)
from app.contexts.notifications.interface.dependencies import build_scheduler
from app.contexts.watch.application.concern_watchdog import (
    EscalateStaleConcerns,
    GuardAgainstDumping,
    MeasureConcernPrecision,
)
from app.contexts.watch.application.contact_loop import (
    AnswerContact,
    PendingAttempts,
    StartContact,
)
from app.contexts.watch.application.designate_referent import DesignateReferent
from app.contexts.watch.application.fire_checks import FireDueChecks
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.appointment_requested import (
    AppointmentRequestedV1,
)
from app.contexts.watch.application.interpreters.life_event_announced import (
    LifeEventAnnouncedV1,
)
from app.contexts.watch.application.interpreters.presence_recorded import PresenceRecordedV1
from app.contexts.watch.application.interpreters.self_declaration import SelfDeclarationV1
from app.contexts.watch.application.interpreters.third_party_concern import (
    ThirdPartyConcernV1,
)
from app.contexts.watch.application.my_cases import CloseCase, ListMyCases, SeeCase
from app.contexts.watch.application.owner_assignment import ResolveOwners
from app.contexts.watch.application.projections import RebuildProjections
from app.contexts.watch.application.raise_concern import RaiseConcern
from app.contexts.watch.application.referent_resolution import (
    MeasureReferentGap,
    ResolveReferent,
    ResolveSignalOwner,
)
from app.contexts.watch.domain.registry import default_registry
from app.contexts.watch.infrastructure.directories import (
    SqlGroupDirectory,
    SqlInviterDirectory,
    SqlPeopleDirectory,
)
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from app.contexts.watch.infrastructure.persistence.checks import SqlScheduledCheckStore
from app.contexts.watch.infrastructure.persistence.ledger import SqlFactLedger
from app.contexts.watch.infrastructure.persistence.referent import (
    SqlCoverageGapStore,
    SqlGroupTypePolicyRepository,
    SqlPrimaryGroupOverrideRepository,
    SqlReferentHistoryRepository,
    SqlReferentOverrideRepository,
    SqlWatchParameterRepository,
)
from app.contexts.watch.infrastructure.persistence.signals import (
    SqlContactAttemptStore,
    SqlSignalStore,
)

SOURCES = default_registry()

INTERPRETERS = InterpreterRegistry()
INTERPRETERS.register(LifeEventAnnouncedV1())
INTERPRETERS.register(PresenceRecordedV1())
INTERPRETERS.register(AppointmentRequestedV1())
INTERPRETERS.register(SelfDeclarationV1())
INTERPRETERS.register(ThirdPartyConcernV1())


def build_store(session) -> AttendanceNeutralizationStore:
    return AttendanceNeutralizationStore(
        SqlPlannedAbsenceRepository(session), SqlWatchExclusionRepository(session)
    )


def build_signals(session) -> SqlSignalStore:
    return SqlSignalStore(session)


def build_checks(session) -> SqlScheduledCheckStore:
    return SqlScheduledCheckStore(session)


def build_intake(session) -> Intake:
    """La pipeline complète — **avec** l'étage 02bis.

    Sans le résolveur de destinataire, une ouverture de cas arriverait en base avec un
    `owner_account_id` nul sur une colonne NOT NULL : l'écriture échouerait, et un fait légitime
    serait perdu au moment où il compte."""
    return Intake(
        SqlFactLedger(session), SOURCES, INTERPRETERS,
        build_store(session), build_signals(session), build_checks(session),
        build_owner_assignment(session),
    )


def build_owner_assignment(session) -> ResolveOwners:
    return ResolveOwners(build_signal_owner(session), SqlPeopleDirectory(session))


def build_fire_checks(session) -> FireDueChecks:
    """Le temps entre par le ledger — et sous plafond, pour ne pas noyer après une panne."""
    return FireDueChecks(
        build_checks(session),
        build_intake(session),
        SqlWatchParameterRepository(session),
        clock=lambda: datetime.now(UTC),
        id_factory=uuid4,
    )


def build_referents(session) -> ResolveReferent:
    """La cascade. Rien n'est stocké : le référent est résolu à chaque lecture."""
    return ResolveReferent(
        SqlReferentOverrideRepository(session),
        SqlPrimaryGroupOverrideRepository(session),
        SqlGroupTypePolicyRepository(session),
        SqlGroupDirectory(session),
        SqlPeopleDirectory(session),
        SqlInviterDirectory(session),
        build_store(session),
    )


def build_signal_owner(session) -> ResolveSignalOwner:
    """À qui adresser un cas — **jamais nul**, contrairement au référent.

    Le store de couverture est branché : une église sans destinataire ne peut pas rester
    silencieuse sans que ce silence soit lui-même visible."""
    return ResolveSignalOwner(
        build_referents(session),
        SqlPeopleDirectory(session),
        SqlCoverageGapStore(session),
        id_factory=uuid4,
    )


def build_referent_gap(session) -> MeasureReferentGap:
    return MeasureReferentGap(
        build_referents(session),
        SqlReferentHistoryRepository(session),
        SqlPeopleDirectory(session),
    )


def build_designate_referent(session) -> DesignateReferent:
    return DesignateReferent(
        SqlReferentOverrideRepository(session),
        SqlReferentHistoryRepository(session),
        SqlPeopleDirectory(session),
        build_referents(session),
        id_factory=uuid4,
        clock=lambda: datetime.now(UTC),
    )


def build_rebuild(session) -> RebuildProjections:
    """Le rejeu porte la **même** pipeline que le direct : étage 02bis et échéances comprises.

    Sans l'étage 02bis, il réécrirait des propriétaires nuls sur une colonne qui n'en accepte plus.
    Sans le store d'échéances, il effacerait les relances programmées d'une église et n'en
    reposerait aucune — en silence."""
    return RebuildProjections(
        SqlFactLedger(session), INTERPRETERS, build_store(session), build_signals(session),
        build_owner_assignment(session), build_checks(session),
    )


def build_raise_concern(session) -> RaiseConcern:
    """« Je m'en occupe cette semaine. » — la source la moins chère du produit."""
    return RaiseConcern(
        build_intake(session),
        build_signal_owner(session),
        build_signals(session),
        build_store(session),
        clock=lambda: datetime.now(UTC),
        id_factory=uuid4,
    )


def build_escalate_concerns(session) -> EscalateStaleConcerns:
    return EscalateStaleConcerns(
        build_signals(session),
        SqlCoverageGapStore(session),
        SqlWatchParameterRepository(session),
        clock=lambda: datetime.now(UTC),
        id_factory=uuid4,
    )


def build_dumping_guard(session) -> GuardAgainstDumping:
    return GuardAgainstDumping(
        build_signals(session),
        SqlCoverageGapStore(session),
        SqlWatchParameterRepository(session),
        clock=lambda: datetime.now(UTC),
        id_factory=uuid4,
    )


def build_concern_precision(session) -> MeasureConcernPrecision:
    return MeasureConcernPrecision(
        build_signals(session),
        SqlWatchParameterRepository(session),
        clock=lambda: datetime.now(UTC),
    )


def build_contacts(session) -> SqlContactAttemptStore:
    return SqlContactAttemptStore(session)


# --- Injection FastAPI ------------------------------------------------------------------------

_now = lambda: datetime.now(UTC)  # noqa: E731 — une horloge, pas une fonction métier


async def get_raise_concern(session: DbSession) -> RaiseConcern:
    return build_raise_concern(session)


async def get_my_cases(session: DbSession) -> ListMyCases:
    return ListMyCases(build_signals(session))


async def get_see_case(session: DbSession) -> SeeCase:
    return SeeCase(build_signals(session), clock=_now)


async def get_close_case(session: DbSession) -> CloseCase:
    return CloseCase(build_signals(session), clock=_now)


async def get_start_contact(session: DbSession) -> StartContact:
    return StartContact(
        build_contacts(session),
        build_signals(session),
        build_scheduler(session),  # le rappel de retour part d'ici, ou nulle part
        clock=_now,
        id_factory=uuid4,
    )


async def get_answer_contact(session: DbSession) -> AnswerContact:
    return AnswerContact(build_contacts(session), build_signals(session), clock=_now)


async def get_pending_attempts(session: DbSession) -> PendingAttempts:
    return PendingAttempts(build_contacts(session), clock=_now)


RaiseConcernDep = Annotated[RaiseConcern, Depends(get_raise_concern)]
ListMyCasesDep = Annotated[ListMyCases, Depends(get_my_cases)]
SeeCaseDep = Annotated[SeeCase, Depends(get_see_case)]
CloseCaseDep = Annotated[CloseCase, Depends(get_close_case)]
StartContactDep = Annotated[StartContact, Depends(get_start_contact)]
AnswerContactDep = Annotated[AnswerContact, Depends(get_answer_contact)]
PendingAttemptsDep = Annotated[PendingAttempts, Depends(get_pending_attempts)]
