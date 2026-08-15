"""La surface du relecteur — le registre des signataires, et la file matérialisée

Deux tables pour une seule dette : 0 pesée relue par un humain sur 45 557.

`urim_reviewer` sort le nom du signataire des corps de requête. `verifier_verdict()` refusait
déjà le vide, les noms de semis et `ia-mistral` ; il n'a jamais pu refuser le nom de quelqu'un
d'autre — et un verdict d'essai a été posé au nom du propriétaire du dépôt. Tant que le nom est
une donnée d'entrée, aucune vérification ne le sauve.

`urim_corpus_signal` matérialise la file des détecteurs. D2 mesure la fréquence d'une tournure
sur tout le corpus : rien de global ne se recalcule dans le temps d'une requête HTTP. C'est une
photographie remplacée à chaque balayage, jamais un journal — d'où `scanned_at`, que la surface
expose, parce qu'une file dont on ne sait pas l'âge ment.

Revision ID: e6f708192a3b
Revises: d4e5f8a9b0c1
"""

import sqlalchemy as sa
from alembic import op

revision = "e6f708192a3b"
down_revision = "d4e5f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urim_reviewer",
        sa.Column("identifiant", sa.String(length=60), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("identifiant"),
        # La machine ne s'enrôle pas : `urim_corpus_review` lui interdit de signer un verdict,
        # celui-ci lui interdit d'exister comme signataire possible.
        sa.CheckConstraint(
            "identifiant <> 'ia-mistral' AND display_name <> 'ia-mistral'",
            name="reviewer_jamais_la_machine",
        ),
        # Le nom affiché **est** ce qui atterrit dans `reviewed_by` : deux homonymes rendraient
        # la trace illisible là où elle sert, sous les yeux du pasteur.
        sa.UniqueConstraint("display_name", name="reviewer_nom_unique"),
    )

    op.create_table(
        "urim_corpus_signal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pericope_id", sa.Uuid(), nullable=False),
        sa.Column("detector", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("scan_fingerprint", sa.String(length=32), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pericope_id"], ["urim_corpus_pericope.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("severity BETWEEN 1 AND 3", name="signal_gravite_bornee"),
    )
    op.create_index("ix_urim_signal_pericope", "urim_corpus_signal", ["pericope_id"])
    op.create_index("ix_urim_signal_gravite", "urim_corpus_signal", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_urim_signal_gravite", table_name="urim_corpus_signal")
    op.drop_index("ix_urim_signal_pericope", table_name="urim_corpus_signal")
    op.drop_table("urim_corpus_signal")
    op.drop_table("urim_reviewer")
