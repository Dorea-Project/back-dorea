"""Use cases du **transfert de membre entre églises** (poignée de main, acte gouverné).

Chaque côté n'agit que sur **sa** maison (souveraineté du tenant) :
- `RequestTransfer` — la **destination** demande à recevoir (autorité sur le tenant destination).
- `AcceptTransfer` — la **source** libère : la saga clôture l'appartenance source
  (`changed_church`, cascade des rôles), la fait quitter les groupes source, puis ouvre / confirme
  une appartenance `confirmed_member` à destination (+ placement en cellule optionnel).
- `DeclineTransfer` — la source refuse. `CancelTransfer` — la destination retire sa demande.

Le **Compte ne bouge jamais** (identité globale) ; on ne mute jamais une autre église sans son
consentement. Les mêmes garde-fous que la clôture protègent la source : jamais le dernier Owner,
jamais le dernier responsable d'un groupe.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.iam.application.access_control import AccessControl
from app.contexts.iam.application.dtos import TransferDTO
from app.contexts.iam.application.ports import (
    MemberEnrollmentStore,
    MemberRosterPort,
    MembershipLifecycleStore,
    MembershipTransitionStore,
)
from app.contexts.iam.domain.aggregates import Membership
from app.contexts.iam.domain.enums import (
    MembershipClosureReason,
    MembershipStatus,
)
from app.contexts.iam.domain.errors import (
    DuplicatePendingTransferError,
    GroupLastLeaderRemovalBlockedError,
    LastOwnerRemovalBlockedError,
    MembershipNotFoundError,
    SameTenantTransferError,
    TransferNotFoundError,
)
from app.contexts.iam.domain.permissions import Permission
from app.contexts.iam.domain.repositories import (
    MembershipRepository,
    MemberTransferRepository,
)
from app.contexts.iam.domain.transfer import MemberTransfer


def to_transfer_dto(t: MemberTransfer) -> TransferDTO:
    return TransferDTO(
        id=t.id,
        account_id=t.account_id,
        from_tenant_id=t.from_tenant_id,
        to_tenant_id=t.to_tenant_id,
        to_group_id=t.to_group_id,
        status=t.status.value,
        requested_at=t.requested_at,
        resolved_at=t.resolved_at,
    )


class RequestTransfer:
    def __init__(
        self,
        transfers: MemberTransferRepository,
        memberships: MembershipRepository,
        access: AccessControl,
        *,
        clock,
    ) -> None:
        self._transfers = transfers
        self._memberships = memberships
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        account_id: UUID,
        from_tenant_id: UUID,
        to_tenant_id: UUID,
        to_group_id: UUID | None = None,
    ) -> TransferDTO:
        if from_tenant_id == to_tenant_id:
            raise SameTenantTransferError(
                "La source et la destination sont la même église.",
                details={"tenant_id": str(from_tenant_id)},
            )
        # La destination demande : elle agit sur SA maison.
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=to_tenant_id,
            permission=Permission.TRANSFER_MEMBER,
        )
        # Rien à transférer si le membre n'appartient pas (activement) à la source.
        if await self._memberships.get_active(account_id, from_tenant_id) is None:
            raise MembershipNotFoundError(
                "Ce compte n'a pas d'appartenance active dans l'église source.",
                details={"account_id": str(account_id), "tenant_id": str(from_tenant_id)},
            )
        if await self._transfers.get_pending(account_id, from_tenant_id, to_tenant_id) is not None:
            raise DuplicatePendingTransferError(
                "Une demande de transfert est déjà en attente pour ce membre.",
                details={"account_id": str(account_id)},
            )

        transfer = MemberTransfer(
            id=uuid4(),
            account_id=account_id,
            from_tenant_id=from_tenant_id,
            to_tenant_id=to_tenant_id,
            to_group_id=to_group_id,
            requested_by_account_id=actor_account_id,
            requested_at=self._clock(),
        )
        await self._transfers.add(transfer)
        return to_transfer_dto(transfer)


class AcceptTransfer:
    def __init__(
        self,
        transfers: MemberTransferRepository,
        memberships: MembershipRepository,
        lifecycle: MembershipLifecycleStore,
        enrollment: MemberEnrollmentStore,
        transitions: MembershipTransitionStore,
        roster: MemberRosterPort,
        access: AccessControl,
        *,
        clock,
    ) -> None:
        self._transfers = transfers
        self._memberships = memberships
        self._lifecycle = lifecycle
        self._enrollment = enrollment
        self._transitions = transitions
        self._roster = roster
        self._access = access
        self._clock = clock

    async def execute(self, *, actor_account_id: UUID, transfer_id: UUID) -> TransferDTO:
        transfer = await self._load_pending(transfer_id)
        # La source libère : elle agit sur SA maison.
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=transfer.from_tenant_id,
            permission=Permission.TRANSFER_MEMBER,
        )

        source = await self._memberships.get_active(
            transfer.account_id, transfer.from_tenant_id
        )
        if source is None:
            raise MembershipNotFoundError(
                "Le membre n'appartient plus à l'église source.",
                details={"account_id": str(transfer.account_id)},
            )
        await self._guard_source_release(source, transfer)

        now = self._clock()
        # 1. Libérer l'appartenance source (cascade des rôles) + quitter ses groupes source.
        await self._lifecycle.close_membership(
            membership_id=source.id,
            closed_at=now,
            closure_reason=MembershipClosureReason.CHANGED_CHURCH,
        )
        await self._roster.release_from_tenant(
            account_id=transfer.account_id, tenant_id=transfer.from_tenant_id, now=now
        )
        # 2. Ouvrir / confirmer l'appartenance destination (confirmed_member).
        await self._settle_destination(transfer, actor_account_id, now)
        # 3. Placement en cellule destination (optionnel).
        if transfer.to_group_id is not None:
            await self._roster.place_in_group(
                account_id=transfer.account_id,
                tenant_id=transfer.to_tenant_id,
                group_id=transfer.to_group_id,
                now=now,
                by_account_id=actor_account_id,
            )
        # 4. Marquer le transfert accepté.
        transfer.accept(by_account_id=actor_account_id, now=now)
        await self._transfers.save(transfer)
        return to_transfer_dto(transfer)

    async def _load_pending(self, transfer_id: UUID) -> MemberTransfer:
        transfer = await self._transfers.get(transfer_id)
        if transfer is None:
            raise TransferNotFoundError(
                "Transfert introuvable.", details={"transfer_id": str(transfer_id)}
            )
        return transfer

    async def _guard_source_release(self, source: Membership, transfer: MemberTransfer) -> None:
        # Jamais le dernier Owner (succession = acte Plateforme).
        if await self._access.is_owner(transfer.account_id, transfer.from_tenant_id):
            raise LastOwnerRemovalBlockedError(
                "On ne transfère pas l'Owner de l'église source.",
                details={"tenant_id": str(transfer.from_tenant_id)},
            )
        # Jamais le dernier responsable d'un groupe (sinon orphelin).
        for ra in source.list_group_leaders():
            if ra.group_id is None:
                continue
            active = await self._memberships.count_active_group_leaders(
                transfer.from_tenant_id, ra.group_id
            )
            if active <= 1:
                raise GroupLastLeaderRemovalBlockedError(
                    "Le transfert retirerait le dernier responsable d'un groupe.",
                    details={"group_id": str(ra.group_id)},
                )

    async def _settle_destination(
        self, transfer: MemberTransfer, actor_account_id: UUID, now
    ) -> None:
        dest = await self._memberships.get_active(transfer.account_id, transfer.to_tenant_id)
        if dest is None:
            # Compte global existant, pas encore membre ici → on ajoute une appartenance.
            await self._enrollment.add_membership(
                membership=Membership(
                    id=uuid4(),
                    account_id=transfer.account_id,
                    tenant_id=transfer.to_tenant_id,
                    status=MembershipStatus.CONFIRMED_MEMBER,
                    last_transition_at=now,
                    role_assignments=[],
                ),
                actor_account_id=actor_account_id,
            )
        elif dest.status is not MembershipStatus.CONFIRMED_MEMBER:
            # Elle y était déjà (partagée) → on officialise en confirmed_member.
            await self._transitions.apply_transition(
                membership_id=dest.id,
                new_status=MembershipStatus.CONFIRMED_MEMBER,
                previous_status=dest.status,
                transitioned_at=now,
            )


class _ResolveTransfer:
    """Base pour refuser (source) / annuler (destination) — résolution simple sans saga."""

    def __init__(
        self,
        transfers: MemberTransferRepository,
        access: AccessControl,
        *,
        clock,
    ) -> None:
        self._transfers = transfers
        self._access = access
        self._clock = clock

    async def _load_pending(self, transfer_id: UUID) -> MemberTransfer:
        transfer = await self._transfers.get(transfer_id)
        if transfer is None:
            raise TransferNotFoundError(
                "Transfert introuvable.", details={"transfer_id": str(transfer_id)}
            )
        return transfer


class DeclineTransfer(_ResolveTransfer):
    async def execute(self, *, actor_account_id: UUID, transfer_id: UUID) -> TransferDTO:
        transfer = await self._load_pending(transfer_id)
        # La source refuse : autorité sur le tenant source.
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=transfer.from_tenant_id,
            permission=Permission.TRANSFER_MEMBER,
        )
        transfer.decline(by_account_id=actor_account_id, now=self._clock())
        await self._transfers.save(transfer)
        return to_transfer_dto(transfer)


class CancelTransfer(_ResolveTransfer):
    async def execute(self, *, actor_account_id: UUID, transfer_id: UUID) -> TransferDTO:
        transfer = await self._load_pending(transfer_id)
        # La destination annule sa propre demande : autorité sur le tenant destination.
        await self._access.ensure(
            account_id=actor_account_id,
            tenant_id=transfer.to_tenant_id,
            permission=Permission.TRANSFER_MEMBER,
        )
        transfer.cancel(by_account_id=actor_account_id, now=self._clock())
        await self._transfers.save(transfer)
        return to_transfer_dto(transfer)
