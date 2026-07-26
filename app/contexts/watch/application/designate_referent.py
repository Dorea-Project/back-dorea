"""Désigner un référent — un geste **explicite**, jamais un effet de bord.

Traiter un signal ne crée pas de référent. Un appel ponctuel ne fait de personne un lien
durable, et si l'on confondait les deux, la couverture se remplirait toute seule sans que
personne n'ait rien décidé — la métrique cesserait de mesurer quoi que ce soit.

L'écran de résolution d'un cas *propose* l'action (« devenir référent », « désigner un
référent »), mais elle reste un tap séparé. Sans cette proposition, le trou remonte
indéfiniment sans jamais se combler ; avec elle, mais implicite, il se comble sur le papier
seulement.

Le sujet n'est **pas notifié** d'une désignation : il la découvre par sa carte de référent,
présentée comme une information — « voici qui t'accompagne » — et non comme une assignation.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.watch.application.referent_ports import (
    PeopleDirectory,
    ReferentHistoryRepository,
    ReferentOverrideRepository,
)
from app.contexts.watch.application.referent_resolution import (
    ObserveReferentChange,
    ResolveReferent,
)
from app.contexts.watch.domain.errors import IneligibleReferentError, SelfReferentError
from app.contexts.watch.domain.referent import (
    ReferentChangeCause,
    ReferentOrigin,
    ReferentOverride,
)


class DesignateReferent:
    def __init__(
        self,
        overrides: ReferentOverrideRepository,
        history: ReferentHistoryRepository,
        people: PeopleDirectory,
        referents: ResolveReferent,
        *,
        id_factory,
        clock,
    ) -> None:
        self._overrides = overrides
        self._history = history
        self._people = people
        self._referents = referents
        self._new_id = id_factory
        self._clock = clock

    async def execute(
        self,
        *,
        person_id: UUID,
        referent_person_id: UUID,
        tenant_id: UUID,
        by_account_id: UUID,
        origin: ReferentOrigin = ReferentOrigin.MANUAL,
    ) -> ReferentOverride:
        if referent_person_id == person_id:
            raise SelfReferentError("Nul n'est son propre référent.")
        if not await self._people.is_eligible(referent_person_id, tenant_id):
            raise IneligibleReferentError(
                "Ce compte ne peut pas être référent (inactif, clos, ou hors veille).",
                details={"referent_person_id": str(referent_person_id)},
            )

        now = self._clock()

        # Une désignation remplace la précédente de même origine — on ne laisse jamais deux
        # liens actifs se disputer la même personne.
        for existing in await self._overrides.active_for(person_id, tenant_id):
            if existing.origin is origin:
                existing.end(at=now, reason="replaced")
                await self._overrides.save(existing)

        override = ReferentOverride(
            id=self._new_id(),
            tenant_id=tenant_id,
            person_id=person_id,
            referent_person_id=referent_person_id,
            origin=origin,
            started_at=now,
            started_by_account_id=by_account_id,
        )
        await self._overrides.add(override)

        await ObserveReferentChange(
            self._referents, self._history, id_factory=self._new_id
        ).execute(
            person_id=person_id,
            tenant_id=tenant_id,
            at=now,
            cause=ReferentChangeCause.MANUAL_SET,
        )
        return override


class EndReferentDesignation:
    """Lever une désignation. Le lien redescend la cascade — ou devient un trou daté."""

    def __init__(
        self,
        overrides: ReferentOverrideRepository,
        history: ReferentHistoryRepository,
        referents: ResolveReferent,
        *,
        id_factory,
        clock,
    ) -> None:
        self._overrides = overrides
        self._history = history
        self._referents = referents
        self._new_id = id_factory
        self._clock = clock

    async def execute(
        self,
        *,
        person_id: UUID,
        tenant_id: UUID,
        origin: ReferentOrigin = ReferentOrigin.MANUAL,
        reason: str = "ended",
    ) -> None:
        now = self._clock()
        for existing in await self._overrides.active_for(person_id, tenant_id):
            if existing.origin is origin:
                existing.end(at=now, reason=reason)
                await self._overrides.save(existing)

        await ObserveReferentChange(
            self._referents, self._history, id_factory=self._new_id
        ).execute(
            person_id=person_id,
            tenant_id=tenant_id,
            at=now,
            cause=ReferentChangeCause.MANUAL_ENDED,
        )
