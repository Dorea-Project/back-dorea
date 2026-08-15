"""Les collisions de sens — la répartition de la divergence entre quatre témoins

Le détecteur comparait deux traductions à la fois et rendait un rapport. Il devient une
dimension servie au pasteur : ce que quatre traducteurs de bonne foi ont fait d'un même mot.

⚠️ Une collision N'EST PAS une variante textuelle. `urim_corpus_textual_variant` reste seule à
dire ce que les manuscrits portent, et se remplit depuis un apparat critique, par un humain.

`version.text_family` est un fait sur le témoin, affiché à côté de lui, dont le produit ne tire
aucune conclusion. La valeur de la Segond a été **mesurée** et non supposée : elle omet la
clause de Rm 8:1 et le comma johanneum comme Darby, et lit « celui qui » en 1 Tm 3:16 là où les
trois autres lisent « Dieu » — elle est éclectique, pas proche du Texte Reçu.

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
"""

import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ajoutée avec un défaut, remplie, puis rendue obligatoire : sans le défaut, la colonne
    # naîtrait NULL sur les quatre versions déjà semées et le `CHECK` refuserait la table.
    op.add_column(
        "urim_corpus_version",
        sa.Column(
            "text_family", sa.String(), nullable=False, server_default="eclectique"
        ),
    )
    op.create_check_constraint(
        "version_text_family",
        "urim_corpus_version",
        "text_family IN ('texte_recu','critique','eclectique','massoretique')",
    )
    # Les trois témoins dont l'édition est connue. La Segond garde `eclectique`, qui est le
    # défaut — et c'est le bon : c'est ce que la mesure a dit d'elle.
    op.execute(
        "UPDATE urim_corpus_version SET text_family = 'critique' WHERE code = 'DARBY'"
    )
    op.execute(
        "UPDATE urim_corpus_version SET text_family = 'texte_recu'"
        " WHERE code IN ('OST','MARTIN')"
    )

    op.create_table(
        "urim_corpus_collision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("book_id", sa.SmallInteger(), nullable=False),
        sa.Column("chapter", sa.SmallInteger(), nullable=False),
        sa.Column("verse", sa.SmallInteger(), nullable=False),
        sa.Column("word", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("form", sa.String(), nullable=False),
        sa.Column("corpus_fingerprint", sa.String(length=32), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["urim_corpus_book.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", "chapter", "verse", "word", name="collision_unique"),
        sa.CheckConstraint(
            "form IN ('temoin_isole','partage','segond_seule')", name="collision_form_close"
        ),
        sa.CheckConstraint("weight > 0", name="collision_poids_positif"),
    )
    op.create_index(
        "ix_urim_collision_ref", "urim_corpus_collision", ["book_id", "chapter", "verse"]
    )

    op.create_table(
        "urim_corpus_collision_witness",
        sa.Column("collision_id", sa.Uuid(), nullable=False),
        sa.Column("version_code", sa.String(), nullable=False),
        sa.Column("stance", sa.String(), nullable=False),
        sa.Column("reading", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["collision_id"], ["urim_corpus_collision.id"]),
        sa.PrimaryKeyConstraint("collision_id", "version_code"),
        sa.CheckConstraint(
            "stance IN ('accorde','diverge','muet')", name="collision_witness_stance"
        ),
        sa.CheckConstraint(
            "stance = 'diverge' OR reading IS NULL", name="collision_lecture_bornee"
        ),
    )


def downgrade() -> None:
    op.drop_table("urim_corpus_collision_witness")
    op.drop_index("ix_urim_collision_ref", table_name="urim_corpus_collision")
    op.drop_table("urim_corpus_collision")
    op.drop_constraint("version_text_family", "urim_corpus_version", type_="check")
    op.drop_column("urim_corpus_version", "text_family")
