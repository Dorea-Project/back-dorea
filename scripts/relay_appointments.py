r"""Runner du relais des rendez-vous — reprend ce qui attend, puis sort.

Process **one-shot** (même patron que `dispatch_notifications`) : un cron externe l'invoque.
Chaque invocation parcourt les églises, relaie ce qui a dépassé le délai, honore les retraits
`DO_NOT_CONTACT`, et remonte à l'admin les demandes que personne ne peut reprendre.

**Une demande sans réponse ne reste jamais silencieuse** — c'est tout l'objet de ce script.

Usage :  python -m scripts.relay_appointments
Cron (Linux, toutes les heures) :
    0 * * * * cd /srv/dorea && .venv/bin/python -m scripts.relay_appointments
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.contexts.appointments.interface.dependencies import build_relay
from app.contexts.tenant.infrastructure.persistence.models import TenantModel
from app.core.database import async_session_factory


async def main() -> None:
    async with async_session_factory() as session:
        tenants = (await session.execute(select(TenantModel.id))).scalars().all()
        relay = build_relay(session)
        totals = {"examined": 0, "relayed": 0, "gaps": 0, "withdrawn": 0}
        for tenant_id in tenants:
            report = await relay.execute(tenant_id=tenant_id)
            totals["examined"] += report.examined
            totals["relayed"] += report.relayed
            totals["gaps"] += report.gaps
            totals["withdrawn"] += report.withdrawn
        await session.commit()

    print(
        f"Relais : {totals['examined']} demandes examinées, {totals['relayed']} relayées, "
        f"{totals['withdrawn']} closes sur retrait, {totals['gaps']} défauts remontés."
    )


if __name__ == "__main__":
    asyncio.run(main())
