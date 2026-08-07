"""Ce que Swagger doit toujours raconter — vérifié, pas espéré.

Trente-deux tags s'affichaient bruts : rien ne disait à quelle surface ils appartenaient, ni ce
que le contexte faisait dans le produit. Un intégrateur devait deviner que `platform:watch` est
un cron et `mission:public` une page sans authentification.

La correction est facile à écrire une fois et impossible à maintenir de bonne volonté : le
prochain contexte qui ouvre une route ajoutera son tag et oubliera sa phrase, et personne ne le
verra — un tag sans description ne casse rien, il rend juste la route inutilisable de
l'extérieur. **D'où ces trois tests plutôt qu'une consigne.**
"""

from app.api.openapi import TAGS
from app.main import app

_SPEC = app.openapi()

#: Les tags réellement portés par une route.
_UTILISES: set[str] = {
    tag
    for operations in _SPEC["paths"].values()
    for operation in operations.values()
    if isinstance(operation, dict)
    for tag in operation.get("tags", [])
}

_DOCUMENTES: dict[str, str] = {entree["name"]: entree["description"] for entree in TAGS}


def test_chaque_tag_servi_porte_une_description():
    """Une route dont le tag n'est pas documenté est une route qu'on ne sait pas appeler."""
    muets = sorted(_UTILISES - set(_DOCUMENTES))

    assert not muets, (
        f"Ces tags servent des routes sans être décrits dans `app/api/openapi.py` : {muets}. "
        "Une phrase qui dit ce que le contexte **fait**, jamais ce qu'il est techniquement."
    )


def test_aucune_description_ne_survit_a_ses_routes():
    """Le sens inverse, qui se périme en silence : un tag documenté que plus rien ne sert.

    Il paraît inoffensif — il ne l'est pas. Swagger affiche une section vide, et le lecteur
    conclut que la fonctionnalité existe."""
    orphelins = sorted(set(_DOCUMENTES) - _UTILISES)

    assert not orphelins, (
        f"Ces tags sont décrits mais plus aucune route ne les porte : {orphelins}. "
        "Retirer la description, ou retrouver la route perdue."
    )


def test_chaque_route_annonce_ce_qu_elle_fait():
    """Sans `summary`, Swagger affiche le chemin nu — et le chemin ne dit pas l'intention.

    ⚠️ **Il faut comparer au nom de la fonction, pas à la chaîne vide.** FastAPI *fabrique* un
    résumé quand on n'en donne pas : `def liste_des_groupes()` devient `« Liste Des Groupes »`.
    La version précédente de ce test cherchait un `summary` vide — il n'y en a jamais, et le test
    ne pouvait pas échouer. Il promettait pourtant d'attraper « la première omission ».

    C'est la troisième garde du dépôt trouvée **vraie par construction** (après
    `FORBIDDEN_FOR_STAGES` et `confessionnel_borne` en SQLite), et les trois se ressemblent :
    la garde regardait un état que le système ne produit jamais.
    """
    from fastapi.routing import APIRoute

    auto = sorted(
        f"{sorted(route.methods)[0]} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.summary in (None, "", route.name.replace("_", " ").title())
    )

    assert not auto, (
        f"Ces routes n'ont pas de résumé écrit — Swagger affiche le nom de la fonction : {auto}. "
        "Une phrase qui dit ce que la route **fait pour quelqu'un**, pas ce qu'elle appelle."
    )


def test_le_resume_fabrique_par_fastapi_est_bien_detecte():
    """Le témoin fautif — sans lui, le test précédent redeviendrait vrai par vacuité le jour où
    quelqu'un « simplifierait » la comparaison.

    On prouve ici que FastAPI remplit bien le trou tout seul : c'est **ce comportement** qui rend
    la garde naïve inopérante, et il doit rester visible dans le fichier qui en dépend."""
    from fastapi import FastAPI

    temoin = FastAPI()

    @temoin.get("/x")
    def une_route_sans_resume():  # pragma: no cover — jamais appelée
        return {}

    fabrique = temoin.openapi()["paths"]["/x"]["get"]["summary"]

    assert fabrique == "Une Route Sans Resume"  # non vide : la garde naïve passait


def test_les_trois_surfaces_sont_expliquees_en_tete():
    """La description d'en-tête porte la seule chose qu'aucune route ne peut dire d'elle-même :
    qui garde quoi."""
    entete = _SPEC["info"]["description"]

    for surface in ("/api/mobile", "/api/backoffice", "le code est l'autorisation"):
        assert surface in entete
