"""announcement subjects + neutralisation + retrait de veille (annonce → veille)

Une annonce nomme des personnes **et le rôle qu'elles y tiennent** (`announcement_subjects`) ;
c'est le rôle qui décide de l'effet sur la veille fraternelle.

Trois écritures :
- `announcements.occurred_at` — quand l'événement est **survenu** (distinct de `published_at`,
  quand on l'a dit, et de `event_at`, quand on se réunit). Toutes les durées courent depuis là ;
- `announcement_subjects` — qui, à quel titre, avec quels effets retenus et l'accord du sujet ;
- `planned_absences.source/source_ref/returned_at/outcome` — l'absence planifiée devient aussi le
  support de la **neutralisation** posée par une annonce (une seule vérité sur « attendu plus
  tard », que le roster et M7 consultent déjà) ;
- `watch_exclusions` — le retrait **définitif** de la veille (décès). Statut de veille, jamais
  statut d'appartenance : publier une annonce ne ferme pas l'adhésion de quelqu'un.

Revision ID: d4f5a6b7c8d9
Revises: c3e4f5a6b7c8
Create Date: 2026-07-26 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'c3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "announcements",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "announcement_subjects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("announcement_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("effects", sa.JSON(), nullable=False),
        sa.Column("consent", sa.String(), nullable=False),
        sa.Column("declared_duration_days", sa.Integer(), nullable=True),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcements.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Une personne, un rôle par annonce — et la clé d'idempotence du rejeu.
        sa.UniqueConstraint("announcement_id", "account_id", name="uq_announcement_subject"),
    )
    op.create_index(
        "ix_announcement_subjects_account", "announcement_subjects", ["account_id"]
    )

    # L'absence planifiée porte désormais deux origines. Les lignes existantes sont toutes des
    # déclarations du membre : le défaut serveur les qualifie sans les réécrire une par une.
    op.add_column(
        "planned_absences",
        sa.Column(
            "source", sa.String(), nullable=False, server_default="self_declared"
        ),
    )
    op.add_column("planned_absences", sa.Column("source_ref", sa.Uuid(), nullable=True))
    op.add_column(
        "planned_absences",
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("planned_absences", sa.Column("outcome", sa.String(), nullable=True))
    op.create_index(
        "ix_planned_absences_source_ref", "planned_absences", ["source_ref"]
    )

    op.create_table(
        "watch_exclusions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("excluded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("declared_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("source_ref", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "account_id", name="uq_watch_exclusion"),
    )


def downgrade() -> None:
    op.drop_table("watch_exclusions")
    op.drop_index("ix_planned_absences_source_ref", table_name="planned_absences")
    op.drop_column("planned_absences", "outcome")
    op.drop_column("planned_absences", "returned_at")
    op.drop_column("planned_absences", "source_ref")
    op.drop_column("planned_absences", "source")
    op.drop_index("ix_announcement_subjects_account", table_name="announcement_subjects")
    op.drop_table("announcement_subjects")
    op.drop_column("announcements", "occurred_at")
