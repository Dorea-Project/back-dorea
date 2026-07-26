"""member_transfers table (transfert de membre entre églises — poignée de main)

Crée `member_transfers` : une demande gouvernée destination→source (pending / accepted /
declined / cancelled). Le Compte ne bouge jamais ; seule l'appartenance change de main.

Revision ID: e7d3f4a1b6c8
Revises: d0b5e2c74a19
Create Date: 2026-07-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7d3f4a1b6c8'
down_revision: Union[str, Sequence[str], None] = 'd0b5e2c74a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "member_transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("from_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("to_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("to_group_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requested_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
    )
    op.create_index(
        "ix_member_transfers_from_tenant", "member_transfers", ["from_tenant_id"]
    )
    op.create_index("ix_member_transfers_to_tenant", "member_transfers", ["to_tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_member_transfers_to_tenant", table_name="member_transfers")
    op.drop_index("ix_member_transfers_from_tenant", table_name="member_transfers")
    op.drop_table("member_transfers")
