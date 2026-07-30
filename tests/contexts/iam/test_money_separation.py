"""La séparation de l'ordonnateur et du comptable — et l'argent tenu hors de la veille.

Deux garde-fous posés **avant** d'écrire une seule ligne du module Collectes, parce qu'ils sont
gratuits maintenant et très chers après.

Le scénario que le premier empêche est le plus corrosif du module : si celui qui lance une
collecte en voit le détail nominatif, alors le pasteur sait qui a donné quoi. Il ne l'a pas
demandé — l'information arrive parce qu'il a créé la collecte, et elle s'installe dans une
relation pastorale sans que personne ne l'ait voulu.
"""

from app.contexts.iam.domain.enums import RoleCode
from app.contexts.iam.domain.permissions import (
    ROLE_PERMISSIONS,
    SEPARATED_PERMISSIONS,
    Permission,
)
from app.contexts.iam.domain.role_authority import ROLE_AUTHORITY
from app.contexts.watch.domain.facts import FactKind, forbidden_reason

# --- Lancer n'est pas voir --------------------------------------------------------------------


def test_no_role_both_launches_and_sees():
    """**Jamais deux sur le même rôle par défaut.**

    Le cumul reste possible dans une petite église où le pasteur est aussi trésorier — mais par
    décision explicite et journalisée, jamais par défaut de configuration. Rien dans la matrice
    ne doit l'accorder tout seul."""
    for left, right in SEPARATED_PERMISSIONS:
        for role, granted in ROLE_PERMISSIONS.items():
            assert not ({left, right} <= granted), f"{role.value} cumule {left} et {right}"


def test_the_pastor_launches_and_never_sees_the_detail():
    granted = ROLE_PERMISSIONS[RoleCode.PASTOR]
    assert Permission.LAUNCH_COLLECTION in granted
    assert Permission.VIEW_CONTRIBUTIONS not in granted
    assert Permission.RECORD_CASH not in granted


def test_the_treasurer_sees_and_never_launches():
    granted = ROLE_PERMISSIONS[RoleCode.TREASURER]
    assert granted == frozenset(
        {Permission.VIEW_CONTRIBUTIONS, Permission.RECORD_CASH}
    )


def test_the_treasurer_gets_no_pastoral_access_by_the_back_door():
    """Comptabilité, pas curiosité. Un rôle financier n'ouvre aucune porte sur les personnes."""
    granted = ROLE_PERMISSIONS[RoleCode.TREASURER]
    for pastoral in (
        Permission.VIEW_MEMBER_DIRECTORY,
        Permission.VIEW_PASTORAL_ALERTS,
        Permission.QUALIFY_ABSENCE,
        Permission.MANAGE_APPOINTMENTS,
    ):
        assert pastoral not in granted, pastoral


def test_naming_the_treasurer_is_a_staff_decision():
    """Il voit le détail nominatif de l'argent : sa nomination n'est pas délégable à un Admin."""
    assert ROLE_AUTHORITY[RoleCode.TREASURER] is Permission.MANAGE_STAFF


def test_no_role_can_see_contributions_except_the_treasurer():
    holders = {
        role for role, granted in ROLE_PERMISSIONS.items()
        if Permission.VIEW_CONTRIBUTIONS in granted
    }
    assert holders == {RoleCode.TREASURER}


# --- L'argent n'entre pas dans la veille ---------------------------------------------------------


def test_the_ledger_already_refuses_every_financial_word():
    """L'invariant « aucune donnée financière n'entre dans le moteur de veille » n'est **pas** à
    construire : le grillage du ledger le tient déjà, et il le tiendra pour les Collectes.

    Ce test le fixe avant que le module existe — le jour où quelqu'un voudra un
    `CONTRIBUTION_RECEIVED` « juste pour la progression », l'enregistrement de la source échouera
    au démarrage de l'application, pas à la revue de code."""
    for word in (
        "contribution_received",
        "donation_made",
        "tithe_paid",
        "offering_collected",
        "payment_succeeded",
        "pledge_signed",
        "amount_collected",
        "fee_charged",
    ):
        assert forbidden_reason(word) == "financier", word


def test_no_existing_fact_kind_carries_money():
    """Le vocabulaire actuel est propre — et doit le rester."""
    for kind in FactKind:
        assert forbidden_reason(kind.value) is None, kind
