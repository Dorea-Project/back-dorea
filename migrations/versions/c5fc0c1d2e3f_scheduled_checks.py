"""les échéances : la porte par laquelle le temps entre dans la veille

**Ce qui manquait.** `ScheduleCheck` était proposé par les interpreters depuis le premier jour et
la matérialisation disait noir sur blanc qu'elle ne savait pas l'écrire. Sans cette table : pas
de réévaluation des cas retenus, pas de rythme choisi par le membre, pas de vérification de
couverture à l'échéance. Le moteur détectait, mais rien ne revenait jamais le relancer.

**Pourquoi une table plutôt qu'un calcul.** Quand une échéance tombe, le worker écrit un
`CHECK_FIRED` **au ledger** — il ne modifie aucun état lui-même. C'est ce qui permet à un
interpreter de ne jamais lire l'horloge : rejouer le journal demain rend exactement ce qu'il a
rendu aujourd'hui. Un service qui « évaluerait les échéances en direct » casserait cet invariant
sans que rien ne le signale.

`reason` voyage avec l'échéance jusqu'au fait émis : un rappel qu'on ne sait plus expliquer est
un rappel qu'on ignore.

`fired_at` et `cancelled_at` sont exclusifs. L'annulation n'est pas une commodité : sans elle on
programme des rappels sur des gens décédés ou qui ont demandé qu'on cesse.

Revision ID: c5fc0c1d2e3f
Revises: b4fc0c1d2e3f
Create Date: 2026-07-28 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5fc0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'b4fc0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watch_scheduled_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # L'index du worker : ce qui est dû, non tiré, non annulé.
    op.create_index(
        "ix_watch_checks_due",
        "watch_scheduled_checks",
        ["tenant_id", "due_at", "fired_at", "cancelled_at"],
    )
    # L'index de l'annulation : tout ce qui pend sur une personne, d'un coup.
    op.create_index(
        "ix_watch_checks_subject", "watch_scheduled_checks", ["tenant_id", "subject_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_watch_checks_subject", table_name="watch_scheduled_checks")
    op.drop_index("ix_watch_checks_due", table_name="watch_scheduled_checks")
    op.drop_table("watch_scheduled_checks")
