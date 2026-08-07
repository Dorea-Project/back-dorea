"""Qui a le droit de préparer — le seul endroit d'Urim qui connaisse les permissions.

L'autorité est `PUBLISH_SERMON`, église entière : **c'est la même personne** que celle qui
déposera le sermon, à un autre moment de son travail. Urim prépare, Sermon publie (D-B).

La séparation posée par le quatrième mur (S29) est celle des **modèles** — une préparation
n'est pas un sermon, et aucune table ne les confond. Ce n'est pas celle des gens : inventer
une permission « préparer » distincte créerait une église où quelqu'un pourrait préparer un
sermon qu'il n'a pas le droit de prêcher, ce qui ne veut rien dire.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission


class GroupAccessPreacherAuthorization:
    """Implémente `PreacherAuthorization` en déléguant à la politique d'accès partagée."""

    def __init__(self, access: GroupAccessPolicy) -> None:
        self._access = access

    async def ensure_may_prepare(self, *, account_id: UUID, church_id: UUID) -> None:
        await self._access.ensure_church_wide(
            actor_account_id=account_id,
            tenant_id=church_id,
            permission=Permission.PUBLISH_SERMON,
        )
