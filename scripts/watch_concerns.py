r"""Runner de la veille sur les inquiétudes signalées — passe, remonte ce qui traîne, puis sort.

Process **one-shot** (même patron que `relay_appointments`) : un cron externe l'invoque. Deux
passes, dans cet ordre, et l'ordre compte :

1. **L'escalade** — une inquiétude signalée il y a dix jours sans **aucun** contact remonte au
   pasteur, *à propos du responsable*. C'est la seule remontée du produit où l'escalade change de
   sujet : le pasteur n'a aucune base pour agir sur le membre, il sait seulement que quelqu'un a
   ressenti quelque chose.

2. **Le garde-fou** — celui qui signale beaucoup et contacte peu se décharge. Le tell est le
   **ratio**, jamais le volume : dix intuitions et dix contacts, c'est l'excellence, et un seuil
   sur le volume punirait exactement les meilleurs.

Les deux remontent comme un **besoin d'aide**, jamais comme un reproche — un responsable qui ne
tient pas ses engagements est le plus souvent un responsable débordé. Et chaque défaut n'est
consigné qu'une fois tant qu'il est ouvert : un rappel qui revient chaque nuit devient du bruit,
et le bruit se désapprend en trois semaines.

Usage :  python -m scripts.watch_concerns
Cron (Linux, une fois par jour) :
    30 6 * * * cd /srv/dorea && .venv/bin/python -m scripts.watch_concerns
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.contexts.tenant.infrastructure.persistence.models import TenantModel
from app.contexts.watch.interface.dependencies import (
    build_dumping_guard,
    build_escalate_concerns,
    build_fire_checks,
)
from app.core.database import async_session_factory


async def main() -> None:
    async with async_session_factory() as session:
        tenants = (await session.execute(select(TenantModel.id))).scalars().all()
        fire = build_fire_checks(session)
        escalate = build_escalate_concerns(session)
        guard = build_dumping_guard(session)

        fired = deferred = escalated = overloaded = 0
        for tenant_id in tenants:
            report = await fire.execute(tenant_id=tenant_id)
            fired += report.fired
            deferred += report.deferred
            escalated += len(await escalate.execute(tenant_id=tenant_id))
            overloaded += len(await guard.execute(tenant_id=tenant_id))
        await session.commit()

    print(
        f"Veille : {fired} échéance(s) tirée(s), {deferred} différée(s) par le garde "
        f"anti-orage, {escalated} engagement(s) non tenu(s) remonté(s), "
        f"{overloaded} responsable(s) probablement débordé(s)."
    )


if __name__ == "__main__":
    asyncio.run(main())
