"""`church_leader` — le responsable d'église (ou d'annexe), M0 §4.1.

« Un `group_leader` à l'échelle de l'église » : il **conduit et opère**, il ne **gouverne pas**.
Trois frontières le définissent, et chacune a son test :

- ≠ `owner` — il n'a pas les clés (la propriété n'est pas un rôle) ;
- ≠ `group_leader` — sa portée est le tenant entier, pas un groupe ;
- ≠ `admin` — l'écart tient exactement aux verbes de gouvernance.

Additif : `role_assignments.role` est une chaîne — **aucune migration**.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.domain.entities import GROUP_SCOPED_ROLES, RoleAssignment
from app.contexts.iam.domain.enums import RoleCode
from app.contexts.iam.domain.permissions import ROLE_PERMISSIONS, Permission, permissions_for
from app.contexts.iam.domain.role_authority import ROLE_AUTHORITY

_OPERATIONNEL = {
    Permission.VIEW_MEMBER_DIRECTORY,
    Permission.VIEW_PASTORAL_ALERTS,
    Permission.RECORD_ATTENDANCE,
    Permission.QUALIFY_ABSENCE,
    Permission.ENROLL_MEMBER,
    Permission.PUBLISH_ANNOUNCEMENT,
    Permission.MANAGE_GROUP,
}

_GOUVERNANCE = {
    Permission.MANAGE_STAFF,
    Permission.MANAGE_TEAM,
    Permission.MANAGE_MEMBERSHIP,
    Permission.CLOSE_MEMBERSHIP,
    Permission.TRANSFER_MEMBER,
}


def test_il_conduit_et_opere():
    assert permissions_for(RoleCode.CHURCH_LEADER) == frozenset(_OPERATIONNEL)


@pytest.mark.parametrize("verbe", sorted(_GOUVERNANCE, key=str))
def test_il_ne_gouverne_pas(verbe: Permission):
    """Nommer, faire progresser un statut, clôturer, transférer : jamais lui."""
    assert verbe not in permissions_for(RoleCode.CHURCH_LEADER)


def test_l_ecart_avec_l_admin_est_exactement_la_gouvernance():
    """Ce que l'Admin a en plus, ce sont les verbes de gouvernance — et rien d'autre
    d'opérationnel qui manquerait au responsable d'église."""
    admin = permissions_for(RoleCode.ADMIN)
    leader = permissions_for(RoleCode.CHURCH_LEADER)
    assert _GOUVERNANCE & admin <= admin - leader  # l'admin gouverne, lui non
    # Réciproquement, le responsable d'église est plus proche du terrain que l'Admin :
    assert Permission.RECORD_ATTENDANCE in leader - admin
    assert Permission.QUALIFY_ABSENCE in leader - admin


def test_sa_portee_est_l_eglise_entiere_pas_un_groupe():
    """≠ `group_leader` : aucune attribution ne le borne à un `group_id`."""
    assert RoleCode.CHURCH_LEADER not in GROUP_SCOPED_ROLES
    # Il se pose avec group_id=None (là où group_leader lèverait `RoleRequiresGroupError`)…
    assignment = RoleAssignment(
        id=uuid4(),
        role=RoleCode.CHURCH_LEADER,
        group_id=None,
        assigned_at=datetime(2026, 8, 3, tzinfo=UTC),
        assigned_by_account_id=uuid4(),
    )
    # …et il couvre n'importe quelle ressource du tenant, groupe compris.
    assert assignment.covers(group_id=None)
    assert assignment.covers(group_id=uuid4())


def test_l_owner_seul_le_nomme():
    """Il porte l'église entière : sa nomination est un acte d'état-major, comme la
    secrétaire et le trésorier — pas un geste délégable à un Admin."""
    assert ROLE_AUTHORITY[RoleCode.CHURCH_LEADER] is Permission.MANAGE_STAFF


def test_il_ne_touche_pas_a_l_argent():
    """La séparation ordonnateur / comptable ne le concerne pas."""
    granted = permissions_for(RoleCode.CHURCH_LEADER)
    for verbe in (
        Permission.LAUNCH_COLLECTION,
        Permission.VIEW_CONTRIBUTIONS,
        Permission.RECORD_CASH,
    ):
        assert verbe not in granted


def test_il_est_bien_dans_la_matrice():
    """Un rôle déclaré sans entrée de permissions serait muet — le piège classique."""
    assert RoleCode.CHURCH_LEADER in ROLE_PERMISSIONS
    assert permissions_for(RoleCode.CHURCH_LEADER)
