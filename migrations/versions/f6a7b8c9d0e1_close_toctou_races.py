"""close_toctou_races : les trois courses fermées par la base (DOREA-008/009/010)

Trois gardes applicatives qui lisaient « c'est libre » avant d'écrire. Sous concurrence,
deux requêtes lisaient toutes deux « libre ». Un index unique partiel rend la seconde
écriture **impossible** — et le handler `IntegrityError → 409 CONFLICT` la traduit en
réponse propre.

- 008 : une seule appartenance **active** par (compte, église) — les closes restent en nombre
- 009 : une seule rencontre **église-entière** par (église, type, horaire) — le culte du jour
        est créé en get-or-create par le compagnon (S-4)
- 010 : un pasteur **confirmé** une seule fois par créneau

Revision ID: f6a7b8c9d0e1
Revises: e4fd0c1d2e3f
Create Date: 2026-08-03 03:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: str | Sequence[str] | None = 'e4fd0c1d2e3f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # DOREA-008
    op.create_index(
        "uq_one_active_membership_per_account_tenant",
        "memberships",
        ["account_id", "tenant_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    # DOREA-009
    op.create_index(
        "uq_one_church_wide_gathering_per_slot",
        "gatherings",
        ["tenant_id", "type", "scheduled_at"],
        unique=True,
        postgresql_where=sa.text("group_id IS NULL"),
    )
    # DOREA-010
    op.create_index(
        "uq_one_confirmed_appointment_per_slot",
        "appointments",
        ["with_pastor_account_id", "scheduled_at"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'confirmed' AND with_pastor_account_id IS NOT NULL "
            "AND scheduled_at IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_one_confirmed_appointment_per_slot", table_name="appointments")
    op.drop_index("uq_one_church_wide_gathering_per_slot", table_name="gatherings")
    op.drop_index("uq_one_active_membership_per_account_tenant", table_name="memberships")
