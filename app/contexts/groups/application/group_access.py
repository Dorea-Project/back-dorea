"""Politique d'autorisation des Groupes — portée **sous-arbre** (M4 §4).

Reprend l'autorisation à deux étages (propriété, puis rôle borné par la portée), mais
la portée d'un rôle scopé couvre désormais **tout le sous-arbre** du groupe qu'il dirige
(résolu via le chemin matérialisé). C'est le contexte Groupes qui l'évalue, car c'est lui
qui détient l'arbre.

Qui peut créer (subsidiarité, §4) :
- Owner ou gestionnaire **église-entière** (`MANAGE_GROUP` non scopé = Admin) → partout + racine.
- Responsable **scopé** (`MANAGE_GROUP` sur un groupe G) → sous-groupes **dans le sous-arbre de G**
  (jamais de racine : créer un groupe de haut niveau est un acte église-entière).
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.groups.domain.aggregates import Group
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.iam.application.ports import OwnershipChecker
from app.contexts.iam.domain.permissions import Permission, permissions_for
from app.contexts.iam.domain.repositories import MembershipRepository


class GroupAccessPolicy:
    def __init__(self, ownership: OwnershipChecker, memberships: MembershipRepository) -> None:
        self._ownership = ownership
        self._memberships = memberships

    async def ensure_can_create(
        self, *, actor_account_id: UUID, tenant_id: UUID, parent: Group | None
    ) -> None:
        """Créer un groupe **sous** `parent` (ou racine si None)."""
        if await self._can_create(actor_account_id, tenant_id, parent):
            return
        raise UnauthorizedGroupActionError(
            "Droit insuffisant pour créer un groupe à cet emplacement.",
            details={
                "tenant_id": str(tenant_id),
                "parent_group_id": str(parent.id) if parent else None,
            },
        )

    async def ensure_can_manage(
        self, *, actor_account_id: UUID, group: Group
    ) -> None:
        """Agir **dans** `group` (membres, sous-groupes, animation) — portée = ce nœud."""
        is_owner, scoped = await self._resolve(actor_account_id, group.tenant_id)
        if is_owner or None in scoped:  # owner ou gestionnaire église-entière
            return
        if any(group.is_covered_by(g) for g in scoped if g is not None):
            return
        raise UnauthorizedGroupActionError(
            "Droit insuffisant pour gérer ce groupe.",
            details={"group_id": str(group.id)},
        )

    async def ensure_can_manage_structure(
        self, *, actor_account_id: UUID, group: Group
    ) -> None:
        """Agir **sur** `group` (le fermer, nommer/révoquer ses responsables pleins) —
        « on structure depuis au-dessus » : il faut couvrir le **parent** (G-5)."""
        is_owner, scoped = await self._resolve(actor_account_id, group.tenant_id)
        if is_owner or None in scoped:  # owner ou gestionnaire église-entière
            return
        if any(group.is_structure_covered_by(g) for g in scoped if g is not None):
            return
        raise UnauthorizedGroupActionError(
            "Droit insuffisant : un acte structurel exige l'autorité du parent.",
            details={"group_id": str(group.id)},
        )

    async def ensure_can(
        self, *, actor_account_id: UUID, group: Group, permission: Permission
    ) -> None:
        """Autorise une **permission scopée** sur `group` (sous-arbre) — ex. `RECORD_ATTENDANCE`.

        Générique : réutilisée par les contextes voisins (présence…) qui agissent dans un
        groupe avec un verbe autre que `MANAGE_GROUP`."""
        is_owner, scoped = await self._resolve(actor_account_id, group.tenant_id, permission)
        if is_owner or None in scoped:
            return
        if any(group.is_covered_by(g) for g in scoped if g is not None):
            return
        raise UnauthorizedGroupActionError(
            "Droit insuffisant dans ce groupe.",
            details={"group_id": str(group.id), "permission": permission.value},
        )

    async def ensure_church_wide(
        self, *, actor_account_id: UUID, tenant_id: UUID, permission: Permission
    ) -> None:
        """Exige une autorité **église-entière** pour `permission` (Owner ou rôle non scopé).

        Pour les vues qui couvrent toute l'église (liste de soin M7-2) — un responsable scopé
        passe, lui, par la vue de *sa* cellule."""
        is_owner, scoped = await self._resolve(actor_account_id, tenant_id, permission)
        if is_owner or None in scoped:
            return
        raise UnauthorizedGroupActionError(
            "Cette vue exige une autorité pastorale sur toute l'église.",
            details={"tenant_id": str(tenant_id), "permission": permission.value},
        )

    async def _can_create(
        self, actor_account_id: UUID, tenant_id: UUID, parent: Group | None
    ) -> bool:
        is_owner, scoped = await self._resolve(actor_account_id, tenant_id)
        if is_owner:
            return True
        if not scoped:
            return False
        # Gestionnaire église-entière (rôle non scopé, ex. Admin) → partout, racine comprise.
        if None in scoped:
            return True
        # Responsable scopé : jamais de racine ; sinon le parent doit tomber dans son sous-arbre.
        if parent is None:
            return False
        return any(parent.is_covered_by(g) for g in scoped if g is not None)

    async def _resolve(
        self,
        actor_account_id: UUID,
        tenant_id: UUID,
        permission: Permission = Permission.MANAGE_GROUP,
    ) -> tuple[bool, list[UUID | None]]:
        """Renvoie (is_owner, groupes scopés portant `permission`). None = portée église entière."""
        if await self._ownership.is_active_owner(actor_account_id, tenant_id):
            return True, []
        membership = await self._memberships.get_active(actor_account_id, tenant_id)
        if membership is None:
            return False, []
        scoped: list[UUID | None] = [
            ra.group_id
            for ra in membership.active_roles()
            if permission in permissions_for(ra.role)
        ]
        return False, scoped
