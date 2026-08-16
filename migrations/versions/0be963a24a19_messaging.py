"""messaging : accuses de reception + refus de diffusion (STOP)

Le sort d'un message envoye, et la liste de ceux qui ont dit stop.

`messaging_deliveries` ne porte **ni numero ni contenu** : `message_id` est notre
identifiant, transmis au fournisseur a l'envoi, et il suffit a repondre a la
seule question posee ici — « le code est-il arrive ? ». Garder les numeros en
ferait un annuaire des membres avec l'heure de leurs codes.

`messaging_opt_outs` porte le numero, lui, et ne peut pas s'en passer : c'est la
cle verifiee avant toute diffusion, et la preuve du refus.

Revision ID: 0be963a24a19
Revises: 647ed6d8ca53
Create Date: 2026-08-16 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0be963a24a19'
down_revision: Union[str, Sequence[str], None] = '647ed6d8ca53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "messaging_deliveries",
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_messaging_deliveries_provider",
        "messaging_deliveries",
        ["provider_message_id"],
    )

    op.create_table(
        "messaging_opt_outs",
        sa.Column("phone_number", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("keyword", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("phone_number"),
    )


def downgrade() -> None:
    op.drop_table("messaging_opt_outs")
    op.drop_index("ix_messaging_deliveries_provider", table_name="messaging_deliveries")
    op.drop_table("messaging_deliveries")
