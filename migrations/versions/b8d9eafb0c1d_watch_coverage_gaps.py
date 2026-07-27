"""correctifs bloc R : unicité des politiques par défaut + défauts de couverture

**C2 — l'unicité qui ne protégeait rien.** `watch_group_type_policies` porte
`UniqueConstraint(tenant_id, group_type)` avec `tenant_id` nullable. Or en SQL `NULL != NULL` :
les trois lignes par défaut pouvaient être insérées plusieurs fois — re-seed, aller-retour de
migration, script d'init rejoué. `all_for()` aurait alors renvoyé deux rangs concurrents pour un
même type, et le résolveur serait devenu **non déterministe selon l'ordre de lecture**, ce qui
casse la rejouabilité du ledger. Un index unique **partiel** `WHERE tenant_id IS NULL` ferme ça.

La colonne reste nullable : `NULL = politique par défaut` est le bon design, on ne le change pas.

**C3 — le propriétaire nul devenait un silence.** Quand ni admin ni pasteur n'existe, on refuse
d'inventer un destinataire — c'est juste — mais l'échec était muet. Une église mal configurée
détectait tout et n'émettait rien, et son écran vide disait « tout va bien » alors qu'il disait
« personne n'est configuré ». `watch_coverage_gaps` rend ce trou visible là où il doit l'être :
dans la couverture, pas dans un journal applicatif que personne ne lit.

`subject_id` est nullable : un défaut peut porter sur l'**église entière**, ce qu'aucun fait ne
sait dire puisqu'un `Fact` a pour sujet une personne ou un groupe.

Revision ID: b8d9eafb0c1d
Revises: a7c8d9eafb0c
Create Date: 2026-07-26 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d9eafb0c1d'
down_revision: Union[str, Sequence[str], None] = 'a7c8d9eafb0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # C2 — dédoublonner d'abord : si un re-seed a déjà eu lieu, l'index refuserait de se créer.
    # On garde la ligne la plus ancienne de chaque type (celle du seed initial).
    op.execute(
        """
        DELETE FROM watch_group_type_policies a
        USING watch_group_type_policies b
        WHERE a.tenant_id IS NULL
          AND b.tenant_id IS NULL
          AND a.group_type = b.group_type
          AND a.ctid > b.ctid
        """
    )
    op.create_index(
        "uq_watch_group_type_policy_default",
        "watch_group_type_policies",
        ["group_type"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
        sqlite_where=sa.text("tenant_id IS NULL"),
    )

    # C3 — les trous du dispositif, visibles.
    op.create_table(
        "watch_coverage_gaps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),  # person | group | tenant
        sa.Column("subject_id", sa.Uuid(), nullable=True),  # NULL = l'église entière
        sa.Column("gap", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watch_coverage_gaps_tenant",
        "watch_coverage_gaps",
        ["tenant_id", "resolved_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_watch_coverage_gaps_tenant", table_name="watch_coverage_gaps")
    op.drop_table("watch_coverage_gaps")
    op.drop_index(
        "uq_watch_group_type_policy_default", table_name="watch_group_type_policies"
    )
