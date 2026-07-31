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
    # **Parler au nom d'un corps.** Diffuser au-delà de son église est un acte institutionnel :
    # c'est l'église qui s'adresse à un corps plus large. Le compte Business est le droit de
    # **payer** ; celui-ci est le droit de **parler**. Les deux sont exigés, et ils ne portent
    # pas sur le même sujet — l'un sur une personne, l'autre sur une institution.
    #
    # L'argument à donner au pasteur n'est pas bureaucratique : *si un de tes membres diffuse
    # une bêtise à toute la dénomination, c'est ton église qu'on blâmera, pas lui.*
    BROADCAST_WIDER = "broadcast_wider"
    # --- Collectes : **lancer n'est pas voir** -------------------------------------------
    #
    # Si celui qui lance une collecte en voit le détail nominatif, alors le pasteur sait qui
    # a donné quoi. Il ne l'a pas demandé : l'information arrive parce qu'il a créé la
    # collecte, et elle s'installe dans une relation pastorale sans que personne ne l'ait
    # voulu. C'est le scénario le plus corrosif de ce module — d'où trois permissions
    # distinctes, et jamais deux sur le même rôle par défaut.
    LAUNCH_COLLECTION = "launch_collection"  # ordonnateur : le pasteur, l'owner
    VIEW_CONTRIBUTIONS = "view_contributions"  # comptable : le trésorier, lui seul
    RECORD_CASH = "record_cash"  # saisir les espèces — le seul vrai anonyme


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
            Permission.BROADCAST_WIDER,  # engage l'institution : la gouvernance le peut
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
            Permission.BROADCAST_WIDER,  # c'est sa voix qui engage l'église au-dehors
            # Il lance la collecte. Il n'en verra **jamais** le détail nominatif — seulement le
            # total et la progression.
            Permission.LAUNCH_COLLECTION,
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
    # Trésorier : la comptabilité, pas la curiosité. Il voit le détail nominatif des
    # contributions **et rien d'autre** — aucun accès pastoral, aucun annuaire.
    RoleCode.TREASURER: frozenset(
        {
            Permission.VIEW_CONTRIBUTIONS,
            Permission.RECORD_CASH,
        }
    ),
    RoleCode.NETWORK_SUPERVISOR: frozenset({Permission.VIEW_MEMBER_DIRECTORY}),
}


def permissions_for(role: RoleCode) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


# L'ordonnateur et le comptable ne se confondent pas. Cette séparation n'est pas une contrainte
# artificielle : c'est celle que la plupart des églises pratiquent déjà.
#
# Le cumul reste **possible** dans une petite église où le pasteur est aussi trésorier — mais par
# décision explicite et journalisée, jamais par défaut de configuration. C'est exactement ce que
# cette paire garantit : rien dans la matrice ne l'accorde tout seul.
SEPARATED_PERMISSIONS: tuple[tuple[Permission, Permission], ...] = (
    (Permission.LAUNCH_COLLECTION, Permission.VIEW_CONTRIBUTIONS),
)
