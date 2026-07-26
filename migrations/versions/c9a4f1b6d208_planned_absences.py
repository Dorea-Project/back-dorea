"""planned_absences table (M6-2 — pré-déclaration d'absence)

Crée `planned_absences` : le membre annonce une période d'absence avec un tag (raison).
Le roster déduit l'« excusé » (rencontre dont la date tombe dans la période).

Revision ID: c9a4f1b6d208
Revises: b8f3e0a72c15
Create Date: 2026-07-16 09:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9a4f1b6d208'
down_revision: Union[str, Sequence[str], None] = 'b8f3e0a72c15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planned_absences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("from_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("declared_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_planned_absences_tenant", "planned_absences", ["tenant_id"])
    op.create_index("ix_planned_absences_account", "planned_absences", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_planned_absences_account", table_name="planned_absences")
    op.drop_index("ix_planned_absences_tenant", table_name="planned_absences")
    op.drop_table("planned_absences")
