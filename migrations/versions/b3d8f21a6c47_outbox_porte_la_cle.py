"""outbox : la clé du catalogue remplace la phrase (L-1 du bilingue)

`scheduled_notifications` stockait le titre et le corps **rendus**. Un rappel de rendez-vous se
pose des semaines à l'avance, et surtout *avant* qu'on sache dans quelle langue il sera lu : la
phrase s'y figeait dans la langue du jour où elle avait été planifiée. On y écrit désormais la
clé du catalogue et les paramètres humains ; le texte naît au dispatch.

**Sans perte, et c'est le point délicat.** Les lignes déjà en file portent leur phrase et aucune
clé. Plutôt que de deviner la clé depuis le texte (fragile : il faudrait ré-analyser
« « Untel » — Salle 2. » pour en réextraire le titre et le lieu), on rend `title`/`body`
nullables et on les laisse partir telles quelles. Le dispatcher sait lire les deux formes. La
file se draine seule — le plus long différé du produit est le rappel d'événement, à 24 h — après
quoi une migration de nettoyage pourra supprimer les deux colonnes.

Revision ID: b3d8f21a6c47
Revises: a7c1e04b93d5
Create Date: 2026-08-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d8f21a6c47'
down_revision: Union[str, Sequence[str], None] = 'a7c1e04b93d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scheduled_notifications", sa.Column("message_key", sa.String(), nullable=True)
    )
    op.add_column("scheduled_notifications", sa.Column("params", sa.JSON(), nullable=True))
    # Les lignes en file gardent leur texte ; plus rien de neuf ne le remplit.
    op.alter_column("scheduled_notifications", "title", existing_type=sa.String(), nullable=True)
    op.alter_column("scheduled_notifications", "body", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    # Redescendre exige un texte : on rend au titre/corps ce que la clé disait, faute de quoi
    # `NOT NULL` refuserait les lignes posées depuis. La phrase exacte est perdue — c'est le
    # sens même de la migration — mais aucune ligne ne l'est.
    op.execute(
        "UPDATE scheduled_notifications SET title = COALESCE(title, message_key), "
        "body = COALESCE(body, '') WHERE title IS NULL OR body IS NULL"
    )
    op.alter_column("scheduled_notifications", "body", existing_type=sa.Text(), nullable=False)
    op.alter_column("scheduled_notifications", "title", existing_type=sa.String(), nullable=False)
    op.drop_column("scheduled_notifications", "params")
    op.drop_column("scheduled_notifications", "message_key")
