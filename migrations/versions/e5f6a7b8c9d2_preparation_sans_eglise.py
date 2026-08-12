"""urim_preparation.church_id devient nullable — la préparation sans église

Urim est l'antichambre : on y entre sans rien savoir de Dorea, et le rôle Dorea `null` est le
cas **normal**, pas le cas particulier. Une préparation qui n'appartient à aucune église, une
colonne nulle le dit exactement — c'est la formulation honnête, pas un raccourci.

Rien à migrer : les lignes existantes ont toutes une église, et elles la gardent.

Revision ID: e5f6a7b8c9d2
Revises: d4e5f8a9b0c1
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d2"
down_revision = "d4e5f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "urim_preparation", "church_id", existing_type=sa.Uuid(), nullable=True
    )


def downgrade() -> None:
    # Redescendre exige que plus aucune préparation personnelle n'existe : la contrainte
    # échouera d'elle-même s'il en reste, et c'est le bon comportement — on ne va pas
    # inventer une église à quelqu'un pour faire passer un `downgrade`.
    op.alter_column(
        "urim_preparation", "church_id", existing_type=sa.Uuid(), nullable=False
    )
