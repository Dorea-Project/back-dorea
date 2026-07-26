"""Énumérations du domaine Groupes (M4 §1).

Les *valeurs* sont la source de vérité (partagées base + surfaces). Stables : on peut
en ajouter, jamais les renommer après mise en production.
"""

from enum import StrEnum


class GroupType(StrEnum):
    """M4 §1 — le type est une couche de règles (seule la cellule se multiplie)."""

    CELLULE = "cellule"  # soin pastoral, se multiplie (générations, santé)
    MINISTERE = "ministere"  # service / équipe (louange, accueil, enfants…)
    CLASSE = "classe"  # cohorte temporaire (préparation baptême…)


class GroupStatus(StrEnum):
    """M4 §1 — cycle de vie d'un groupe."""

    ACTIVE = "active"
    MULTIPLYING = "multiplying"  # cellule en cours de division (G-3)
    DORMANT = "dormant"
    CLOSED = "closed"
