"""La cascade — résoudre le référent, et à défaut le propriétaire d'un cas.

Deux services, et il ne faut jamais les confondre :

- `ResolveReferent` — le lien durable. **Peut renvoyer NULL**, et ce NULL est la donnée la plus
  utile du module : « personne ne connaît cette personne ». C'est lui qui alimente la couverture
  et la carte du membre.
- `ResolveSignalOwner` — l'assignation opérationnelle. **Jamais NULL** : un cas sans destinataire
  est un cas que personne ne traite. Quand il faut escalader, le **motif est renvoyé pour être
  stocké avec le signal** — un pasteur qui reçoit un cas inexplicable l'ignore.

Si l'escalade remplissait le référent, la couverture vaudrait mécaniquement 100 % et la métrique
la plus vendable du produit ne mesurerait plus rien.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.contexts.watch.application.ports import NeutralizationStore
from app.contexts.watch.application.referent_ports import (
    GroupDirectory,
    GroupTypePolicyRepository,
    InviterDirectory,
    PeopleDirectory,
    PrimaryGroupOverrideRepository,
    ReferentHistoryRepository,
    ReferentOverrideRepository,
)
from app.contexts.watch.domain.referent import (
    MembershipCandidate,
    Referent,
    ReferentChangeCause,
    ReferentHistoryEntry,
    ReferentOrigin,
    pick_primary_group,
)


@dataclass(frozen=True)
class SignalOwner:
    """À qui revient le cas, et **pourquoi** si ce n'est pas au référent."""

    account_id: UUID
    escalation_reason: str | None = None

    @property
    def is_escalated(self) -> bool:
        return self.escalation_reason is not None


class ResolveReferent:
    def __init__(
        self,
        overrides: ReferentOverrideRepository,
        primary_overrides: PrimaryGroupOverrideRepository,
        policies: GroupTypePolicyRepository,
        groups: GroupDirectory,
        people: PeopleDirectory,
        inviters: InviterDirectory,
        exclusions: NeutralizationStore | None = None,
    ) -> None:
        self._overrides = overrides
        self._primary_overrides = primary_overrides
        self._policies = policies
        self._groups = groups
        self._people = people
        self._inviters = inviters
        self._exclusions = exclusions

    async def execute(
        self, *, person_id: UUID, tenant_id: UUID, at: datetime
    ) -> Referent | None:
        # Un défunt n'est pas un trou de couverture : il est hors du dénominateur.
        if self._exclusions is not None:
            excluded = await self._exclusions.excluded_subject_ids(tenant_id)
            if person_id in excluded:
                return None

        active = await self._overrides.active_for(person_id, tenant_id)
        by_origin = {o.origin: o for o in active}

        # A1 — MANUAL gagne toujours : c'est une décision humaine délibérée, et elle tient
        # jusqu'à ce qu'un humain la lève.
        manual = by_origin.get(ReferentOrigin.MANUAL)
        if manual is not None and await self._eligible(
            manual.referent_person_id, tenant_id, person_id
        ):
            return Referent(
                person_id, manual.referent_person_id, ReferentOrigin.MANUAL, manual.started_at
            )

        # A2 — GROUP_LEAD : pointeur **calculé**. Changer de responsable ne provoque aucune
        # écriture de référent, et l'histoire relationnelle reste attachée aux personnes.
        primary = await self.primary_group(person_id=person_id, tenant_id=tenant_id)
        if primary is not None:
            lead = await self._groups.active_leader_of(primary.group_id, tenant_id)
            if lead is not None and await self._eligible(lead, tenant_id, person_id):
                return Referent(
                    person_id, lead, ReferentOrigin.GROUP_LEAD, primary.joined_at
                )

        # A3 — INVITER, A4 — WELCOME_TEAM : les filets, dans cet ordre.
        for origin in (ReferentOrigin.INVITER, ReferentOrigin.WELCOME_TEAM):
            override = by_origin.get(origin)
            if override is not None and await self._eligible(
                override.referent_person_id, tenant_id, person_id
            ):
                return Referent(
                    person_id, override.referent_person_id, origin, override.started_at
                )

        if ReferentOrigin.INVITER not in by_origin:
            inviter = await self._inviters.inviter_of(person_id, tenant_id)
            if inviter is not None and await self._eligible(inviter, tenant_id, person_id):
                return Referent(person_id, inviter, ReferentOrigin.INVITER, at)

        # A5 — TROU. C'est une donnée, pas une erreur.
        return None

    async def primary_group(
        self, *, person_id: UUID, tenant_id: UUID
    ) -> MembershipCandidate | None:
        """Le groupe qui fonde le lien — **dérivé**, jamais un drapeau à maintenir."""
        candidates = await self._groups.active_memberships(person_id, tenant_id)
        policies = await self._policies.all_for(tenant_id)
        override = await self._primary_overrides.active_for(person_id, tenant_id)
        return pick_primary_group(
            candidates,
            policies,
            override_group_id=override.group_id if override is not None else None,
        )

    async def _eligible(self, candidate: UUID, tenant_id: UUID, person_id: UUID) -> bool:
        if candidate == person_id:
            return False  # nul n'est son propre référent
        return await self._people.is_eligible(candidate, tenant_id)


class ResolveSignalOwner:
    """À qui adresser un cas. **Jamais nul** — et le motif d'escalade est renvoyé pour être
    stocké avec le signal."""

    def __init__(self, referents: ResolveReferent, people: PeopleDirectory) -> None:
        self._referents = referents
        self._people = people

    async def execute(
        self, *, person_id: UUID, tenant_id: UUID, at: datetime
    ) -> SignalOwner | None:
        referent = await self._referents.execute(
            person_id=person_id, tenant_id=tenant_id, at=at
        )
        if referent is not None:
            return SignalOwner(referent.referent_person_id)

        primary = await self._referents.primary_group(
            person_id=person_id, tenant_id=tenant_id
        )
        admin = await self._people.church_admin(tenant_id)
        pastor = await self._people.pastor(tenant_id)

        if primary is None:
            reason = "Cette personne n'appartient à aucun groupe de suivi."
            fallback = admin or pastor
        else:
            reason = "Ce groupe n'a pas de responsable actif."
            fallback = admin or pastor

        if fallback is None:
            # Aucun échelon disponible : mieux vaut ne rien émettre qu'inventer un destinataire.
            return None
        return SignalOwner(fallback, escalation_reason=reason)


class ObserveReferentChange:
    """Écrit l'historique quand — et seulement quand — le lien a réellement bougé.

    Appelé sur changement de responsable, entrée/sortie de groupe, pose ou levée d'override,
    révocation de compte, décès. Sans cette observation, un trou n'est pas datable, et
    « sans référent » n'est pas actionnable."""

    def __init__(
        self,
        referents: ResolveReferent,
        history: ReferentHistoryRepository,
        *,
        id_factory,
    ) -> None:
        self._referents = referents
        self._history = history
        self._new_id = id_factory

    async def execute(
        self,
        *,
        person_id: UUID,
        tenant_id: UUID,
        at: datetime,
        cause: ReferentChangeCause,
    ) -> ReferentHistoryEntry | None:
        previous = await self._history.last_for(person_id, tenant_id)
        current = await self._referents.execute(
            person_id=person_id, tenant_id=tenant_id, at=at
        )
        current_id = current.referent_person_id if current is not None else None

        if previous is not None and previous.referent_person_id == current_id:
            return None  # rien n'a changé : on n'écrit pas de bruit
        if previous is None and current_id is None:
            return None

        entry = ReferentHistoryEntry(
            id=self._new_id(),
            tenant_id=tenant_id,
            person_id=person_id,
            referent_person_id=current_id,  # NULL = début d'un trou
            origin=current.origin if current is not None else None,
            observed_at=at,
            cause=cause,
        )
        await self._history.append(entry)
        return entry
