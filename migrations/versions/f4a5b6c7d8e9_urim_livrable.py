"""Le livrable — le document et son encodage séparés, et la validation signée

`urim_deliverable` portait `kind IN ('pptx','pdf')`, ce qui mélangeait deux questions. Avec
**deux documents** (ce que l'assemblée voit / la note du prédicateur) et **trois formats** (le
PDF est gardé, comme conversion), une seule colonne ne peut plus dire lequel est sorti — or
c'est précisément la frontière que le livrable existe pour tenir, et ce que la trace doit savoir.

1. **`kind IN ('deck','note')`** — *quel document* — et **`format IN ('pptx','docx','pdf')`** —
   *sous quel encodage*. Plus un `CHECK` qui interdit les deux couples impossibles : un deck
   n'est jamais un `.docx`, une note n'est jamais un `.pptx`.

2. **`validated_by` / `validated_at`**, et un `CHECK` : `validation = 'conforme'` exige les
   deux. Un livrable conforme que personne n'a signé serait une validation que personne n'a
   faite — exactement ce que la règle centrale interdit. Même patron que
   `synthese_validee_signee` côté Retour et `reviewed_by NOT NULL` côté corpus.

3. **`corpus_snapshot` et `content_fingerprint`** : *une décision ne vaut que sur l'objet
   qu'elle a regardé*. Deux documents de la même préparation à deux semaines d'écart ne sont pas
   le même document, et sans empreinte on ne peut ni le dire ni le prouver.

Rien à migrer : la table n'a jamais été écrite.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
"""

from alembic import op
import sqlalchemy as sa

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("deliverable_kind", "urim_deliverable", type_="check")
    op.add_column(
        "urim_deliverable",
        sa.Column("format", sa.String(), nullable=False, server_default="pptx"),
    )
    op.alter_column("urim_deliverable", "format", server_default=None)
    op.add_column("urim_deliverable", sa.Column("validated_by", sa.Uuid(), nullable=True))
    op.add_column(
        "urim_deliverable",
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "urim_deliverable", sa.Column("corpus_snapshot", sa.String(64), nullable=True)
    )
    op.add_column(
        "urim_deliverable", sa.Column("content_fingerprint", sa.String(32), nullable=True)
    )

    op.create_check_constraint(
        "deliverable_kind", "urim_deliverable", "kind IN ('deck','note')"
    )
    op.create_check_constraint(
        "deliverable_format", "urim_deliverable", "format IN ('pptx','docx','pdf')"
    )
    # Les deux couples que la frontière du §3 rend impossibles. En base plutôt qu'au service :
    # une garde applicative tombe dès qu'un second chemin d'écriture apparaît.
    op.create_check_constraint(
        "deliverable_document_format",
        "urim_deliverable",
        "(kind = 'deck' AND format IN ('pptx','pdf'))"
        " OR (kind = 'note' AND format IN ('docx','pdf'))",
    )
    op.create_check_constraint(
        "deliverable_validation_signee",
        "urim_deliverable",
        "validation IS DISTINCT FROM 'conforme'"
        " OR (validated_by IS NOT NULL AND validated_at IS NOT NULL)",
    )


def downgrade() -> None:
    for nom in (
        "deliverable_validation_signee",
        "deliverable_document_format",
        "deliverable_format",
        "deliverable_kind",
    ):
        op.drop_constraint(nom, "urim_deliverable", type_="check")
    for colonne in (
        "content_fingerprint", "corpus_snapshot", "validated_at", "validated_by", "format",
    ):
        op.drop_column("urim_deliverable", colonne)
    op.create_check_constraint(
        "deliverable_kind", "urim_deliverable", "kind IN ('pptx','pdf')"
    )
