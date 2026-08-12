"""Ce que le pasteur a écarté — la moitié du dialogue qui ne se stockait nulle part

Urim gardait ce qui avait été choisi et rien de ce qui avait été décliné. Le moteur rejoue à
chaque lecture : sans cette table, il repropose à chaque tour ce qu'on vient de repousser.

Un refus est une **décision**, pas un raisonnement — il entre donc dans la doctrine de stockage
sans qu'il faille l'assouplir.

Revision ID: a7b8c9d2e3f4
Revises: f6a7b8c9d2e3
"""

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d2e3f4"
down_revision = "f6a7b8c9d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urim_preparation_dismissal",
        sa.Column("preparation_id", sa.Uuid(), nullable=False),
        sa.Column("stage_code", sa.String(), nullable=False),
        sa.Column("option_code", sa.String(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["preparation_id"], ["urim_preparation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("preparation_id", "stage_code", "option_code"),
    )


def downgrade() -> None:
    op.drop_table("urim_preparation_dismissal")
