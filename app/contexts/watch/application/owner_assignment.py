"""Étage 02bis — à qui ce cas revient. Résolu **avant** l'arbitrage, jamais dans l'interpreter.

Un interpreter est pur : il ne peut interroger ni l'annuaire, ni les rôles, ni la propriété de
l'église. Il sait pourtant, seul, *à quel titre* un cas doit être adressé — une demande de
rendez-vous déclinée est une dette de l'agenda, une annulation est une main tendue qui se retire
devant le pasteur, une absence est l'affaire de celui qui connaît la personne. Il renvoie donc un
`owner_kind`, et cet étage le change en identité.

**Pourquoi ici, et pas à la matérialisation.** Deux raisons, et la seconde est la vraie :

- l'arbitrage compte le plafond de débit **par propriétaire** ; s'il ne le connaît pas encore, il
  attribue tout le monde au même budget et le plafond ne pèse sur personne ;
- la reprojection construit sa propre matérialisation. Un propriétaire résolu à l'étage 04
  laisserait le rejeu réécrire des `NULL` — et la colonne est désormais NOT NULL.

**Pourquoi avant l'arbitrage, et pas après.** L'arbitrage peut fusionner une ouverture dans un cas
déjà ouvert : après lui, il est trop tard pour savoir à qui la nouvelle ouverture aurait été
adressée. Avant lui, la question est encore posée.

Ce que cet étage ne fait jamais : inventer un destinataire. Quand l'église n'a personne — pas même
de propriétaire, ce qui ne devrait pas exister — l'ouverture est **écartée**, et le trou est déjà
consigné par `ResolveSignalOwner` au niveau du tenant. Mieux vaut un cas non émis et un défaut
visible qu'un cas adressé à quelqu'un choisi au hasard.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from app.contexts.watch.application.referent_ports import PeopleDirectory
from app.contexts.watch.application.referent_resolution import ResolveSignalOwner
from app.contexts.watch.domain.effects import OpenCase, OwnerKind, ProposedEffect


class ResolveOwners:
    """Referme la question du destinataire sur chaque ouverture de cas proposée."""

    def __init__(self, owners: ResolveSignalOwner, people: PeopleDirectory) -> None:
        self._owners = owners
        self._people = people

    async def execute(
        self, effects: Sequence[ProposedEffect], *, tenant_id: UUID, at: datetime
    ) -> tuple[tuple[ProposedEffect, ...], tuple[tuple[ProposedEffect, str], ...]]:
        """Renvoie (les effets destinés, les ouvertures écartées avec leur motif)."""
        kept: list[ProposedEffect] = []
        dropped: list[tuple[ProposedEffect, str]] = []

        for effect in effects:
            if not isinstance(effect, OpenCase) or effect.owner_account_id is not None:
                kept.append(effect)
                continue

            owner = await self._resolve(effect, tenant_id=tenant_id, at=at)
            if owner is None:
                dropped.append((effect, "no_recipient"))
                continue
            kept.append(replace(effect, owner_account_id=owner))

        return tuple(kept), tuple(dropped)

    async def _resolve(
        self, effect: OpenCase, *, tenant_id: UUID, at: datetime
    ) -> UUID | None:
        """Le titre demandé, puis ses replis. Le référent est le défaut, jamais un rattrapage."""
        if effect.owner_kind is OwnerKind.AGENDA_KEEPER:
            direct = await self._people.agenda_keeper(tenant_id)
        elif effect.owner_kind is OwnerKind.PASTOR:
            direct = await self._people.pastor(tenant_id)
        else:
            direct = None

        if direct is not None:
            return direct

        # Le titre demandé n'existe pas dans cette église : on retombe sur la cascade, qui se
        # termine elle-même sur le propriétaire. On ne renvoie **jamais** un cas de rendez-vous
        # au responsable de cellule par ce chemin sans que ce soit la cascade qui l'ait décidé —
        # et si elle le décide, c'est qu'il n'y a ni agenda, ni pasteur, ni admin, ni propriétaire
        # au-dessus de lui.
        resolved = await self._owners.execute(
            person_id=effect.subject_id, tenant_id=tenant_id, at=at
        )
        return resolved.account_id if resolved is not None else None
