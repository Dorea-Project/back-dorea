"""ce que l'échéance emporte avec elle jusqu'au jour où elle tombe

Une échéance posée aujourd'hui sera interprétée dans trois semaines. Ce que l'on savait au moment
de la poser — le groupe concerné, la cadence que la personne a choisie, la date de sa dernière
parole — doit donc voyager **avec elle**.

L'alternative serait de relire ces informations au moment du tir. Elle est mauvaise pour deux
raisons : l'état aura bougé (le groupe a changé de responsable, la cadence a été modifiée), et
surtout un interpreter qui relit l'état courant n'est plus déterministe — rejouer le journal
demain ne rendrait plus ce que le direct a rendu, et l'invariant sur lequel repose toute la
reprojection tomberait sans bruit.

Revision ID: e7fc0c1d2e3f
Revises: d6fc0c1d2e3f
Create Date: 2026-07-30 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7fc0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'd6fc0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "watch_scheduled_checks",
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("watch_scheduled_checks", "payload")
