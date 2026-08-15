"""La version dans laquelle la citation a ete reconnue.

L'index ne porte le texte que de la version de repli. Une citation tiree d'une autre
traduction detenue est retrouvee par une seconde passe en base -- mais **la trace n'est pas
persistee**, elle se recalcule a chaque lecture. Sans cette colonne, la premiere ouverture
disait « retrouve dans Darby » et la relecture suivante « lu comme une intention » : la meme
preparation, deux motifs contradictoires.

On range donc la trouvaille a cote de la resolution qu'elle a produite. NULL = la resolution
ne vient pas d'ailleurs (reference, citation dans la version de repli, IA, ou rien).

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "urim_preparation",
        sa.Column("citation_version", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("urim_preparation", "citation_version")
