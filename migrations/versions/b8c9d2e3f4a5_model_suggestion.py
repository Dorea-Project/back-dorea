"""Les suggestions du modèle sont gardées, pas redemandées

Sans cette table, le rejeu n'est pas un rejeu : c'est un recalcul qui se trouve d'accord.
`corpus_snapshot` garantit le déterminisme côté corpus ; rien ne le garantissait côté modèle, et
`mistral-small-latest` est un alias mouvant. Le jour où il bouge, une préparation d'hier rejoue
autrement, en silence, alors que la trace affirme le contraire.

Le coût vient en second : le bloc conviction partait à chaque rejeu — donc à chaque lecture
d'écran et à chaque refus — pour rendre mot pour mot ce qui venait d'être rendu.

Revision ID: b8c9d2e3f4a5
Revises: a7b8c9d2e3f4
"""

import sqlalchemy as sa
from alembic import op

revision = "b8c9d2e3f4a5"
down_revision = "a7b8c9d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urim_model_suggestion",
        sa.Column("preparation_id", sa.Uuid(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("axes", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("passages", sa.JSON(), nullable=False),
        sa.Column("suggested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["preparation_id"], ["urim_preparation.id"], ondelete="CASCADE"
        ),
        # `input_hash` est dans la clé : une préparation pose plusieurs questions (le chemin
        # conviction et le chemin impasse), et une seule ligne les faisait s'écraser.
        sa.PrimaryKeyConstraint("preparation_id", "input_hash"),
    )


def downgrade() -> None:
    op.drop_table("urim_model_suggestion")
