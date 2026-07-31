"""Le régime de rodage d'une église, en base — et son défaut, qui n'est pas neutre.

**L'absence de ligne vaut `SHADOW`.** Ce n'est pas une commodité d'implémentation : c'est ce qui
garantit qu'aucune église, existante ou future, ne peut se mettre à parler par oubli. Un défaut
« émettre » aurait exigé qu'on pense à insérer une ligne au provisionnement, et le jour où quelqu'un
oublierait, une église découvrirait Dorea par un cas envoyé à un responsable qui ne l'attendait pas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.ports import RegimeStore
from app.contexts.watch.domain.regime import DEFAULT_REGIME, TenantRegime
from app.contexts.watch.infrastructure.persistence.models import TenantRegimeModel


class SqlRegimeStore(RegimeStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def regime_of(self, tenant_id: UUID) -> TenantRegime:
        stmt = select(TenantRegimeModel.regime).where(
            TenantRegimeModel.tenant_id == tenant_id
        )
        found = (await self._session.execute(stmt)).scalars().first()
        return TenantRegime(found) if found else DEFAULT_REGIME

    async def set_regime(
        self, *, tenant_id: UUID, regime: TenantRegime, at: datetime, by_account_id: UUID
    ) -> None:
        row = (
            await self._session.execute(
                select(TenantRegimeModel).where(TenantRegimeModel.tenant_id == tenant_id)
            )
        ).scalars().first()
        if row is None:
            self._session.add(
                TenantRegimeModel(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    regime=regime.value,
                    since=at,
                    changed_by_account_id=by_account_id,
                )
            )
        else:
            row.regime = regime.value
            row.since = at
            row.changed_by_account_id = by_account_id
        await self._session.flush()
