"""R0 — l'alias déprécié du sujet de reconnaissance.

Le geste a déménagé de `sermon` vers `watch`, où le fait, l'interpreter et la source `COMPANION`
étaient déjà. Le **client mobile est dans un autre dépôt** et ne se déploie pas en même temps que
celui-ci : couper l'ancienne URL d'un coup ferait disparaître sans prévenir la seule parole du
membre qui dise que ça va.

D'où un alias — et d'où ce fichier, parce qu'un alias non testé est un alias qu'on casse au
premier nettoyage d'imports.

## Ce que ces tests tiennent, et pourquoi ils sont structurels

Ils n'appellent pas la base. Ce qu'il faut prouver n'est pas qu'un dépôt de reconnaissance
fonctionne — trois tests le font déjà dans `tests/contexts/watch/test_gratitude_life_sign.py` —
mais que les deux URL désignent **le même geste**. Une seconde implémentation qui dérive est le
mode de panne d'un alias, et c'est celui-là qu'on veut voir rougir.

Deux points d'observation, et chacun a sa raison :

- **l'OpenAPI** pour les URL et la dépréciation, parce que c'est littéralement ce que le client
  mobile consomme. `app.routes` ne convient pas : cette version de FastAPI y garde les routeurs
  inclus enveloppés au lieu de les aplatir, et un test qui lit cette structure casserait à la
  prochaine montée de version sans que rien du produit ait bougé ;
- **les routeurs eux-mêmes** pour l'identité des classes et de la dépendance, que l'OpenAPI ne
  peut pas dire — il ne rend que des noms, et deux classes homonymes s'y ressemblent.

⚠️ **Ce fichier disparaît avec l'alias** (R4, ou dès que le client mobile appelle la nouvelle
URL). Un alias qu'on oublie de retirer n'est plus une transition, c'est une seconde API.
"""

from app.contexts.sermon.interface.mobile_router import router as sermon_router
from app.contexts.watch.interface.mobile_router import router as watch_router
from app.contexts.watch.interface.schemas import (
    DepositGratitudeBody,
    GratitudeDepositedView,
)
from app.main import create_app

ANCIENNE = "/api/mobile/sermons/tenants/{tenant_id}/gratitude"
NOUVELLE = "/api/mobile/watch/tenants/{tenant_id}/gratitude"
CHEMIN_RELATIF = "/tenants/{tenant_id}/gratitude"


def _route(router):
    """La route de la reconnaissance dans un routeur — et une seule."""
    trouvees = [r for r in router.routes if getattr(r, "path", None) == CHEMIN_RELATIF]
    assert len(trouvees) == 1, f"{len(trouvees)} routes gratitude au lieu d'une"
    return trouvees[0]


def test_les_deux_url_existent_pendant_la_transition():
    """La nouvelle est la vraie ; l'ancienne survit le temps que le client suive."""
    chemins = create_app().openapi()["paths"]
    assert NOUVELLE in chemins, (
        "la route d'arrivée n'est pas publiée — le déménagement est à moitié fait"
    )
    assert ANCIENNE in chemins, (
        "l'alias a disparu : un client mobile encore déployé perdrait le dépôt de reconnaissance "
        "sans aucun message"
    )


def test_l_ancienne_est_marquee_depreciee():
    """Le seul signal que le client reçoit **avant** la coupure, et il passe par l'OpenAPI.

    Sans lui, l'alias est indiscernable d'une route pérenne, et personne côté mobile n'a de raison
    de migrer avant que ça casse."""
    chemins = create_app().openapi()["paths"]
    assert chemins[ANCIENNE]["post"].get("deprecated") is True
    assert chemins[NOUVELLE]["post"].get("deprecated", False) is False


def test_les_deux_url_decrivent_le_meme_geste():
    """**Le mode de panne d'un alias, c'est la divergence** — pas l'absence.

    Deux handlers qui recopient la même logique se mettent à différer au premier correctif appliqué
    d'un seul côté, et le client voit deux contrats pour un même geste. On compare donc les
    **classes elles-mêmes**, pas leurs noms : deux schémas homonymes dans deux modules passeraient
    une comparaison par nom sans être le même contrat."""
    ancienne, nouvelle = _route(sermon_router), _route(watch_router)

    assert ancienne.body_field.field_info.annotation is DepositGratitudeBody
    assert nouvelle.body_field.field_info.annotation is DepositGratitudeBody
    assert ancienne.response_model is GratitudeDepositedView
    assert nouvelle.response_model is GratitudeDepositedView


def test_l_alias_ne_recable_pas_sa_propre_commande():
    """Il emprunte la dépendance de `watch` — sinon il y aurait deux assemblages à maintenir.

    Même raison qu'au-dessus, un cran plus bas : un second `get_...` finirait par recevoir un
    correctif que l'autre n'a pas, et les deux URL n'écriraient plus le même fait."""
    from app.contexts.watch.interface.dependencies import get_deposit_gratitude

    for route in (_route(sermon_router), _route(watch_router)):
        appels = {d.call for d in route.dependant.dependencies}
        assert get_deposit_gratitude in appels


def test_sermon_n_a_plus_de_commande_de_reconnaissance():
    """Le déménagement est **complet**, pas dupliqué.

    Tant que l'ancien module existe, un import distrait le ressuscite — et on se retrouve avec deux
    émetteurs pour un fait dont le registre n'en attend qu'un."""
    import importlib

    try:
        importlib.import_module("app.contexts.sermon.application.commands.gratitude")
    except ModuleNotFoundError:
        return
    raise AssertionError(
        "`sermon.application.commands.gratitude` existe encore : la commande a été copiée, "
        "pas déplacée"
    )
