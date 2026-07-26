"""unique_account_email : unicité de l'e-mail de compte (login backoffice)

Le login backoffice se fait par e-mail : deux comptes ne peuvent le partager.
Index *partiel* (WHERE email IS NOT NULL) → les comptes tél-only (email NULL,
la majorité des membres mobiles) restent permis en nombre.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_accounts_email_not_null",
        "accounts",
        ["email"],
        unique=True,
        postgresql_where="email IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_accounts_email_not_null", table_name="accounts")
