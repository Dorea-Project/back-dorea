"""Use cases **de disponibilité** (backoffice) — définir quand un pasteur reçoit.

Récurrence hebdomadaire : un gardien (`MANAGE_APPOINTMENTS`) pose une `AvailabilityRule` pour un
**pasteur** (le membre visé doit vraiment avoir le rôle Pasteur), ou la désactive.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.appointments.application.dtos import AvailabilityRuleDTO
from app.contexts.appointments.application.mapping import to_rule_dto
from app.contexts.appointments.domain.availability import AvailabilityRule
from app.contexts.appointments.domain.errors import (
    AvailabilityRuleNotFoundError,
    NotAPastorError,
)
from app.contexts.appointments.domain.repositories import AvailabilityRuleRepository
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.enums import RoleCode
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MembershipRepository


async def _ensure_keeper(access: GroupAccessPolicy, *, actor_account_id: UUID, tenant_id: UUID):
    await access.ensure_church_wide(
        actor_account_id=actor_account_id,
        tenant_id=tenant_id,
        permission=Permission.MANAGE_APPOINTMENTS,
    )


async def ensure_is_pastor(
    memberships: MembershipRepository, *, account_id: UUID, tenant_id: UUID
) -> None:
    membership = await memberships.get_active(account_id, tenant_id)
    if membership is None or not any(
        ra.role is RoleCode.PASTOR for ra in membership.active_roles()
    ):
        raise NotAPastorError(
            "Ce membre n'est pas pasteur — pas d'agenda à lui ouvrir.",
            details={"account_id": str(account_id)},
        )


class AddAvailabilityRule:
    def __init__(
        self,
        rules: AvailabilityRuleRepository,
        memberships: MembershipRepository,
        access: GroupAccessPolicy,
        *,
        clock,
    ) -> None:
        self._rules = rules
        self._memberships = memberships
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        pastor_account_id: UUID,
        weekday: int,
        start_minute: int,
        end_minute: int,
        slot_minutes: int,
    ) -> AvailabilityRuleDTO:
        await _ensure_keeper(
            self._access, actor_account_id=actor_account_id, tenant_id=tenant_id
        )
        await ensure_is_pastor(
            self._memberships, account_id=pastor_account_id, tenant_id=tenant_id
        )
        rule = AvailabilityRule.create(
            id=uuid4(),
            tenant_id=tenant_id,
            pastor_account_id=pastor_account_id,
            weekday=weekday,
            start_minute=start_minute,
            end_minute=end_minute,
            slot_minutes=slot_minutes,
            now=self._clock(),
        )
        await self._rules.add(rule)
        return to_rule_dto(rule)


class DeactivateAvailabilityRule:
    def __init__(
        self, rules: AvailabilityRuleRepository, access: GroupAccessPolicy
    ) -> None:
        self._rules = rules
        self._access = access

    async def execute(self, *, actor_account_id: UUID, rule_id: UUID) -> None:
        rule = await self._rules.get(rule_id)
        if rule is None:
            raise AvailabilityRuleNotFoundError(
                "Disponibilité introuvable.", details={"rule_id": str(rule_id)}
            )
        await _ensure_keeper(
            self._access, actor_account_id=actor_account_id, tenant_id=rule.tenant_id
        )
        rule.deactivate()
        await self._rules.save(rule)
