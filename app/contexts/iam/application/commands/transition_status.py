"""Use case `TransitionStatus` — fait avancer le statut d'un membre (§5.5).

RBAC : l'acteur doit détenir `MANAGE_MEMBERSHIP` dans le tenant (Admin ou Intégration).
La transition elle-même est validée par la table de domaine (`next_status`), qui
interdit les sauts de palier (fast-track invited→member interdit en V1).

`first_attendance_recorded` (invited→visitor) sera aussi déclenché **automatiquement**
par M6 (présences) ; ici on couvre les événements manuels du backoffice.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.dtos import TransitionResult
from app.contexts.iam.application.ports import MembershipTransitionStore
from app.contexts.iam.domain.enums import MembershipTransitionEvent
from app.contexts.iam.domain.errors import MembershipNotFoundError
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.iam.domain.transitions import next_status


class TransitionStatus:
    def __init__(
        self,
        memberships: MembershipRepository,
        store: MembershipTransitionStore,
        access: AccessControl,
        *,
        clock,
    ) -> None:
        self._memberships = memberships
        self._store = store
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        target_account_id: UUID,
        event: MembershipTransitionEvent,
    ) -> TransitionResult:
        # Autorisation : gérer les statuts exige MANAGE_MEMBERSHIP (Admin/Intégration).
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.MANAGE_MEMBERSHIP,
        )

        target = await self._memberships.get_active(target_account_id, tenant_id)
        if target is None:
            raise MembershipNotFoundError(
                "Aucune appartenance active pour ce compte dans ce tenant.",
                details={"account_id": str(target_account_id), "tenant_id": str(tenant_id)},
            )

        # Table de domaine : lève InvalidTransition / StatusSkipForbidden si non permis.
        new = next_status(target.status, event)

        await self._store.apply_transition(
            membership_id=target.id,
            new_status=new,
            previous_status=target.status,
            transitioned_at=self._clock(),
        )

        return TransitionResult(
            membership_id=target.id,
            status=new.value,
            previous_status=target.status.value,
        )
