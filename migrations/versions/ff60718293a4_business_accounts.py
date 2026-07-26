"""business accounts : le tier d'une personne (compte Business par carte prépayée Visa)

Le compte devient Business dès qu'une carte prépayée Visa y est enregistrée (non facturé). On ne
stocke jamais le numéro complet : marque, 4 derniers, expiration, jeton d'un futur PSP.

Revision ID: ff60718293a4
Revises: fe5f60718293
Create Date: 2026-07-18 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff60718293a4'
down_revision: Union[str, Sequence[str], None] = 'fe5f60718293'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("card_brand", sa.String(), nullable=True),
        sa.Column("card_last4", sa.String(), nullable=True),
        sa.Column("card_prepaid", sa.Boolean(), nullable=True),
        sa.Column("card_exp_month", sa.Integer(), nullable=True),
        sa.Column("card_exp_year", sa.Integer(), nullable=True),
        sa.Column("card_provider_token", sa.String(), nullable=True),
        sa.Column("card_added_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_business_account"),
    )


def downgrade() -> None:
    op.drop_table("business_accounts")
