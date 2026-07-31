"""un cas rétracté n'est pas toujours un cas faux

`RETRACTED` mélangeait deux choses que le pilote a besoin de distinguer. Un cas **devenu faux**
n'avait jamais lieu d'être : une saisie tardive a montré qu'il reposait sur une erreur. Un cas
**dépassé par un signe de vie** n'est pas faux — il est sans objet : la personne a donné de ses
nouvelles avant que quiconque ne la contacte.

Les deux sortent des métriques de résolution, et c'est juste : ni l'un ni l'autre n'a résolu quoi
que ce soit. Mais les confondre empêcherait de lire ce qui s'est réellement passé — le premier dit
que la détection s'est trompée, le second qu'elle a été plus lente que la vie.

On réutilise l'état plutôt que d'en ajouter un septième : la machine à états ne bouge pas, une
colonne suffit.

Revision ID: b1fd0c1d2e3f
Revises: a9fc0c1d2e3f
Create Date: 2026-07-31 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1fd0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'a9fc0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("watch_signals", sa.Column("retraction_cause", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("watch_signals", "retraction_cause")
