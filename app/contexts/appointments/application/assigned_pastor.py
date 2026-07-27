"""Le **pasteur assigné** — dérivé à la lecture, jamais stocké.

Même nature que le référent, donc même mécanique : aucun champ `assigned_pastor_id` sur la
personne. Un changement de pasteur d'annexe rebascule tout le monde **sans une seule écriture**.

La cascade :

1. **Override manuel** — une décision humaine, stockée seulement parce qu'elle existe ;
2. **Dérivation** — personne → groupe primaire → le pasteur de sa branche. On réutilise le lien
   primaire du module Referent : la même personne ne peut pas avoir deux « groupes qui comptent »
   selon qu'on cherche un référent ou un pasteur ;
3. **Pasteur de l'église.**

Dans une église à un seul pasteur, la dérivation renvoie toujours le même — c'est correct, pas
dégradé. Le mécanisme sert quand l'église grandit, et il est là avant.

**La disponibilité est consultée à chaque étage.** Un pasteur absent n'est pas un pasteur qui
oublie : on le contourne tout de suite, sans faire attendre la demande le délai de relais.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.contexts.appointments.domain.repositories import PastorUnavailabilityRepository
from app.contexts.appointments.domain.unavailability import is_available
from app.contexts.watch.application.referent_ports import GroupDirectory, PeopleDirectory
from app.contexts.watch.application.referent_resolution import ResolveReferent


@dataclass(frozen=True)
class AssignedPastor:
    account_id: UUID
    origin: str  # manual | branch | church


class PastorOverrideDirectory:
    """Les désignations explicites de pasteur. Vide tant qu'aucune n'existe — et c'est normal."""

    async def active_for(self, person_id: UUID, tenant_id: UUID) -> UUID | None:
        return None


class ResolveAssignedPastor:
    def __init__(
        self,
        referents: ResolveReferent,
        groups: GroupDirectory,
        people: PeopleDirectory,
        unavailabilities: PastorUnavailabilityRepository,
        overrides: PastorOverrideDirectory | None = None,
    ) -> None:
        self._referents = referents
        self._groups = groups
        self._people = people
        self._unavailabilities = unavailabilities
        self._overrides = overrides or PastorOverrideDirectory()

    async def execute(
        self, *, person_id: UUID, tenant_id: UUID, at: datetime
    ) -> AssignedPastor | None:
        manual = await self._overrides.active_for(person_id, tenant_id)
        if manual is not None and await self._available(manual, tenant_id, at):
            return AssignedPastor(manual, "manual")

        # Le groupe primaire vient du module Referent : une seule notion de « groupe qui compte ».
        primary = await self._referents.primary_group(
            person_id=person_id, tenant_id=tenant_id
        )
        if primary is not None:
            branch_pastor = await self._groups.pastor_of_branch(primary.group_id, tenant_id)
            if branch_pastor is not None and await self._available(
                branch_pastor, tenant_id, at
            ):
                return AssignedPastor(branch_pastor, "branch")

        church_pastor = await self._people.pastor(tenant_id)
        if church_pastor is not None and await self._available(church_pastor, tenant_id, at):
            return AssignedPastor(church_pastor, "church")

        return None  # aucun pasteur disponible — le relais prend le relais (§3)

    async def _available(self, pastor: UUID, tenant_id: UUID, at: datetime) -> bool:
        declared = await self._unavailabilities.list_active_for(pastor, tenant_id)
        return is_available(declared, at)
