"""La **carte publique** d'un événement — le lien qu'on partage hors de Dorea.

C'est la contrepartie de la cadence. On ne peut annoncer qu'un événement par semaine, parce que
publier fait sonner tous les téléphones de l'église ; en échange, **le lien du vôtre se partage
autant que vous voulez** — WhatsApp, Facebook, un affichage devant le temple. Ce qui est rationné
est la *notification*, jamais la diffusion.

Sans elle, la cadence serait une mutilation : celui qui organise un repas ne pourrait plus inviter
personne pendant sept jours. Avec elle, il invite mieux — les gens qu'il connaît, là où ils sont
déjà, au lieu de compter sur une notification que quarante personnes reçoivent et que trois
lisent.

**Le lien est la clé**, comme la carte de Mission : l'identifiant est un UUID, il n'est ni
devinable ni énumérable, et le posséder suffit. Aucune authentification, aucun compte.

**Ce que cette page ne montre pas** — et c'est la moitié de sa conception :

- **personne.** Ni l'organisateur, ni les participants, ni le moindre compte. Un événement est un
  *happening*, pas un annuaire ; celui qui reçoit le lien vient à un repas, il n'entre pas dans
  l'église ;
- **aucun nombre.** Ni vues, ni intéressés, ni confirmés. Le tableau de bord appartient à
  l'organisateur, et un compteur public serait un score — l'invariant vaut aussi dehors ;
- **rien d'annulé ni de retiré.** Un lien vers un événement qui n'aura pas lieu ferait déplacer
  quelqu'un pour rien, et un événement retiré par la modération le resterait pour les membres tout
  en circulant librement à l'extérieur.
"""

from uuid import UUID

from fastapi import APIRouter

from app.contexts.events.interface.dependencies import GetPublicEventDep
from app.contexts.events.interface.schemas import PublicEventView

router = APIRouter()


@router.get(
    "/events/{event_id}",
    response_model=PublicEventView,
    summary="La carte d'un événement (public) — ce qu'on partage hors de Dorea",
)
async def public_event(event_id: UUID, query: GetPublicEventDep) -> PublicEventView:
    return PublicEventView.of(await query.execute(event_id=event_id))
