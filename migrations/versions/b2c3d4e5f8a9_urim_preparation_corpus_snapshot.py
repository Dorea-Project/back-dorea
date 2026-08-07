"""urim_preparation_corpus_snapshot : l'empreinte du corpus contre lequel on a préparé

`StudyState.corpus_snapshot` est la clé du déterminisme — même saisie, même corpus, même
sortie. La table ne la portait pas : une préparation rouverte après un enrichissement du
corpus aurait rejoué une trace **différente sans que rien ne le signale**.

La colonne rend la dérive visible plutôt que devinable. Elle est nullable : les
préparations ouvertes avant cette migration n'ont pas d'empreinte, et prétendre le
contraire serait pire que l'admettre.

Revision ID: b2c3d4e5f8a9
Revises: a1b2c3d4e5f7
Create Date: 2026-08-07 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f8a9'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "urim_preparation",
        sa.Column("corpus_snapshot", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("urim_preparation", "corpus_snapshot")
