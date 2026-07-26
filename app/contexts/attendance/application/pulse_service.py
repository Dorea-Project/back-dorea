"""Calcul partagé de l'état de marche d'un groupe (M7) — réutilisé par la pulsation et l'effectif.

Assemble le flux de présences par membre, calcule l'état (pur, `compute_walk_state`), applique
l'override `shared` (signal réseau), et repère l'**absence en cours** + sa **gravité** (crochet
effectif M7-1). Isole cette logique pour que `GetGroupPulse` et `GetGroupEffectif` la partagent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.contexts.attendance.domain.gravity import AbsenceGravity, gravity_of
from app.contexts.attendance.domain.pulse import (
    CARE_STATES,
    Outcome,
    WalkState,
    compute_walk_state,
)
from app.contexts.attendance.domain.repositories import (
    AttendanceRecordRepository,
    GatheringRepository,
    PlannedAbsenceRepository,
    WatchExclusionRepository,
)
from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.repositories import GroupMembershipRepository


@dataclass(frozen=True)
class MemberPulse:
    account_id: UUID
    state: WalkState
    missed: int
    last_present_at: datetime | None
    current_absence_gravity: AbsenceGravity | None  # gravité d'une absence couvrant *maintenant*


@dataclass(frozen=True)
class TrajectoryPoint:
    gathering_id: UUID
    scheduled_at: datetime
    outcome: Outcome  # present / excused / absent
    title: str | None


@dataclass(frozen=True)
class MemberTrajectory:
    """La frise d'un membre dans une cellule : l'histoire, pas un verdict (drill-down soin)."""

    account_id: UUID
    state: WalkState
    missed: int  # silence concerné (rencontres absentes depuis la dernière venue)
    last_present_at: datetime | None
    active_elsewhere: bool  # présent dans une autre église depuis (compte global, sans révéler où)
    current_absence_reason: str | None  # tag d'une absence déclarée couvrant *maintenant*
    current_absence_gravity: AbsenceGravity | None
    points: list[TrajectoryPoint]  # chronologique (plus ancien d'abord), depuis son adhésion


@dataclass(frozen=True)
class EffectifStats:
    active: int  # membres vivants (hors dormants & déménagés)
    at_risk: int
    shared: int
    review: list[tuple[UUID, str]]  # (account_id, reason) — suggestions, jamais auto


def classify_effectif(pulses: list[MemberPulse]) -> EffectifStats:
    """Classe les états en effectif honnête + candidats à revoir (partagé M7-1/M7-3)."""
    active = at_risk = shared = 0
    review: list[tuple[UUID, str]] = []
    for p in pulses:
        # Le déménagement déclaré prime (raison la plus informative), même si aussi silencieux.
        if p.current_absence_gravity is AbsenceGravity.STRUCTURAL:
            review.append((p.account_id, "declared_moved"))
            continue
        if p.state is WalkState.DORMANT:
            review.append((p.account_id, "prolonged_silence"))
            continue
        active += 1
        if p.state is WalkState.AT_RISK:
            at_risk += 1
        elif p.state is WalkState.SHARED:
            shared += 1
    return EffectifStats(active=active, at_risk=at_risk, shared=shared, review=review)


class GroupPulseComputer:
    def __init__(
        self,
        gatherings: GatheringRepository,
        records: AttendanceRecordRepository,
        absences: PlannedAbsenceRepository,
        group_memberships: GroupMembershipRepository,
        exclusions: WatchExclusionRepository | None = None,
    ) -> None:
        self._gatherings = gatherings
        self._records = records
        self._absences = absences
        self._group_memberships = group_memberships
        self._exclusions = exclusions

    async def _excluded(self, tenant_id: UUID) -> set[UUID]:
        """Les personnes retirées de la veille (décès annoncé) — on ne calcule rien sur elles."""
        if self._exclusions is None:
            return set()
        return await self._exclusions.excluded_account_ids(tenant_id)

    async def compute(self, *, group: Group, now: datetime) -> list[MemberPulse]:
        gatherings = [
            g for g in await self._gatherings.list_by_group(group.id) if g.scheduled_at <= now
        ]
        gatherings.sort(key=lambda g: g.scheduled_at)

        present = {
            (r.gathering_id, r.account_id)
            for r in await self._records.list_present_for_gatherings([g.id for g in gatherings])
        }
        tenant_absences = await self._absences.list_active_by_tenant(group.tenant_id)
        excluded = await self._excluded(group.tenant_id)
        # Un membre pas encore arrivé à `now` n'est pas du groupe à cette date (snapshot honnête
        # quand on recule l'horloge pour une tendance — sans effet quand `now` = maintenant).
        # Une personne hors veille (décès annoncé) sort du calcul : sans cela, le moteur
        # signalerait son silence six semaines plus tard.
        members = [
            m
            for m in await self._group_memberships.list_active_by_group(group.id)
            if m.joined_at <= now and m.account_id not in excluded
        ]

        result: list[MemberPulse] = []
        for m in members:
            # On ne juge que les rencontres **depuis son arrivée** (sinon un nouveau membre
            # d'une vieille cellule apparaîtrait « dormant » à tort).
            since_join = [g for g in gatherings if g.scheduled_at >= m.joined_at]
            outcomes = [
                self._outcome(g, m.account_id, present, tenant_absences) for g in since_join
            ]
            state, missed = compute_walk_state(outcomes)
            last_present_at = self._last_present_at(since_join, m.account_id, present)

            if state in CARE_STATES and last_present_at is not None:
                if await self._records.has_present_in_other_tenant_since(
                    m.account_id, group.tenant_id, last_present_at
                ):
                    state = WalkState.SHARED

            covering = next(
                (a for a in tenant_absences if a.account_id == m.account_id and a.covers(now)),
                None,
            )
            gravity = gravity_of(covering.reason) if covering is not None else None
            result.append(
                MemberPulse(m.account_id, state, missed, last_present_at, gravity)
            )
        return result

    async def trajectory(
        self, *, group: Group, account_id: UUID, now: datetime
    ) -> MemberTrajectory | None:
        """La frise d'un seul membre : ses rencontres depuis son arrivée + son état actuel.

        Renvoie None si le compte n'est pas membre actif du groupe (drill-down invalide)."""
        membership = await self._group_memberships.get_active(account_id, group.id)
        if membership is None:
            return None
        if account_id in await self._excluded(group.tenant_id):
            return None  # hors veille : il n'y a plus de trajectoire à lire

        gatherings = [
            g for g in await self._gatherings.list_by_group(group.id) if g.scheduled_at <= now
        ]
        gatherings.sort(key=lambda g: g.scheduled_at)
        present = {
            (r.gathering_id, r.account_id)
            for r in await self._records.list_present_for_gatherings([g.id for g in gatherings])
        }
        tenant_absences = await self._absences.list_active_by_tenant(group.tenant_id)

        since_join = [g for g in gatherings if g.scheduled_at >= membership.joined_at]
        outcomes = [self._outcome(g, account_id, present, tenant_absences) for g in since_join]
        state, missed = compute_walk_state(outcomes)
        last_present_at = self._last_present_at(since_join, account_id, present)

        active_elsewhere = last_present_at is not None and (
            await self._records.has_present_in_other_tenant_since(
                account_id, group.tenant_id, last_present_at
            )
        )
        if state in CARE_STATES and active_elsewhere:
            state = WalkState.SHARED

        covering = next(
            (a for a in tenant_absences if a.account_id == account_id and a.covers(now)), None
        )
        points = [
            TrajectoryPoint(g.id, g.scheduled_at, o, g.title)
            for g, o in zip(since_join, outcomes, strict=True)
        ]
        return MemberTrajectory(
            account_id=account_id,
            state=state,
            missed=missed,
            last_present_at=last_present_at,
            active_elsewhere=active_elsewhere,
            current_absence_reason=covering.reason.value if covering is not None else None,
            current_absence_gravity=(
                gravity_of(covering.reason) if covering is not None else None
            ),
            points=points,
        )

    @staticmethod
    def _outcome(gathering, account_id, present, tenant_absences) -> Outcome:
        if (gathering.id, account_id) in present:
            return Outcome.PRESENT
        if any(
            a.account_id == account_id and a.covers(gathering.scheduled_at)
            for a in tenant_absences
        ):
            return Outcome.EXCUSED
        return Outcome.ABSENT

    @staticmethod
    def _last_present_at(gatherings, account_id, present):
        dates = [g.scheduled_at for g in gatherings if (g.id, account_id) in present]
        return max(dates) if dates else None
