"""onboarding_profile_fields : parité des champs Church-OS dans la demande d'onboarding

Le brouillon d'onboarding porte désormais les mêmes champs M0 §2.2 que le
provisionnement direct (logo, contact, régional, operates_annexes) — ils survivent
de `submit` à `approve` (matérialisation).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-23 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("onboarding_requests", sa.Column("logo_url", sa.String(), nullable=True))
    op.add_column(
        "onboarding_requests", sa.Column("short_description", sa.String(), nullable=True)
    )
    op.add_column("onboarding_requests", sa.Column("contact_name", sa.String(), nullable=True))
    op.add_column("onboarding_requests", sa.Column("contact_phone", sa.String(), nullable=True))
    op.add_column(
        "onboarding_requests",
        sa.Column("timezone", sa.String(), nullable=False, server_default="Africa/Abidjan"),
    )
    op.add_column(
        "onboarding_requests",
        sa.Column("language", sa.String(), nullable=False, server_default="fr"),
    )
    op.add_column(
        "onboarding_requests",
        sa.Column("currency", sa.String(), nullable=False, server_default="XOF"),
    )
    op.add_column(
        "onboarding_requests",
        sa.Column(
            "operates_annexes", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade() -> None:
    for col in (
        "operates_annexes",
        "currency",
        "language",
        "timezone",
        "contact_phone",
        "contact_name",
        "short_description",
        "logo_url",
    ):
        op.drop_column("onboarding_requests", col)
