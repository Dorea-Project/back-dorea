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
from uuid import UUID, uuid4

from app.contexts.watch.application.ports import NeutralizationStore
from app.contexts.watch.application.referent_ports import (
    CoverageGapStore,
    GroupDirectory,
    GroupTypePolicyRepository,
    InviterDirectory,
    PeopleDirectory,
    PrimaryGroupOverrideRepository,
    ReferentHistoryRepository,
    ReferentOverrideRepository,
)
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import CoverageGap, CoverageScope
from app.contexts.watch.domain.referent import (
    MembershipCandidate,
    Referent,
    ReferentChangeCause,
    ReferentHistoryEntry,
    ReferentOrigin,
    gap_duration,
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
    stocké avec le signal.

    Quand aucun échelon n'existe, on préfère ne rien émettre qu'inventer un destinataire. Mais
    ce refus est **consigné en défaut de couverture** : une église sans admin ni pasteur
    détecterait tout et n'émettrait rien, et son écran vide dirait « tout va bien » alors qu'il
    dit « personne n'est configuré ». C'est exactement le faux silence que le produit existe
    pour empêcher.
    """

    def __init__(
        self,
        referents: ResolveReferent,
        people: PeopleDirectory,
        gaps: CoverageGapStore | None = None,
        *,
        id_factory=uuid4,
    ) -> None:
        self._referents = referents
        self._people = people
        self._gaps = gaps
        self._new_id = id_factory

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
        reason = (
            "Cette personne n'appartient à aucun groupe de suivi."
            if primary is None
            else "Ce groupe n'a pas de responsable actif."
        )
        fallback = await self._people.church_admin(tenant_id) or await self._people.pastor(
            tenant_id
        )

        if fallback is None:
            await self._record_no_recipient(tenant_id, at)
            return None
        return SignalOwner(fallback, escalation_reason=reason)

    async def _record_no_recipient(self, tenant_id: UUID, at: datetime) -> None:
        """Le défaut porte sur l'**église**, pas sur la personne : ce n'est pas elle qui manque."""
        if self._gaps is None:
            return
        await self._gaps.record_once(
            CoverageGapRecord(
                id=self._new_id(),
                tenant_id=tenant_id,
                scope=CoverageScope.TENANT,
                gap=CoverageGap.NO_RECIPIENT,
                reason="Aucun destinataire configuré : ni admin, ni pasteur.",
                observed_at=at,
            )
        )


class MeasureReferentGap:
    """Depuis combien de temps cette personne n'est sous le regard de personne.

    Compose la résolution et l'historique : s'il y a un référent, il n'y a pas de trou ; sinon
    le trou court depuis la dernière observation — ou, si personne ne l'a **jamais** connue,
    depuis son adhésion."""

    def __init__(
        self,
        referents: ResolveReferent,
        history: ReferentHistoryRepository,
        people: PeopleDirectory,
    ) -> None:
        self._referents = referents
        self._history = history
        self._people = people

    async def execute(self, *, person_id: UUID, tenant_id: UUID, at: datetime):
        referent = await self._referents.execute(
            person_id=person_id, tenant_id=tenant_id, at=at
        )
        if referent is not None:
            return None

        entry = await self._history.last_for(person_id, tenant_id)
        member_since = await self._people.member_since(person_id, tenant_id)
        return gap_duration(entry, at, member_since=member_since)


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
