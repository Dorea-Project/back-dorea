"""tenant_profile_fields : champs Church OS du Tenant (M0 §2.2)

slug (identifiant lisible liens/QR, unique partiel), branding (logo_url,
short_description), contact (contact_name, contact_phone), régional (timezone,
language, currency — FCFA=XOF défaut), operates_annexes (plan famille).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("slug", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("contact_name", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("contact_phone", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("logo_url", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("short_description", sa.String(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("timezone", sa.String(), nullable=False, server_default="Africa/Abidjan"),
    )
    op.add_column(
        "tenants", sa.Column("language", sa.String(), nullable=False, server_default="fr")
    )
    op.add_column(
        "tenants", sa.Column("currency", sa.String(), nullable=False, server_default="XOF")
    )
    op.add_column(
        "tenants",
        sa.Column(
            "operates_annexes", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.create_index(
        "uq_tenants_slug_not_null",
        "tenants",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenants_slug_not_null", table_name="tenants")
    for col in (
        "operates_annexes",
        "currency",
        "language",
        "timezone",
        "short_description",
        "logo_url",
        "contact_phone",
        "contact_name",
        "slug",
    ):
        op.drop_column("tenants", col)
