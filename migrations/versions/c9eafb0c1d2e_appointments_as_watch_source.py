"""le rendez-vous devient une source de veille : issues tracées, indisponibilité déclarée

**Un rendez-vous demandé est une main levée. L'agenda n'est que ce qui se passe après.**

Le module se terminait sur lui-même : une demande produisait un créneau, et les chemins d'échec
— décliné, réorienté, annulé, non honoré — disparaissaient sans laisser de trace. Ce sont
pourtant eux qui portent le plus d'information, et l'annulation par le demandeur est
probablement le signal le plus urgent que le produit sache produire : quelqu'un a franchi le pas
le plus difficile, puis a fait demi-tour.

Trois écritures :

- `appointments.oriented_to_account_id` — servi autrement, pas refusé ;
- `appointments.cancelled_by_account_id` — **qui** a annulé. Le demandeur qui recule et l'église
  qui range son agenda ne disent pas la même chose ;
- `pastor_unavailabilities` — l'absence déclarée d'un pasteur, à ne pas confondre avec ses
  créneaux. Sans elle, un pasteur en voyage trois semaines ferait attendre chaque demande le
  délai de relais complet, alors qu'on savait dès le premier jour qu'il ne répondrait pas.

Côté moteur, `watch_signals` gagne :

- `priority` — distincte de l'origine : un cas d'absence qu'un rendez-vous annulé rend
  soudain le plus urgent de la file garde son origine et change d'urgence ;
- `annotations` — ce qu'on a appris **depuis** l'ouverture. La raison d'origine ne bouge jamais ;
  on ajoute. C'est ce qui permet de lire une trajectoire au lieu d'un instantané.

Aucun nouveau type de fait : `APPOINTMENT_REQUESTED` existait au registre, l'état voyage dans le
payload.

Revision ID: c9eafb0c1d2e
Revises: b8d9eafb0c1d
Create Date: 2026-07-27 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9eafb0c1d2e'
down_revision: Union[str, Sequence[str], None] = 'b8d9eafb0c1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointments", sa.Column("oriented_to_account_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "appointments", sa.Column("cancelled_by_account_id", sa.Uuid(), nullable=True)
    )

    op.create_table(
        "pastor_unavailabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("pastor_account_id", sa.Uuid(), nullable=False),
        sa.Column("unavailable_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unavailable_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),  # court, jamais exigé
        sa.Column("declared_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pastor_unavailability",
        "pastor_unavailabilities",
        ["tenant_id", "pastor_account_id"],
    )

    # Les cas déjà ouverts prennent leur origine comme priorité — c'était déjà le comportement
    # implicite, on ne fait que l'écrire.
    op.add_column("watch_signals", sa.Column("priority", sa.String(), nullable=True))
    op.execute("UPDATE watch_signals SET priority = origin WHERE priority IS NULL")
    op.alter_column("watch_signals", "priority", nullable=False)

    op.add_column("watch_signals", sa.Column("annotations", sa.JSON(), nullable=True))
    op.execute("UPDATE watch_signals SET annotations = '[]'::json WHERE annotations IS NULL")
    op.alter_column("watch_signals", "annotations", nullable=False)


def downgrade() -> None:
    op.drop_column("watch_signals", "annotations")
    op.drop_column("watch_signals", "priority")
    op.drop_index("ix_pastor_unavailability", table_name="pastor_unavailabilities")
    op.drop_table("pastor_unavailabilities")
    op.drop_column("appointments", "cancelled_by_account_id")
    op.drop_column("appointments", "oriented_to_account_id")
