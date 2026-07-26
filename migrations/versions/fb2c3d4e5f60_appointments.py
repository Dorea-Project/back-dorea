"""appointments : l'agenda du pasteur, gardé par la secrétaire (module Rendez-vous)

Un membre demande (sujet confidentiel, créneau souhaité) ; la secrétaire confirme un créneau,
décline avec un mot, ou le rendez-vous est honoré.

Revision ID: fb2c3d4e5f60
Revises: fa1b2c3d4e5f
Create Date: 2026-07-18 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb2c3d4e5f60'
down_revision: Union[str, Sequence[str], None] = 'fa1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        # Émetteur : membre (compte) OU walk-in au bureau (nom + tél, sans compte).
        sa.Column("requester_account_id", sa.Uuid(), nullable=True),
        sa.Column("requester_name", sa.String(), nullable=True),
        sa.Column("requester_phone", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False, server_default="other"),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("preferred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_appointments_requester", "appointments", ["requester_account_id", "tenant_id"]
    )
    op.create_index("ix_appointments_tenant_status", "appointments", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_appointments_tenant_status", table_name="appointments")
    op.drop_index("ix_appointments_requester", table_name="appointments")
    op.drop_table("appointments")
