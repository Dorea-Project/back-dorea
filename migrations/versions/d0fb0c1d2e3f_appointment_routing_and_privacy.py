"""routage et relais du rendez-vous + paramètres par église + désignation de pasteur

**Bloc 5 — le relais.** Une main levée à laquelle personne ne répond est pire qu'un canal fermé.
`appointments` porte désormais chez qui la demande est (`routed_to_account_id`), depuis quand,
combien de fois elle a été relayée, et **pourquoi** — un pasteur qui reçoit une demande sans
savoir pourquoi elle lui arrive l'ignore.

**`pastor_overrides`** remplace un point d'extension resté vide : sans lui la cascade n'avait pas
de premier étage, et la seule façon de corriger un routage était d'attendre que quelqu'un ne
réponde pas.

**`watch_parameters`** matérialise enfin ce que le moteur exige depuis le début : *les politiques
sont des données, jamais des constantes*. Délai de relais, plafond de cas, seuils d'agrégation —
calibrables par église, sans livraison. `tenant_id` NULL = le défaut du produit, protégé par un
index partiel (en SQL, `NULL != NULL` : sans lui le défaut serait ré-insérable à chaque seed).

Le **bloc 6 (cloisonnement)** n'a besoin d'aucune écriture : il tient dans le type de sortie des
requêtes. Le secrétariat reçoit un `AgendaEntryDTO` qui ne **porte pas** les champs sensibles —
un oubli de filtrage ne peut donc pas les faire fuir.

Revision ID: d0fb0c1d2e3f
Revises: c9eafb0c1d2e
Create Date: 2026-07-27 14:00:00.000000

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0fb0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'c9eafb0c1d2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Des paris, pas des vérités — c'est bien pour ça qu'ils sont en table.
DEFAULT_PARAMS = (
    ("open_cases_cap", 5),
    ("relay_delay_hours", 48),
    ("relay_attempts_before_gap", 2),
    ("coverage_aggregation_threshold", 3),
)


def upgrade() -> None:
    for column in (
        sa.Column("routed_to_account_id", sa.Uuid(), nullable=True),
        sa.Column("routed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relay_reason", sa.String(), nullable=True),
    ):
        op.add_column("appointments", column)
    op.add_column(
        "appointments",
        sa.Column("relay_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "pastor_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("pastor_account_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pastor_override_person", "pastor_overrides", ["tenant_id", "person_id"]
    )

    params = op.create_table(
        "watch_parameters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),  # NULL = défaut du produit
        sa.Column("param", sa.String(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "param", name="uq_watch_parameter"),
    )
    op.create_index(
        "uq_watch_parameter_default",
        "watch_parameters",
        ["param"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
        sqlite_where=sa.text("tenant_id IS NULL"),
    )
    op.bulk_insert(
        params,
        [
            {"id": uuid4(), "tenant_id": None, "param": name, "value": value}
            for name, value in DEFAULT_PARAMS
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_watch_parameter_default", table_name="watch_parameters")
    op.drop_table("watch_parameters")
    op.drop_index("ix_pastor_override_person", table_name="pastor_overrides")
    op.drop_table("pastor_overrides")
    for column in (
        "relay_count",
        "relay_reason",
        "routed_at",
        "routed_to_account_id",
    ):
        op.drop_column("appointments", column)
