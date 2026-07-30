"""Route **Plateforme** du moteur de veille — la cadence, appelée par un cron externe.

Deux passes, écrites et testées depuis un moment, et jusqu'ici **injoignables** : elles ne
vivaient que dans un script. Un service qu'aucune surface n'atteint ne tourne nulle part.

1. **Les échéances** — ce qui est dû tombe, sous plafond anti-orage. C'est par là que le temps
   entre dans la veille : le worker écrit un `CHECK_FIRED` au ledger et ne touche à rien d'autre.
2. **L'escalade** — une inquiétude signalée il y a dix jours sans aucun contact remonte au
   pasteur, *à propos du responsable*. La seule remontée du produit où l'escalade change de sujet.
3. **Le garde-fou** — celui qui signale beaucoup et contacte peu se décharge. Le tell est le
   **ratio**, jamais le volume.
4. **La relève des retenus** — ce que le plafond avait retenu sort quand la place se libère.
   « Retenu ≠ perdu » n'est vrai que si quelque chose les relâche.
5. **Les groupes aveugles** — celui qui ne saisit aucune rencontre ne détecte personne, et son
   silence ressemble à la santé. Le défaut porte sur le groupe, jamais sur ses membres.

L'ordre compte : les échéances d'abord, pour que l'escalade voie l'état du jour et non celui
d'hier.

Gardée par le **jeton de service Plateforme** : c'est de l'infrastructure, pas une action
d'église. Le même code reste accessible par `python -m scripts.watch_concerns` — deux chemins,
une seule implémentation.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession
from app.contexts.tenant.infrastructure.persistence.models import TenantModel
from app.contexts.tenant.interface.dependencies import require_platform_token
from app.contexts.watch.interface.dependencies import (
    build_blind_groups,
    build_dumping_guard,
    build_escalate_concerns,
    build_fire_checks,
    build_release_held,
)

router = APIRouter(dependencies=[Depends(require_platform_token)])


class WatchRunResult(BaseModel):
    """Ce que la passe a **effectivement** consigné — jamais ce qu'elle a examiné.

    Les défauts déjà ouverts ne sont pas recomptés : un rappel qui revient chaque nuit devient du
    bruit, et le bruit se désapprend en trois semaines."""

    tenants: int
    fired: int  # échéances tombées, entrées au ledger
    # Dues mais retenues par le garde anti-orage. **Dites, jamais tues** : une passe qui
    # affiche « 20 tirées » en taisant les 180 restantes ressemble à une passe qui a tout fait.
    deferred: int
    escalated: int  # engagements non tenus remontés au pasteur
    overloaded: int  # responsables probablement débordés
    released: int  # cas retenus par le plafond que la place libérée laisse enfin sortir
    # Groupes dont aucune rencontre n'est saisie : ils ne détectent personne, et leur écran vide
    # ressemble à la santé. Le défaut porte sur le groupe, jamais sur ses membres.
    blind_groups: int
    # Ce qui reste retenu. Un arriéré permanent n'est pas un problème de plafond : c'est une
    # détection trop bavarde, et c'est le seuil qu'on remonte alors, jamais le plafond.
    still_held: int


@router.post(
    "/watch/run",
    response_model=WatchRunResult,
    summary="Passe de veille : échéances dues, escalade des engagements non tenus, garde-fou",
)
async def run(session: DbSession, tenant_id: UUID | None = None) -> WatchRunResult:
    # `tenant_id` optionnel : une église seule pour rejouer un cas précis, toutes par défaut.
    tenants = (
        [tenant_id]
        if tenant_id is not None
        else list((await session.execute(select(TenantModel.id))).scalars().all())
    )
    fire = build_fire_checks(session)
    escalate, guard = build_escalate_concerns(session), build_dumping_guard(session)
    release, blind = build_release_held(session), build_blind_groups(session)

    fired = deferred = escalated = overloaded = released = still_held = blind_groups = 0
    for each in tenants:
        report = await fire.execute(tenant_id=each)
        fired += report.fired
        deferred += report.deferred
        escalated += len(await escalate.execute(tenant_id=each))
        overloaded += len(await guard.execute(tenant_id=each))
        # En dernier : les échéances de la passe ont pu ouvrir des cas, et les clôtures de la
        # journée ont pu libérer de la place. On relâche d'après l'état du jour, pas celui d'hier.
        freed = await release.execute(tenant_id=each)
        released += freed.released
        still_held += freed.still_held
        blind_groups += (await blind.execute(tenant_id=each)).recorded

    return WatchRunResult(
        tenants=len(tenants), fired=fired, deferred=deferred,
        escalated=escalated, overloaded=overloaded,
        released=released, still_held=still_held, blind_groups=blind_groups,
    )
