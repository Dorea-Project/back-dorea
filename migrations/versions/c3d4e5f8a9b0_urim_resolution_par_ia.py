"""urim_resolution_par_ia : `chosen_by` accepte « ia »

`urim_resolution_attempt.chosen_by` disait **qui a tranché** — le moteur ou le pasteur. Un
modèle qui retrouve la référence n'est ni l'un ni l'autre : le déterminisme du moteur se
vérifie, la décision du pasteur l'engage, et le verdict d'un modèle ne fait ni l'un ni
l'autre. Les confondre effacerait la seule information que cette colonne existe pour porter.

Revision ID: c3d4e5f8a9b0
Revises: b2c3d4e5f8a9
Create Date: 2026-08-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ANCIEN = "chosen_by IN ('moteur','pasteur')"
_NOUVEAU = "chosen_by IN ('moteur','pasteur','ia')"


def upgrade() -> None:
    op.drop_constraint("attempt_chosen_by", "urim_resolution_attempt", type_="check")
    op.create_check_constraint("attempt_chosen_by", "urim_resolution_attempt", _NOUVEAU)


def downgrade() -> None:
    # Les lignes « ia » deviendraient invalides : on les remet sur « moteur », qui est le
    # moins faux — la bordure du moteur est bien ce qui a appelé le modèle.
    op.execute(
        "UPDATE urim_resolution_attempt SET chosen_by = 'moteur' WHERE chosen_by = 'ia'"
    )
    op.drop_constraint("attempt_chosen_by", "urim_resolution_attempt", type_="check")
    op.create_check_constraint("attempt_chosen_by", "urim_resolution_attempt", _ANCIEN)
