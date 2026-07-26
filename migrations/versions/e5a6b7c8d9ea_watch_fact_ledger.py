"""moteur de veille : le ledger des faits (noyau fermé, bloc 1)

Le journal devient la source de vérité du moteur. Neutralisations et exclusions n'en sont plus
que des projections : on peut les effacer et rejouer le ledger pour les reconstruire à
l'identique.

`seq` est la clé primaire **et** l'ordre du rejeu — le seul ordre total dont on dispose. Les
dates ne suffisent pas : `recorded_at` peut être à égalité, `occurred_at` peut remonter le temps.

`announcement_subjects.applied_at` disparaît : c'était un état mutable qui portait l'idempotence
des effets. Sous ledger, l'idempotence vient de `fact_id` — et un marqueur « déjà appliqué »
empêcherait la reprojection.

Revision ID: e5a6b7c8d9ea
Revises: d4f5a6b7c8d9
Create Date: 2026-07-26 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a6b7c8d9ea'
down_revision: Union[str, Sequence[str], None] = 'd4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watch_fact_ledger",
        sa.Column("seq", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("subject_kind", sa.String(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("consent", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("seq"),
    )
    op.create_index("ix_watch_ledger_tenant_seq", "watch_fact_ledger", ["tenant_id", "seq"])
    op.create_index("ix_watch_ledger_subject", "watch_fact_ledger", ["tenant_id", "subject_id"])
    op.create_index("ix_watch_ledger_fact", "watch_fact_ledger", ["fact_id"], unique=True)

    op.drop_column("announcement_subjects", "applied_at")


def downgrade() -> None:
    op.add_column(
        "announcement_subjects",
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_index("ix_watch_ledger_fact", table_name="watch_fact_ledger")
    op.drop_index("ix_watch_ledger_subject", table_name="watch_fact_ledger")
    op.drop_index("ix_watch_ledger_tenant_seq", table_name="watch_fact_ledger")
    op.drop_table("watch_fact_ledger")
