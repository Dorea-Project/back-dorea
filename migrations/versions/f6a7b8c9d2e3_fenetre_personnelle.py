"""La réservation d'étude sans église — le registre du quota personnel

Le plafond comptait par église. L'antichambre n'en a pas : le pasteur qui prépare seul n'avait
aucun sujet de comptage, donc aucune façon d'être plafonné ni de savoir ce qu'il a consommé.

**Aucune fenêtre d'usage personnelle n'est créée**, et c'est délibéré. `urim_usage_window`
porte un `metered_units` qu'aucun code n'a jamais incrémenté ; en ajouter un second pour les
comptes aurait dupliqué un compteur qui dérive au premier incrément perdu. Le registre est
`urim_study_reservation` : une réservation par texte, `metered_at` posé une fois, et le mois
s'obtient en additionnant des lignes qui existent.

L'index unique partiel porte `church_id`. Sous PostgreSQL `NULL <> NULL` : sans église il ne
contraint plus rien, et deux réservations personnelles du même auteur sur le même texte
passeraient toutes les deux — l'idempotence que cette table existe pour tenir tomberait
exactement là où elle compte le plus. D'où un **second** index, pour le cas sans église.

Revision ID: f6a7b8c9d2e3
Revises: e5f6a7b8c9d2
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d2e3"
down_revision = "e5f6a7b8c9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "urim_study_reservation", "church_id", existing_type=sa.Uuid(), nullable=True
    )
    op.create_index(
        "ix_urim_reservation_personnelle",
        "urim_study_reservation",
        ["author_id", "pericope_key"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL AND church_id IS NULL"),
        sqlite_where=sa.text("released_at IS NULL AND church_id IS NULL"),
    )
    # Le mois d'un auteur se lit en balayant ses réservations facturées : sans cet index,
    # le quota coûterait un parcours complet de la table à chaque ouverture.
    op.create_index(
        "ix_urim_reservation_quota",
        "urim_study_reservation",
        ["author_id", "metered_at"],
        postgresql_where=sa.text("church_id IS NULL AND metered_at IS NOT NULL"),
        sqlite_where=sa.text("church_id IS NULL AND metered_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_urim_reservation_quota", table_name="urim_study_reservation")
    op.drop_index("ix_urim_reservation_personnelle", table_name="urim_study_reservation")
    op.alter_column(
        "urim_study_reservation", "church_id", existing_type=sa.Uuid(), nullable=False
    )
