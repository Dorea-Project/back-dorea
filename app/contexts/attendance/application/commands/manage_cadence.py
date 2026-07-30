"""Commandes de la Fondation A (P1) — déclarer le rythme, acquitter une occurrence, suspendre.

Ces commandes **peuplent** les fondations ; elles n'émettent aucune alerte (P2).

**L'autorisation vit ici**, pas dans les routes. Le docstring d'origine la renvoyait à la couche
interface ; c'est le genre de report qui laisse une commande nue accessible par la prochaine
surface qu'on branchera sans y penser. `MANAGE_GROUP` sur le groupe pour la cadence et
l'acquittement, autorité **église-entière** pour la suspension.

Pourquoi `MANAGE_GROUP` et non `RECORD_ATTENDANCE` pour l'acquittement : acquitter **retire une
occurrence du dénominateur** de couverture. C'est précisément la surface d'échappatoire du
module — celui qui peut la poser doit être celui qui répond du groupe.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.attendance.application.dtos import (
    CadenceAcknowledgementDTO,
    ChurchSuspensionDTO,
    GroupCadenceDTO,
)
from app.contexts.attendance.domain.cadence import (
    AcknowledgementReason,
    CadenceAcknowledgement,
    CadenceFrequency,
    ChurchSuspension,
    GroupCadence,
    SuspensionReason,
)
from app.contexts.attendance.domain.errors import (
    CadenceAlreadyExistsError,
    InvalidCadenceError,
    InvalidSuspensionPeriodError,
)
from app.contexts.attendance.domain.repositories import (
    CadenceAcknowledgementRepository,
    ChurchSuspensionRepository,
    GroupCadenceRepository,
)
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission

_STEP_FREQUENCIES = {CadenceFrequency.WEEKLY, CadenceFrequency.BIWEEKLY}


def _cadence_dto(c: GroupCadence) -> GroupCadenceDTO:
    return GroupCadenceDTO(
        id=c.id,
        group_id=c.group_id,
        frequency=c.frequency.value,
        weekday=c.weekday,
        day_of_month=c.day_of_month,
        anchor_date=c.anchor_date,
        active_from=c.active_from,
        active_until=c.active_until,
    )


class DeclareCadence:
    """Déclare le rythme attendu d'un groupe (au plus une cadence active par groupe)."""

    def __init__(
        self,
        cadences: GroupCadenceRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._cadences = cadences
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        frequency: CadenceFrequency,
        anchor_date: datetime,
        active_from: datetime,
        weekday: int | None = None,
        day_of_month: int | None = None,
        active_until: datetime | None = None,
    ) -> GroupCadenceDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id, group=group, permission=Permission.MANAGE_GROUP
        )
        self._validate(frequency, weekday, day_of_month, active_from, active_until)
        if await self._cadences.get_active_by_group(group_id) is not None:
            raise CadenceAlreadyExistsError(
                "Ce groupe a déjà une cadence active.",
                details={"group_id": str(group_id)},
            )
        cadence = GroupCadence(
            id=uuid4(),
            tenant_id=tenant_id,
            group_id=group_id,
            frequency=frequency,
            anchor_date=anchor_date,
            active_from=active_from,
            created_at=self._clock(),
            created_by_account_id=actor_account_id,
            weekday=weekday,
            day_of_month=day_of_month,
            active_until=active_until,
        )
        await self._cadences.add(cadence)
        return _cadence_dto(cadence)

    @staticmethod
    def _validate(frequency, weekday, day_of_month, active_from, active_until) -> None:
        if frequency in _STEP_FREQUENCIES and weekday is None:
            raise InvalidCadenceError(
                "Une cadence hebdomadaire/bihebdomadaire exige un jour de semaine.",
                details={"frequency": frequency.value},
            )
        if frequency in _STEP_FREQUENCIES and weekday is not None and not 0 <= weekday <= 6:
            raise InvalidCadenceError("Jour de semaine hors 0-6.", details={"weekday": weekday})
        if frequency is CadenceFrequency.MONTHLY:
            if day_of_month is None or not 1 <= day_of_month <= 28:
                raise InvalidCadenceError(
                    "Une cadence mensuelle exige un jour du mois entre 1 et 28.",
                    details={"day_of_month": day_of_month},
                )
        if active_until is not None and active_until < active_from:
            raise InvalidCadenceError(
                "La fin de validité précède le début.",
                details={
                    "active_from": active_from.isoformat(),
                    "active_until": active_until.isoformat(),
                },
            )


class AcknowledgeOccurrence:
    """Acquitte une occurrence non tenue (motif connu). Idempotent : re-poser renvoie l'existant."""

    def __init__(
        self,
        acks: CadenceAcknowledgementRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._acks = acks
        self._groups = groups
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        group_id: UUID,
        occurrence_date: datetime,
        reason: AcknowledgementReason,
    ) -> CadenceAcknowledgementDTO:
        group = await load_group_in_tenant(self._groups, group_id, tenant_id)
        await self._access.ensure_can(
            actor_account_id=actor_account_id, group=group, permission=Permission.MANAGE_GROUP
        )
        existing = await self._acks.get_for(group_id, occurrence_date)
        if existing is not None:
            return _ack_dto(existing)
        ack = CadenceAcknowledgement(
            id=uuid4(),
            tenant_id=tenant_id,
            group_id=group_id,
            occurrence_date=occurrence_date,
            reason=reason,
            acknowledged_by_account_id=actor_account_id,
            acknowledged_at=self._clock(),
        )
        await self._acks.add(ack)
        return _ack_dto(ack)


def _ack_dto(a: CadenceAcknowledgement) -> CadenceAcknowledgementDTO:
    return CadenceAcknowledgementDTO(
        id=a.id,
        group_id=a.group_id,
        occurrence_date=a.occurrence_date,
        reason=a.reason.value,
    )


class SuspendChurch:
    """Pose une suspension église (Noël, deuil). La cascade d'acquittement est calculée à la
    lecture — aucune ligne d'acquittement n'est générée par groupe."""

    def __init__(
        self,
        suspensions: ChurchSuspensionRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._suspensions = suspensions
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        reason: SuspensionReason,
        from_date: datetime,
        to_date: datetime,
    ) -> ChurchSuspensionDTO:
        # Une suspension touche **toute** l'église : elle ne se décide pas depuis un groupe.
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.MANAGE_GROUP,
        )
        if to_date < from_date:
            raise InvalidSuspensionPeriodError(
                "La fin de la période précède le début.",
                details={"from": from_date.isoformat(), "to": to_date.isoformat()},
            )
        suspension = ChurchSuspension(
            id=uuid4(),
            tenant_id=tenant_id,
            reason=reason,
            from_date=from_date,
            to_date=to_date,
            declared_by_account_id=actor_account_id,
            declared_at=self._clock(),
        )
        await self._suspensions.add(suspension)
        return ChurchSuspensionDTO(
            id=suspension.id,
            tenant_id=tenant_id,
            reason=reason.value,
            from_date=from_date,
            to_date=to_date,
        )
