"""L'articulation proposée — dans l'atelier, jamais dans le document

Le pasteur demande au modèle d'articuler un point de son plan : un développement, une
transition. **Ce texte ne va nulle part ailleurs que dans son écran.** Le livrable n'imprime que
`preparation_element.body` — ce qu'il a écrit ou adopté — et il n'existe aucun chemin par lequel
une proposition non reprise atteigne un fichier.

D'où une table à part, et non une colonne de plus sur l'élément : **la proposition et le texte
du pasteur ne doivent pas partager un champ.** Dans la même colonne, une reprise silencieuse
suffirait à faire imprimer la machine sous son nom.

`input_hash` couvre le point tel qu'il était au moment de la demande. Il fait deux choses :
le rejeu ne redemande pas (donc ne refacture pas), et un point réécrit obtient une proposition
neuve plutôt qu'une réponse à une question qui n'est plus posée — même raisonnement que
`urim_model_suggestion`.

`model` est stocké pour la même raison que `corpus_snapshot` : `mistral-small-latest` est un
alias mouvant, et une proposition d'hier n'a pas été écrite par le modèle d'aujourd'hui.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
"""

from alembic import op
import sqlalchemy as sa

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urim_plan_suggestion",
        sa.Column(
            "preparation_id",
            sa.Uuid(),
            sa.ForeignKey("urim_preparation.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("element_code", sa.String(), primary_key=True),
        sa.Column("ordinal", sa.SmallInteger(), primary_key=True),
        sa.Column("input_hash", sa.String(32), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("transition", sa.Text(), nullable=True),
        sa.Column("suggested_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("urim_plan_suggestion")
