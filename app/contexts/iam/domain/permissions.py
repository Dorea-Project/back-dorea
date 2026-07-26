"""Permissions et matrice rôle → permissions (RBAC borné par la propriété).

> « Un acteur peut faire A **si** un rôle accorde A **ET** que la ressource
> tombe dans sa portée. Le rôle donne le verbe. La propriété donne le
> périmètre. » (spec métier §5.6)

`Permission` = le **verbe** (indépendant de toute ressource). La **portée** est
vérifiée séparément par `RoleAssignment.covers()` / `AuthorizationService`.

⚠️ Matrice **initiale et extensible** : on l'enrichit au fil des modules (M6/M7/
M8). Elle reflète les descriptions de rôles de la spec §5.6 (pasteur = lecture
seule, responsable = portée groupe, admin = gestion).
"""

from enum import StrEnum

from app.contexts.iam.domain.enums import RoleCode


class Permission(StrEnum):
    VIEW_MEMBER_DIRECTORY = "view_member_directory"
    VIEW_PASTORAL_ALERTS = "view_pastoral_alerts"
    MANAGE_STAFF = "manage_staff"  # enrôler Pasteur/Admin (Owner seul, §5.3/§5.6)
    MANAGE_TEAM = "manage_team"  # enrôler responsable/accueil/intégration (Admin, §5.3/§5.6)
    MANAGE_MEMBERSHIP = "manage_membership"  # transitions de statut (admin/intégration)
    CLOSE_MEMBERSHIP = "close_membership"  # rétrogradation/clôture (Admin seul, §5.5)
    TRANSFER_MEMBER = "transfer_member"  # transfert entre églises (poignée de main, Admin/Owner)
    ENROLL_MEMBER = "enroll_member"  # enrôler un fidèle ordinaire (invited) — respo/accueil
    MANAGE_GROUP = "manage_group"  # portée groupe (M4)
    RECORD_ATTENDANCE = "record_attendance"  # M6
    QUALIFY_ABSENCE = "qualify_absence"  # M7
    PUBLISH_ANNOUNCEMENT = "publish_announcement"  # M8
    MANAGE_APPOINTMENTS = "manage_appointments"  # garder l'agenda du pasteur (RDV)
    PUBLISH_SERMON = "publish_sermon"  # déposer/approuver/publier un sermon (le pasteur)


ROLE_PERMISSIONS: dict[RoleCode, frozenset[Permission]] = {
    # NB : l'Owner n'est PAS ici — la propriété est un 1ᵉʳ étage d'autorisation
    # (AccessControl), au-dessus du RBAC des rôles.
    # Admin / Gestionnaire : gestion église/annexe.
    RoleCode.ADMIN: frozenset(
        {
            Permission.VIEW_MEMBER_DIRECTORY,
            Permission.VIEW_PASTORAL_ALERTS,
            Permission.MANAGE_TEAM,  # enrôle responsable/accueil/intégration (§5.6)
            Permission.MANAGE_MEMBERSHIP,
            Permission.CLOSE_MEMBERSHIP,  # rétrogradation/clôture — Admin seul (§5.5)
            Permission.TRANSFER_MEMBER,  # transfert entre églises (les deux côtés)
            Permission.MANAGE_GROUP,
            Permission.ENROLL_MEMBER,
            Permission.PUBLISH_ANNOUNCEMENT,
            Permission.MANAGE_APPOINTMENTS,  # gouvernance : peut aussi tenir l'agenda
            Permission.PUBLISH_SERMON,  # gouvernance : peut aussi déposer/publier un sermon
        }
    ),
    # Pasteur : LECTURE SEULE (spec §5.6) — **sauf son agenda de rendez-vous** et **ses sermons**,
    # ses deux actes d'écriture propres (décisions produit).
    RoleCode.PASTOR: frozenset(
        {
            Permission.VIEW_MEMBER_DIRECTORY,
            Permission.VIEW_PASTORAL_ALERTS,
            Permission.MANAGE_APPOINTMENTS,
            Permission.PUBLISH_SERMON,
        }
    ),
    # Secrétaire : « les affaires du pasteur ». Le pasteur étant en lecture seule, elle est **ses
    # mains** — sa voix (annoncer au nom de l'église) et ses yeux (le carnet, l'agenda des visites).
    # Elle **n'est pas** un gouvernant : ni nommer, ni clôturer, ni transférer, ni gérer.
    RoleCode.SECRETARY: frozenset(
        {
            Permission.VIEW_MEMBER_DIRECTORY,
            Permission.VIEW_PASTORAL_ALERTS,  # organise les visites (info pastorale sensible)
            Permission.PUBLISH_ANNOUNCEMENT,  # non scopée → porte jusqu'à l'église entière
            Permission.MANAGE_APPOINTMENTS,  # garde l'agenda du pasteur (ses mains)
        }
    ),
    # Responsable de groupe : opérations de portée groupe (1 à 6 par groupe).
    RoleCode.GROUP_LEADER: frozenset(
        {
            Permission.RECORD_ATTENDANCE,
            Permission.QUALIFY_ABSENCE,
            Permission.PUBLISH_ANNOUNCEMENT,
            Permission.MANAGE_GROUP,
            Permission.ENROLL_MEMBER,  # enregistre les membres de son groupe (§5.3)
            Permission.VIEW_PASTORAL_ALERTS,
        }
    ),
    # Responsable-en-formation (« Timothée », M4 §5) : aide à animer la cellule, SANS
    # gouvernance (ni MANAGE_GROUP ni ENROLL) — promu GROUP_LEADER à la multiplication (G-3).
    RoleCode.LEADER_IN_TRAINING: frozenset(
        {
            Permission.VIEW_MEMBER_DIRECTORY,
            Permission.VIEW_PASTORAL_ALERTS,
            Permission.RECORD_ATTENDANCE,
        }
    ),
    # Accueil : suivi des visiteurs — les enregistre en présentiel (§5.6).
    RoleCode.WELCOME_TEAM: frozenset(
        {Permission.VIEW_MEMBER_DIRECTORY, Permission.ENROLL_MEMBER}
    ),
    # Intégration : fait progresser les statuts (Nouveau → Membre confirmé).
    RoleCode.INTEGRATION_TEAM: frozenset(
        {Permission.VIEW_MEMBER_DIRECTORY, Permission.MANAGE_MEMBERSHIP}
    ),
    # Superviseur réseau : lecture agrégée (dashboard dénomination).
    RoleCode.NETWORK_SUPERVISOR: frozenset({Permission.VIEW_MEMBER_DIRECTORY}),
}


def permissions_for(role: RoleCode) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())
