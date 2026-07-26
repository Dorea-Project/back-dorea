"""church_suspensions table (P1 — Fondation A : suspension église, cascade d'acquittement)

Période église (Noël, deuil national) qui acquitte en cascade toutes les occurrences du périmètre.
La cascade est calculée à la lecture — aucune ligne d'acquittement générée par groupe.

Revision ID: c3e4f5a6b7c8
Revises: b2d3e4f5a6b7
Create Date: 2026-07-25 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'b2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "church_suspensions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("from_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("declared_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_church_suspensions_tenant", "church_suspensions", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_church_suspensions_tenant", table_name="church_suspensions")
    op.drop_table("church_suspensions")
