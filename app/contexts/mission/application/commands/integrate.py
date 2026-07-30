"""Use case **Intégrer** (M9-4) — le chercheur devient membre : la boucle missionnaire se ferme.

Le Seeker est le *frère digital du Visiteur* (M6-3) ; l'intégration **réutilise exactement** la
machinerie visiteur→membre (`ConvertVisitor`) : identité globale par téléphone (créée ou
réutilisée), appartenance en statut `invited` (le début du tunnel), inscription au roster de la
cellule pour un chercheur de groupe. Le missionnaire *déverse* dans le tunnel déjà bâti.

Différence avec le Visiteur : le Seeker n'est **pas supprimé** — il passe à `integrated` et garde le
lien vers le compte qu'il est devenu (le futur arbre d'attribution).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.membership import GroupMembership
from app.contexts.groups.domain.repositories import (
    GroupMembershipRepository,
    GroupRepository,
)
from app.contexts.iam.application.commands.admit_person import ADMISSION_STATUS, AdmitPerson
from app.contexts.iam.domain.enums import AccountCreationSource
from app.contexts.iam.domain.permissions import Permission
from app.contexts.mission.application.dtos import IntegrateSeekerResult
from app.contexts.mission.domain.enums import SeekerStatus
from app.contexts.mission.domain.errors import (
    SeekerNotFoundError,
    SeekerPhoneRequiredError,
)
from app.contexts.mission.domain.repositories import SeekerRepository
from app.contexts.watch.application.ports import SignalStore
from app.contexts.watch.domain.signal import SignalOutcome


class IntegrateSeeker:
    def __init__(
        self,
        seekers: SeekerRepository,
        admit: AdmitPerson,
        groups: GroupRepository,
        group_memberships: GroupMembershipRepository,
        access: GroupAccessPolicy,
        signals: SignalStore | None = None,
        *,
        clock,
    ) -> None:
        self._seekers = seekers
        self._admit = admit
        self._groups = groups
        self._group_memberships = group_memberships
        self._access = access
        self._signals = signals
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        seeker_id: UUID,
        phone: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> IntegrateSeekerResult:
        seeker = await self._seekers.get(seeker_id)
        if seeker is None:
            raise SeekerNotFoundError(
                "Chercheur introuvable.", details={"seeker_id": str(seeker_id)}
            )
        tenant_id = seeker.tenant_id

        # Enrôler est un acte **gouverné** (comme ConvertVisitor) : chercheur de groupe → autorité
        # d'enrôlement sur la cellule (+ inscription au roster) ; chercheur personnel → autorité
        # d'enrôlement église-entière (pas de cellule cible).
        group = None
        if seeker.inviter_group_id is not None:
            group = await load_group_in_tenant(self._groups, seeker.inviter_group_id, tenant_id)
            await self._access.ensure_can(
                actor_account_id=actor_account_id,
                group=group,
                permission=Permission.ENROLL_MEMBER,
            )
        else:
            await self._access.ensure_church_wide(
                actor_account_id=actor_account_id,
                tenant_id=tenant_id,
                permission=Permission.ENROLL_MEMBER,
            )

        phone = phone or seeker.phone
        if not phone:
            raise SeekerPhoneRequiredError(
                "Un téléphone est requis pour intégrer ce chercheur.",
                details={"seeker_id": str(seeker_id)},
            )

        now = self._clock()
        # **Un seul écrivain du statut de personne.** `mission` ne construit plus d'appartenance :
        # il demande à IAM d'admettre quelqu'un, et IAM décide du palier d'entrée.
        account_id, reused = await self._admit.execute(
            tenant_id=tenant_id,
            phone=phone,
            first_name=first_name or seeker.name,
            last_name=last_name,
            creation_source=AccountCreationSource.SELF_SERVICE,  # chercheur digital
            actor_account_id=actor_account_id,
            now=now,
        )

        # Roster : seulement pour un chercheur de groupe (tolérant : jamais de doublon).
        if group is not None and await self._group_memberships.get_active(
            account_id, group.id
        ) is None:
            await self._group_memberships.add(
                GroupMembership.join(
                    id=uuid4(),
                    group_id=group.id,
                    account_id=account_id,
                    tenant_id=tenant_id,
                    now=now,
                    joined_by_account_id=actor_account_id,
                )
            )

        # **Deux effets distincts**, et c'est exactement pourquoi une seule machine à états ne
        # suffisait pas : le statut de la personne a changé (IAM, ci-dessus), *et* le cas de
        # veille se ferme. `RESTORED` — la main tendue a été saisie, le lien tient.
        await self._close_case(seeker, actor_account_id, now)

        # Le Seeker garde la **provenance** : quel compte il est devenu, et quand. Ce n'est pas
        # un statut — c'est le pont vers l'arbre d'attribution, et lui seul le sait.
        seeker.integrated_account_id = account_id
        seeker.integrated_at = now
        await self._seekers.save(seeker)
        return IntegrateSeekerResult(
            account_id=account_id,
            tenant_id=tenant_id,
            group_id=group.id if group is not None else None,
            membership_status=ADMISSION_STATUS.value,
            reused_account=reused,
            seeker_status=SeekerStatus.INTEGRATED.value,  # dérivé, plus jamais stocké
        )

    async def _close_case(self, seeker, actor_account_id: UUID, now) -> None:
        """Le suivi de veille s'arrête ici — il a abouti.

        Sans cette fermeture, la personne intégrée resterait dans la file de son inviteur, et
        l'escalade finirait par remonter au pasteur un engagement « non tenu » sur quelqu'un qui
        est devenu membre. Le pire des faux positifs : celui qui punit une réussite."""
        if self._signals is None or seeker.person_account_id is None:
            return
        case = await self._signals.live_case_of(
            subject_id=seeker.person_account_id, tenant_id=seeker.tenant_id
        )
        if case is None:
            return
        case.close(
            outcome=SignalOutcome.RESTORED, at=now, closed_by_account_id=actor_account_id
        )
        await self._signals.save_case(case)
