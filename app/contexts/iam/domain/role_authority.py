"""Politique d'autorité par rôle (§5.3/§5.6) — partagée par enrôlement et révocation.

Qui peut **attribuer/retirer** quel rôle : Owner pour l'état-major, Admin pour l'équipe.
`owner` et `network_supervisor` ne passent pas par cette voie (genèse/succession Plateforme).
"""

from app.contexts.iam.domain.enums import RoleCode
from app.contexts.iam.domain.permissions import Permission

ROLE_AUTHORITY: dict[RoleCode, Permission] = {
    RoleCode.PASTOR: Permission.MANAGE_STAFF,
    # La secrétaire parle au nom de l'église entière : sa nomination reste un acte d'état-major
    # (Owner), jamais un geste opérationnel délégable à n'importe quel Admin.
    RoleCode.SECRETARY: Permission.MANAGE_STAFF,
    RoleCode.ADMIN: Permission.MANAGE_STAFF,
    # Le trésorier voit le détail nominatif de l'argent : sa nomination est un acte
    # d'état-major (Owner), jamais un geste opérationnel délégable à un Admin.
    RoleCode.TREASURER: Permission.MANAGE_STAFF,
    # Le responsable d'église porte l'église entière (portée non scopée) : comme la
    # secrétaire et le trésorier, sa nomination est un acte d'état-major (Owner), pas
    # un geste opérationnel délégable à un Admin.
    RoleCode.CHURCH_LEADER: Permission.MANAGE_STAFF,
    RoleCode.GROUP_LEADER: Permission.MANAGE_TEAM,
    RoleCode.LEADER_IN_TRAINING: Permission.MANAGE_TEAM,
    RoleCode.WELCOME_TEAM: Permission.MANAGE_TEAM,
    RoleCode.INTEGRATION_TEAM: Permission.MANAGE_TEAM,
}
