"""le destinataire d'un cas cesse d'être facultatif

**Ce qui était faux.** `watch_signals.owner_account_id` était nullable, et le commentaire disait
que ce nul était « une donnée ». Il l'est pour le **référent** — « personne ne connaît cette
personne » est précisément ce qu'il faut voir. Il ne l'est pas pour le destinataire d'un cas : un
cas sans destinataire est un cas que personne ne traite, et la règle « un cas sans propriétaire
est prenable » en faisait une porte — n'importe quel responsable de la portée pouvait s'attribuer
le cas, donc le lire.

C'est par cette porte que passait la fuite du rendez-vous : un cas ouvert sur « A demandé à
rencontrer un pasteur. « … » » retombait sur le responsable de cellule du demandeur.

**Pourquoi la contrainte peut tenir.** La cascade de `ResolveSignalOwner` se termine désormais sur
le propriétaire de l'église, qui existe toujours. Aucune inquiétude ne se perd faute de
configuration, et le recours à ce dernier échelon reste consigné en défaut de couverture.

**Le rattrapage des lignes existantes.** On n'invente pas de destinataire en SQL : la résolution
est une cascade applicative (override manuel, responsable du groupe primaire, inviteur, équipe
d'accueil, puis admin / pasteur / propriétaire). Les lignes orphelines sont donc rattachées au
**propriétaire de l'église** — le même dernier échelon que la cascade — et la vérité se
reconstruit d'un coup par une reprojection (`RebuildProjections`), qui rejoue le ledger avec
l'étage 02bis branché. Si une ligne reste sans destinataire après ce rattrapage (église sans
propriétaire actif, ce qui ne devrait pas exister), la migration **échoue bruyamment** plutôt que
de laisser passer un cas que personne ne recevra.

Revision ID: d6fc0c1d2e3f
Revises: c5fc0c1d2e3f
Create Date: 2026-07-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd6fc0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = 'c5fc0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # Rattrapage : le propriétaire actif de l'église du cas.
    connection.execute(
        sa.text(
            """
            UPDATE watch_signals AS s
               SET owner_account_id = o.account_id
              FROM tenant_ownerships AS o
             WHERE s.owner_account_id IS NULL
               AND o.tenant_id = s.tenant_id
               AND o.status = 'active'
            """
        )
    )

    orphans = connection.execute(
        sa.text("SELECT count(*) FROM watch_signals WHERE owner_account_id IS NULL")
    ).scalar_one()
    if orphans:
        raise RuntimeError(
            f"{orphans} cas sans destinataire, et leur église n'a pas de propriétaire actif. "
            "Corriger la propriété de ces tenants avant d'appliquer cette migration — un cas "
            "que personne ne reçoit ne doit pas devenir un cas que tout le monde peut lire."
        )

    op.alter_column(
        "watch_signals",
        "owner_account_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "watch_signals",
        "owner_account_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
