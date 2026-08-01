"""Qui peut voir l'anniversaire de qui — **les gens de ses groupes**, et personne d'autre.

Le cercle n'est pas « l'église » : dans une assemblée de huit cents personnes, un encart qui
afficherait douze anniversaires par jour serait du bruit, et le douzième nom n'appellerait aucun
geste. C'est le groupe qui donne le cercle, parce que c'est là qu'on se connaît.

**Une seule requête, deux jointures.** Les groupes vivants du viewer, puis les gens vivants de ces
groupes — et l'année ne figure pas dans le `SELECT`. Ce n'est pas une précaution rhétorique : ce
qui n'est pas lu ne peut pas fuir dans un log, une trace, ou un DTO écrit trop vite.

`referent_of` délègue à la cascade du moteur de veille (`ResolveReferent`) plutôt que de relire
le responsable du groupe : le référent est un **pointeur calculé**, et le J-1 doit suivre la même
définition partout. Une seconde définition du mot « référent » aurait divergé dans six mois.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.groups.domain.membership import GroupMembershipStatus
from app.contexts.groups.infrastructure.persistence.models import GroupMembershipModel
from app.contexts.iam.application.birthdays import BirthdayDirectory, BirthdayStore
from app.contexts.iam.infrastructure.persistence.models import AccountModel

_LIVE_MEMBERSHIP = GroupMembershipStatus.ACTIVE.value


class SqlBirthdayStore(BirthdayStore):
    """Quatre colonnes sur le compte. Pas de table, pas d'historique : une date de naissance ne
    change pas, et si elle change c'est qu'elle était fausse."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_birthday(
        self, *, account_id: UUID, day: int, month: int, year: int | None, scope: str
    ) -> None:
        await self._session.execute(
            update(AccountModel)
            .where(AccountModel.id == account_id)
            .values(
                birth_day=day, birth_month=month, birth_year=year, birthday_scope=scope
            )
        )


class SqlBirthdayDirectory(BirthdayDirectory):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def candidates(self, *, viewer_account_id: UUID, tenant_id: UUID) -> list:
        mine = select(GroupMembershipModel.group_id).where(
            GroupMembershipModel.account_id == viewer_account_id,
            GroupMembershipModel.tenant_id == tenant_id,
            GroupMembershipModel.status == _LIVE_MEMBERSHIP,
        )
        stmt = (
            select(
                AccountModel.id,
                AccountModel.first_name,
                AccountModel.last_name,
                AccountModel.birth_day,
                AccountModel.birth_month,
                # **`birth_year` n'est pas dans le SELECT.** L'âge de quelqu'un n'est pas une
                # donnée d'église : il ne sort pas de la base, donc il ne peut sortir de nulle part.
                AccountModel.birthday_scope,
            )
            .join(GroupMembershipModel, GroupMembershipModel.account_id == AccountModel.id)
            .where(
                GroupMembershipModel.tenant_id == tenant_id,
                GroupMembershipModel.status == _LIVE_MEMBERSHIP,
                GroupMembershipModel.group_id.in_(mine),
                AccountModel.birth_day.is_not(None),
            )
            .distinct()
        )
        return [tuple(row) for row in (await self._session.execute(stmt)).all()]

    async def referent_of(self, account_id: UUID, tenant_id: UUID) -> UUID | None:
        # Import local : le moteur de veille importe déjà Groupes, et le remonter en tête de
        # module referme la boucle d'imports qui empêchait l'application de démarrer.
        from app.contexts.watch.interface.dependencies import build_referents

        referent = await build_referents(self._session).execute(
            person_id=account_id, tenant_id=tenant_id, at=datetime.now(UTC)
        )
        return referent.referent_person_id if referent is not None else None
