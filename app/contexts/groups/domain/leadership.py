"""Grades de leadership d'un groupe (M4 §5).

Grade **groupe** exposé par l'API, mappé en interne sur un rôle IAM scopé (le leadership
reste un rôle IAM pour que l'autorisation par sous-arbre le lise) :
- `leader` → `RoleCode.GROUP_LEADER` (autorité pleine, cap 6/nœud) ;
- `in_training` → `RoleCode.LEADER_IN_TRAINING` (« Timothée », sans gouvernance).
"""

from enum import StrEnum

from app.contexts.iam.domain.enums import RoleCode


class GroupLeadershipGrade(StrEnum):
    LEADER = "leader"
    IN_TRAINING = "in_training"

    def to_role(self) -> RoleCode:
        return (
            RoleCode.GROUP_LEADER
            if self is GroupLeadershipGrade.LEADER
            else RoleCode.LEADER_IN_TRAINING
        )
