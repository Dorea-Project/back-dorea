"""Agrégat `Group` — nœud typé et récursif de l'arbre d'une église (M4).

Deux liens de parenté **distincts** (§2) :
- `parent_group_id` : appartenance structurelle (famille ⊂ Jeunesse ⊂ Église).
- `multiplied_from_id` : lignée (famille B ← famille A), cellule uniquement (crochet G-3).

Le **chemin matérialisé** `path` (`/{racine}/…/{self}/`) rend le contrôle d'accès par
sous-arbre trivial (§4) : « le groupe G couvre X ⇔ `/{G}/` ∈ `X.path` ».
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.groups.domain.enums import GroupStatus, GroupType


class Group(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        name: str,
        type: GroupType,
        path: str,
        parent_group_id: UUID | None,
        status: GroupStatus,
        created_at: datetime,
        created_by_account_id: UUID,
        multiplied_from_id: UUID | None = None,
        generation: int = 1,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.name = name
        self.type = type
        self.path = path
        self.parent_group_id = parent_group_id
        self.status = status
        self.created_at = created_at
        self.created_by_account_id = created_by_account_id
        self.multiplied_from_id = multiplied_from_id
        self.generation = generation  # G1 à la création ; +1 à chaque multiplication (§ lignée)

    @classmethod
    def create_root(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        name: str,
        type: GroupType,
        now: datetime,
        created_by_account_id: UUID,
    ) -> Group:
        """Groupe racine (haut de l'arbre d'une église) — acte église-entière (§4)."""
        return cls(
            id=id,
            tenant_id=tenant_id,
            name=name,
            type=type,
            path=_segment(id),
            parent_group_id=None,
            status=GroupStatus.ACTIVE,
            created_at=now,
            created_by_account_id=created_by_account_id,
        )

    @classmethod
    def create_child(
        cls,
        *,
        id: UUID,
        parent: Group,
        name: str,
        type: GroupType,
        now: datetime,
        created_by_account_id: UUID,
    ) -> Group:
        """Sous-groupe sous `parent` : hérite du tenant et prolonge le chemin (§2/§4)."""
        return cls(
            id=id,
            tenant_id=parent.tenant_id,
            name=name,
            type=type,
            path=parent.path + _segment(id).lstrip("/"),
            parent_group_id=parent.id,
            status=GroupStatus.ACTIVE,
            created_at=now,
            created_by_account_id=created_by_account_id,
        )

    def multiply(
        self,
        *,
        daughter_id: UUID,
        name: str,
        now: datetime,
        created_by_account_id: UUID,
    ) -> Group:
        """Enfante une cellule-fille (§ multiplication, G-3).

        La fille est une **sœur** (même parent structurel) reliée par `multiplied_from_id`,
        de génération +1. Seule une cellule se multiplie (garanti par l'appelant)."""
        return Group(
            id=daughter_id,
            tenant_id=self.tenant_id,
            name=name,
            type=GroupType.CELLULE,
            path=self._sibling_path(daughter_id),
            parent_group_id=self.parent_group_id,
            status=GroupStatus.ACTIVE,
            created_at=now,
            created_by_account_id=created_by_account_id,
            multiplied_from_id=self.id,
            generation=self.generation + 1,
        )

    def mark_promoted(self) -> None:
        """Le groupe est devenu une église autonome (émancipation, §8/G-4) → clôturé."""
        self.status = GroupStatus.CLOSED

    def rename(self, name: str) -> None:
        self.name = name

    def set_status(self, status: GroupStatus) -> None:
        """Bascule `active ↔ dormant` (G-5). La fermeture passe par `mark_closed`."""
        self.status = status

    def mark_closed(self) -> None:
        self.status = GroupStatus.CLOSED

    @property
    def is_promotable(self) -> bool:
        return self.status is not GroupStatus.CLOSED

    @property
    def is_closed(self) -> bool:
        return self.status is GroupStatus.CLOSED

    def is_covered_by(self, group_id: UUID) -> bool:
        """`group_id` est-il un ancêtre-ou-soi de ce nœud ? (portée sous-arbre, §4)."""
        return _segment(group_id) in self.path

    def is_structure_covered_by(self, group_id: UUID) -> bool:
        """`group_id` couvre-t-il le **parent** de ce nœud ? (autorité structurelle, G-5).

        « On structure depuis au-dessus » : agir SUR un nœud (le fermer, nommer ses
        responsables pleins) exige de couvrir son parent — pas le nœud lui-même."""
        return _segment(group_id) in self._parent_path()

    def _parent_path(self) -> str:
        """Chemin du parent structurel = mon chemin privé de mon dernier segment.
        (Racine → `/` ; aucun groupe scopé ne le couvre, seul Owner/Admin agit.)"""
        return self.path[: -len(f"{self.id}/")]

    def _sibling_path(self, new_id: UUID) -> str:
        """Chemin d'une sœur : même parent structurel + segment du nouveau nœud."""
        return f"{self._parent_path()}{new_id}/"


def _segment(group_id: UUID) -> str:
    """Segment de chemin délimité pour un id (`/{id}/`) — la délimitation rend
    la recherche de sous-chaîne sûre (les UUID sont de longueur fixe)."""
    return f"/{group_id}/"
