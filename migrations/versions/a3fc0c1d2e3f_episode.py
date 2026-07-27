"""l'épisode : ce qu'une réouverture doit savoir du cas précédent

**Le problème.** Awa a été absente en janvier ; Jean l'a appelée, elle allait mal, il a fermé le
cas le 3 février. Elle redécroche en mars. Sans mémoire, le nouveau cas s'affiche exactement
comme le premier — et Jean rappelle en ouvrant par « je vois que tu n'es pas venue », alors qu'il
lui a parlé six semaines plus tôt. C'est le moment précis où l'outil cesse d'être du soin pour
devenir un logiciel de relance.

Quatre colonnes suffisent à produire la phrase :

    « Nouvelle absence. Cas précédent clos le 3 février — repris contact, situation suivie. »

- `episode_id` — la chaîne des cas successifs sur une même personne ;
- `occurrence_number` — la combientième fois ;
- `previous_outcome` / `previous_closed_at` — de quoi écrire la phrase, **figés à l'ouverture**.

Figés, et non recalculés par jointure : le cas précédent peut être purgé, reprojeté, ou fermé
autrement plus tard, et la phrase lue par le responsable ne doit pas changer sous ses yeux.

Les lignes existantes ouvrent chacune leur propre épisode — c'est la vérité : aucune d'elles n'a
d'antériorité connue.

Revision ID: a3fc0c1d2e3f
Revises: f2fb0c1d2e3f
Create Date: 2026-07-27 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3fc0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'f2fb0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("watch_signals", sa.Column("episode_id", sa.Uuid(), nullable=True))
    op.add_column(
        "watch_signals",
        sa.Column("occurrence_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "watch_signals", sa.Column("previous_outcome", sa.String(), nullable=True)
    )
    op.add_column(
        "watch_signals",
        sa.Column("previous_closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Chaque cas existant est le premier de son propre épisode.
    op.execute("UPDATE watch_signals SET episode_id = id WHERE episode_id IS NULL")
    op.alter_column("watch_signals", "episode_id", nullable=False)

    op.create_index("ix_watch_signals_episode", "watch_signals", ["tenant_id", "episode_id"])


def downgrade() -> None:
    op.drop_index("ix_watch_signals_episode", table_name="watch_signals")
    op.drop_column("watch_signals", "previous_closed_at")
    op.drop_column("watch_signals", "previous_outcome")
    op.drop_column("watch_signals", "occurrence_number")
    op.drop_column("watch_signals", "episode_id")
