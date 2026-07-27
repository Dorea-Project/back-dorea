"""la boucle de contact : enregistrer l'effort au départ, et les deux métriques du pilote

**Le problème.** Dorea n'héberge pas le contact : on sort vers WhatsApp ou le téléphone, et on
ne revient pas. Le responsable appelle, la conversation dure vingt minutes, il passe à autre
chose, et l'issue n'est jamais enregistrée. Le signal reste ouvert, le taux d'ignorés explose —
non parce que personne n'a appelé, mais **parce que personne n'est revenu le dire**.

Le système conclut alors que la veille ne fonctionne pas, alors que le contact humain a bien eu
lieu. C'est le pire des faux négatifs : celui qui invalide un succès réel, et qui fait abandonner
un outil qui marchait.

`watch_contact_attempts` porte la trace de l'effort, écrite **avant** que l'application perde la
main. `result = pending` est l'état normal au départ, pas une anomalie.

`watch_signals` gagne les deux mesures du pilote :

- `first_seen_at` — le cas a été **ouvert** par son propriétaire. Alimente le taux d'ignorés à
  14 jours, le seul indicateur qui *anticipe* l'abandon ; tous les autres constatent ;
- `first_contact_at` — le délai détection → premier contact humain, la métrique reine.

Revision ID: f2fb0c1d2e3f
Revises: e1fb0c1d2e3f
Create Date: 2026-07-27 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2fb0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'e1fb0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "watch_signals", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "watch_signals",
        sa.Column("first_contact_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "watch_contact_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("by_account_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watch_contact_signal", "watch_contact_attempts", ["signal_id"])
    op.create_index(
        "ix_watch_contact_pending",
        "watch_contact_attempts",
        ["tenant_id", "by_account_id", "result"],
    )


def downgrade() -> None:
    op.drop_index("ix_watch_contact_pending", table_name="watch_contact_attempts")
    op.drop_index("ix_watch_contact_signal", table_name="watch_contact_attempts")
    op.drop_table("watch_contact_attempts")
    op.drop_column("watch_signals", "first_contact_at")
    op.drop_column("watch_signals", "first_seen_at")
