r"""Runner du fan-out — dispatche les notifications planifiées dues, puis sort.

Process **one-shot** (pas de boucle en process, cf. `docs/Notifications_Push.md`) : un
**cron externe** l'invoque périodiquement. Chaque invocation **draine** la file (plusieurs passes
de `DispatchDueNotifications.run()` tant qu'un lot plein revient) puis termine — un arriéré se vide
en une invocation au lieu d'attendre un tick par lot.

C'est le pendant « même hôte » de la route Plateforme `POST /platform/notifications/dispatch`
(qui, elle, sert le déclenchement manuel/distant, gardée par le jeton de service). Ici : accès DB
direct, ni HTTP ni jeton.

Usage :  python -m scripts.dispatch_notifications
Cron (Linux, chaque minute) :
    * * * * * cd /srv/dorea && .venv/bin/python -m scripts.dispatch_notifications
Windows (Planificateur de tâches) — déclencheur « répéter toutes les 1 min », action :
    powershell -c ".\.venv\Scripts\python.exe -m scripts.dispatch_notifications"
"""

from __future__ import annotations

import asyncio
import sys

from app.contexts.notifications.application.dispatch import DispatchDueNotifications
from app.contexts.notifications.interface.dependencies import get_dispatch
from app.core.database import async_session_factory, engine

BATCH = 100  # taille d'un lot (aligne le `limit` de run())
MAX_PASSES = 10_000  # garde-fou anti-boucle (chaque passe réduit strictement la file des dus)


async def drain(
    dispatch: DispatchDueNotifications, *, batch: int = BATCH, max_passes: int = MAX_PASSES
) -> int:
    """Enchaîne les passes jusqu'à ce qu'un lot **non plein** revienne (file drainée)."""
    total = 0
    for _ in range(max_passes):
        sent = await dispatch.run(limit=batch)
        total += sent
        if sent < batch:  # dernier lot incomplet → plus rien de dû
            break
    return total


async def main() -> None:
    # La console Windows est en cp1252 par défaut → forcer UTF-8 pour l'affichage.
    sys.stdout.reconfigure(encoding="utf-8")
    async with async_session_factory() as session:
        total = await drain(get_dispatch(session))
        await session.commit()
    await engine.dispose()
    print(f"Notifications dispatchées : {total}")


if __name__ == "__main__":
    asyncio.run(main())
