"""device_revocation : la déconnexion tue vraiment les jetons (DOREA-016)

Avant : le logout backoffice effaçait le cookie — le jeton restait valable 12 h ; le
mobile n'avait **aucune** déconnexion, et son refresh vivait 30 jours. Un appareil volé
gardait l'accès jusqu'à expiration.

Le jeton porte désormais l'appareil (`did`), et l'appareil peut être **révoqué** :
access, refresh et session meurent ensemble puisqu'ils désignent le même appareil.

L'index d'unicité devient **partiel** : un appareil révoqué garde sa ligne (trace), et
le même appareil peut redevenir de confiance plus tard (nouvel OTP) sans collision.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-04 01:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: str | Sequence[str] | None = 'f6a7b8c9d0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trusted_devices",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_index("uq_account_device", table_name="trusted_devices")
    op.create_index(
        "uq_account_device",
        "trusted_devices",
        ["account_id", "device_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    # Les appareils révoqués redeviendraient des doublons : on les purge d'abord.
    op.execute("DELETE FROM trusted_devices WHERE revoked_at IS NOT NULL")
    op.drop_index("uq_account_device", table_name="trusted_devices")
    op.create_index(
        "uq_account_device", "trusted_devices", ["account_id", "device_id"], unique=True
    )
    op.drop_column("trusted_devices", "revoked_at")
