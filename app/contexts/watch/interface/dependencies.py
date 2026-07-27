"""Assemblage du moteur de veille.

Le registre des sources et celui des interpreters sont construits **une fois** au chargement du
module : ce sont des structures, pas de l'état. C'est aussi ce qui fait que l'ajout d'un kind de
forme interdite fait échouer le démarrage de l'application — et pas une requête, un jour, chez
un client.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.contexts.attendance.infrastructure.persistence.absence_repository import (
    SqlPlannedAbsenceRepository,
    SqlWatchExclusionRepository,
)
from app.contexts.watch.application.designate_referent import DesignateReferent
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.appointment_requested import (
    AppointmentRequestedV1,
)
from app.contexts.watch.application.interpreters.life_event_announced import (
    LifeEventAnnouncedV1,
)
from app.contexts.watch.application.interpreters.presence_recorded import PresenceRecordedV1
from app.contexts.watch.application.projections import RebuildProjections
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
from app.contexts.watch.infrastructure.persistence.ledger import SqlFactLedger
from app.contexts.watch.infrastructure.persistence.referent import (
    SqlCoverageGapStore,
    SqlGroupTypePolicyRepository,
    SqlPrimaryGroupOverrideRepository,
    SqlReferentHistoryRepository,
    SqlReferentOverrideRepository,
)
from app.contexts.watch.infrastructure.persistence.signals import SqlSignalStore

SOURCES = default_registry()

INTERPRETERS = InterpreterRegistry()
INTERPRETERS.register(LifeEventAnnouncedV1())
INTERPRETERS.register(PresenceRecordedV1())
INTERPRETERS.register(AppointmentRequestedV1())


def build_store(session) -> AttendanceNeutralizationStore:
    return AttendanceNeutralizationStore(
        SqlPlannedAbsenceRepository(session), SqlWatchExclusionRepository(session)
    )


def build_signals(session) -> SqlSignalStore:
    return SqlSignalStore(session)


def build_intake(session) -> Intake:
    return Intake(
        SqlFactLedger(session), SOURCES, INTERPRETERS,
        build_store(session), build_signals(session),
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
    return RebuildProjections(
        SqlFactLedger(session), INTERPRETERS, build_store(session), build_signals(session)
    )
