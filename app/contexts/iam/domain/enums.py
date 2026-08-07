"""Énumérations du domaine IAM.

⚠️ Les *valeurs* sont la source de vérité, partagée entre les deux surfaces
(backoffice + mobile) et la base (M1 §7). Elles sont **stables** : on peut en
ajouter, jamais les renommer après mise en production.
"""

from enum import StrEnum


class AccountCreationSource(StrEnum):
    """M1 §7.1 — origine de création d'un compte."""

    OWNER = "owner"
    WALK_IN_REGISTRATION = "walk_in_registration"  # ex-« accueil » (présentiel)
    SELF_SERVICE = "self_service"
    # Une capsule acceptée : quelqu'un a laissé son contact en retour d'une invitation.
    # L'origine compte — c'est elle qui dit « quelqu'un l'a amenée ».
    MISSION_CAPSULE = "mission_capsule"
    SYSTEM = "system"  # Phase 0 P0.1 — origine du compte système « Dorea Platform »


class AccountStatus(StrEnum):
    """M1 §7.2."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class MembershipStatus(StrEnum):
    """M1 §7.3 — chaîne de progression + statuts parallèle/sortie."""

    INVITED = "invited"
    VISITOR = "visitor"
    SYMPATHIZER = "sympathizer"
    NEWCOMER = "newcomer"
    CONFIRMED_MEMBER = "confirmed_member"
    EXTERNAL_PARTICIPANT = "external_participant"  # hors chaîne (spec métier §5.5)
    CLOSED = "closed"


class MembershipTransitionEvent(StrEnum):
    """M1 §7.8 — événements paramètres de `TransitionStatus` (journalisés, non stockés)."""

    BOOTSTRAP_OWNER = "bootstrap_owner"
    ENROLL_INVITED = "enroll_invited"
    FIRST_ATTENDANCE_RECORDED = "first_attendance_recorded"  # invited → visitor (auto, M6)
    QUALIFY_SYMPATHIZER = "qualify_sympathizer"  # visitor → sympathizer
    QUALIFY_NEWCOMER = "qualify_newcomer"  # sympathizer → newcomer
    CONFIRM_MEMBER = "confirm_member"  # newcomer → confirmed_member
    DEMOTE = "demote"
    CLOSE = "close"
    CREATE_EXTERNAL_PARTICIPANT = "create_external_participant"


class RoleCode(StrEnum):
    """M1 §7.4 — un rôle donne le *verbe* ; la portée donne le *périmètre*.

    ⚠️ `owner` n'est **pas** un rôle : la propriété (gouvernance) est une relation
    de premier rang (`tenant_ownerships`), vérifiée avant le RBAC. Voir `AccessControl`.
    """

    PASTOR = "pastor"
    SECRETARY = "secretary"  # les affaires du pasteur — sa voix et ses yeux, sans gouvernance
    ADMIN = "admin"
    # Le responsable de l'église (ou d'une annexe) : il la **conduit** sans en détenir les
    # clés (≠ owner) et sans se limiter à un groupe (≠ group_leader). M0 §4.1.
    CHURCH_LEADER = "church_leader"
    GROUP_LEADER = "group_leader"
    LEADER_IN_TRAINING = "leader_in_training"  # M4 §5 — « Timothée » (sans autorité)
    # Le comptable, distinct de l'ordonnateur. Ce n'est pas un rôle inventé pour le
    # logiciel : toute église en a un, et la séparation lancer/voir se pratique déjà.
    TREASURER = "treasurer"
    WELCOME_TEAM = "welcome_team"  # ex-« accueil »
    INTEGRATION_TEAM = "integration_team"  # ex-« intégration »
    NETWORK_SUPERVISOR = "network_supervisor"


class RevocationReason(StrEnum):
    """M1 §7.6."""

    ADMIN_ACTION = "admin_action"
    DEMOTION_CASCADE = "demotion_cascade"


class MembershipClosureReason(StrEnum):
    """M1 §7.7."""

    CHANGED_CHURCH = "changed_church"
    INACTIVITY = "inactivity"
    MEMBER_REQUEST = "member_request"
    OTHER = "other"


class AbsenceReason(StrEnum):
    """Qualification d'absence active portée par l'appartenance (concept M7).

    Défini ici car `Membership.active_absence_reason` le référence (M1 §3) ;
    le contexte M7 en reste propriétaire fonctionnel.
    """

    SICK = "sick"  # Malade
    TRAVELING = "traveling"  # En voyage
    EXCUSED = "excused"  # Excusé
    CHANGED_CHURCH = "changed_church"  # A changé d'église
    NO_NEWS = "no_news"  # Sans nouvelles (seul état qui alerte)
