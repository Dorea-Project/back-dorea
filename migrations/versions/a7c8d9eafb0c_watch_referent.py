"""moteur de veille : le Referent — cascade, lien primaire dérivé, trous datés (bloc R)

Aucun champ `current_referent_id` sur la personne, aucun drapeau `is_primary` sur
l'appartenance : le référent est **résolu à la lecture**. Un champ que personne n'a intérêt à
maintenir pourrit en trois mois, et on retrouve des gens à zéro ou deux primaires — exactement
l'indétermination qu'on voulait supprimer.

Ce qu'on stocke, et seulement cela :
- `watch_group_type_policies` — **le rang est une donnée, pas une constante**. Le résolveur ne
  connaît le nom d'aucun type de groupe : il lit cette table. Enrichir `GroupType` devient une
  insertion de ligne, sans toucher au code ni risquer de casser la résolution ;
- `watch_referent_overrides` — les désignations explicites ;
- `watch_primary_group_overrides` — « c'est ce groupe-là qui compte pour elle » ;
- `watch_referent_history` — append-only, `referent_person_id` NULL marquant le début d'un trou.
  Sans datation, « sans référent » n'est pas actionnable ; « sans référent depuis quatre mois »
  l'est.

Seed du défaut (tenant NULL, valable pour toutes les églises) : CELLULE 1, MINISTERE 2,
CLASSE 3 — ordonnés par **durabilité du lien**, pas par intensité. Une classe d'intégration
s'achève en quelques mois, un ministère dure ; quelqu'un qui est dans les deux verra son
référent basculer tout seul à la fin de la classe, gratuitement, puisque `GROUP_LEAD` est un
pointeur calculé.

Aucun type n'est exclu aujourd'hui. Le mécanisme (`bears_veille`) est en place **avant** le
risque : le jour où COMMISSION ou ASSOCIATION existeront, une ligne à `false` suffira.

Revision ID: a7c8d9eafb0c
Revises: f6b7c8d9eafb
Create Date: 2026-07-26 21:00:00.000000

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c8d9eafb0c'
down_revision: Union[str, Sequence[str], None] = 'f6b7c8d9eafb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Le défaut, ordonné par durabilité du lien. Modifiable par église sans toucher au code.
DEFAULT_POLICIES = (
    ("cellule", True, 1),
    ("ministere", True, 2),
    ("classe", True, 3),
)


def upgrade() -> None:
    policies = op.create_table(
        "watch_group_type_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),  # NULL = politique par défaut
        sa.Column("group_type", sa.String(), nullable=False),
        sa.Column("bears_veille", sa.Boolean(), nullable=False),
        sa.Column("primacy_rank", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "group_type", name="uq_watch_group_type_policy"),
    )
    op.bulk_insert(
        policies,
        [
            {
                "id": uuid4(),
                "tenant_id": None,
                "group_type": group_type,
                "bears_veille": bears,
                "primacy_rank": rank,
            }
            for group_type, bears, rank in DEFAULT_POLICIES
        ],
    )

    op.create_table(
        "watch_referent_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("referent_person_id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_reason", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watch_referent_overrides_person",
        "watch_referent_overrides",
        ["tenant_id", "person_id"],
    )

    op.create_table(
        "watch_primary_group_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watch_primary_group_person",
        "watch_primary_group_overrides",
        ["tenant_id", "person_id"],
    )

    op.create_table(
        "watch_referent_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("referent_person_id", sa.Uuid(), nullable=True),  # NULL = début d'un trou
        sa.Column("origin", sa.String(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cause", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watch_referent_history_person",
        "watch_referent_history",
        ["tenant_id", "person_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_watch_referent_history_person", table_name="watch_referent_history")
    op.drop_table("watch_referent_history")
    op.drop_index(
        "ix_watch_primary_group_person", table_name="watch_primary_group_overrides"
    )
    op.drop_table("watch_primary_group_overrides")
    op.drop_index(
        "ix_watch_referent_overrides_person", table_name="watch_referent_overrides"
    )
    op.drop_table("watch_referent_overrides")
    op.drop_table("watch_group_type_policies")
