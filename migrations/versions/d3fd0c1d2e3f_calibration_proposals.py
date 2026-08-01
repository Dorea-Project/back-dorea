"""la boucle froide : ce qu'elle propose attend un humain

**Le problème.** Les seuils du moteur sont des paris — `DEFAULTS` le dit en toutes lettres. Rien
ne les confronte à ce que les églises constatent réellement, et une valeur de départ jamais
mesurée finit par passer pour une vérité parce qu'elle n'a jamais été contredite.

**Ce que cette table est.** Ce que la boucle froide *propose*, et rien de plus : un paramètre, sa
valeur, celle qu'on suggère, et la phrase qui le justifie. Elle vit **hors du journal** — une
proposition n'est pas un fait, aucun rejeu ne la relit, aucun interpreter ne peut la transformer en
effet. Le seul chemin de retour vers la boucle chaude est un `WatchParam` entier qu'un humain, ou
une borne dure, a laissé passer.

**Ce qu'elle n'a pas.** Pas de `subject_id`, et ce n'est pas un oubli : le grain le plus fin de la
calibration est `(église, paramètre)`. Le seul identifiant de personne est `decided_by_account_id`
— l'auteur d'une décision, jamais le sujet d'une mesure. C'est la frontière du module, et un test
structurel la tient.

Revision ID: d3fd0c1d2e3f
Revises: c2fd0c1d2e3f
Create Date: 2026-08-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3fd0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'c2fd0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watch_calibration_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("param", sa.String(), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False),
        sa.Column("proposed_value", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("decided_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # L'écran du pasteur : ce qui attend une décision, chez lui.
    op.create_index(
        "ix_watch_calibration_pending",
        "watch_calibration_proposals",
        ["tenant_id", "status", "param"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_watch_calibration_pending", table_name="watch_calibration_proposals"
    )
    op.drop_table("watch_calibration_proposals")
