"""moteur de veille : le Signal et la mémoire du lien (bloc 2)

Le cas ouvert cesse d'être une proposition différée : il s'écrit. C'est ce qui donne enfin un
effet à une annonce de décès pour la famille endeuillée — l'épisode qui, jusqu'ici, était
proposé puis mis de côté faute d'objet pour le porter.

`owner_account_id` est nullable, et c'est **une donnée** : tant que `Referent` n'existe pas,
NULL dit la vérité — personne n'est désigné. Prétendre le contraire fausserait la mesure de
couverture le jour où elle comptera.

`watch_care_memory` porte la mémoire du lien, consommable une seule fois (`delivered_at`).

Les deux tables sont **entièrement** des projections du ledger : une reprojection les vide et
les reconstruit.

Revision ID: f6b7c8d9eafb
Revises: e5a6b7c8d9ea
Create Date: 2026-07-26 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b7c8d9eafb'
down_revision: Union[str, Sequence[str], None] = 'e5a6b7c8d9ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watch_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_account_id", sa.Uuid(), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("gestures_count", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watch_signals_tenant_status", "watch_signals", ["tenant_id", "status"])
    op.create_index("ix_watch_signals_subject", "watch_signals", ["tenant_id", "subject_id"])
    op.create_index("ix_watch_signals_owner", "watch_signals", ["tenant_id", "owner_account_id"])

    op.create_table(
        "watch_care_memory",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("item", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watch_care_memory_subject", "watch_care_memory", ["tenant_id", "subject_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_watch_care_memory_subject", table_name="watch_care_memory")
    op.drop_table("watch_care_memory")
    op.drop_index("ix_watch_signals_owner", table_name="watch_signals")
    op.drop_index("ix_watch_signals_subject", table_name="watch_signals")
    op.drop_index("ix_watch_signals_tenant_status", table_name="watch_signals")
    op.drop_table("watch_signals")
