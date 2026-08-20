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


# --------------------------------------------------------------- le corps qu'on ne déclare pas
#
# Deux routes reçoivent un **fichier** — un PDF ou un PPTX déposé comme sermon, une image de
# marque — et le lisent en corps brut, sans modèle Pydantic. FastAPI ne peut pas le deviner :
# l'opération sort donc **sans `requestBody`**, et le contrat annonce une route qu'on appelle
# sans rien envoyer.
#
# Ce n'est pas cosmétique. Un client généré depuis ce contrat ne sait pas quoi poster, et la
# prochaine route de ce genre — celle qui recevra l'audio d'une prédication — héritera du même
# silence, avec la reprise et le découpage par-dessus.

_LECTURE_BRUTE = "read_body_capped"


def _fonctions_a_corps_brut() -> set[str]:
    """Le nom des fonctions de route qui lisent elles-mêmes le corps de la requête.

    On lit **la source de la fonction**, pas la signature : un paramètre `Request` sert aussi à
    lire une en-tête ou une adresse, et le compter ferait rougir des routes sans corps. L'appel
    à `read_body_capped`, lui, ne laisse aucun doute.

    ⚠️ **On ne passe pas par `app.routes`.** L'application monte ses routeurs en différé
    (`_IncludedRouter`) : à la racine il n'y a que huit entrées, et les chemins des routes
    internes sont relatifs à leur préfixe. On descend donc dans les routeurs d'origine, et on
    rejoint le contrat par l'`operationId`, que FastAPI dérive du nom de la fonction.
    """
    import ast
    import inspect
    import textwrap

    from fastapi.routing import APIRoute

    from app.main import app as application

    def descendre(routeur, vues: list) -> list:
        for route in getattr(routeur, "routes", []):
            if isinstance(route, APIRoute):
                vues.append(route)
            else:
                interne = getattr(route, "original_router", None) or getattr(route, "app", None)
                if interne is not None:
                    descendre(interne, vues)
        return vues

    def lit_le_corps(fonction, profondeur: int = 1) -> bool:
        """La fonction lit-elle le corps, elle-même ou par une aide de son module ?

        ⚠️ **Un saut, et il en faut un.** `PUT /media` délègue à `_do_upload`, où vit la
        lecture bornée : s'arrêter à la fonction de route laisserait passer la seule autre
        route à corps brut du dépôt — et le test aurait l'air de marcher."""
        try:
            source = inspect.getsource(fonction)
        except (OSError, TypeError):  # pragma: no cover — fonction sans source lisible
            return False

        if _LECTURE_BRUTE in source:
            return True
        if profondeur <= 0:
            return False

        appels = {
            noeud.func.id
            for noeud in ast.walk(ast.parse(textwrap.dedent(source)))
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
        }
        portee = getattr(fonction, "__globals__", {})

        return any(
            callable(portee.get(appel)) and lit_le_corps(portee[appel], profondeur - 1)
            for appel in appels
        )

    return {
        route.endpoint.__name__
        for route in descendre(application, [])
        if lit_le_corps(route.endpoint)
    }


def _operations_de(nom: str) -> list[tuple[str, str, dict]]:
    """Les opérations du contrat qui viennent de cette fonction."""
    return [
        (methode, chemin, operation)
        for chemin, operations in _SPEC["paths"].items()
        for methode, operation in operations.items()
        if isinstance(operation, dict)
        and operation.get("operationId", "").startswith(nom)
    ]


def test_la_garde_voit_bien_les_routes_a_corps_brut():
    """Le témoin fautif, comme pour le résumé fabriqué.

    Une garde qui ne trouve aucun sujet passe au vert sans rien vérifier — c'est exactement
    ainsi que la garde du `summary` a promis pendant des mois d'attraper « la première
    omission »."""
    fonctions = _fonctions_a_corps_brut()

    assert fonctions, (
        "Aucune route ne lit de corps brut : soit le dépôt a changé, soit la détection est "
        "cassée. Dans les deux cas, le test suivant ne prouve plus rien."
    )
    assert all(_operations_de(nom) for nom in fonctions), (
        f"Une de ces fonctions n'est pas retrouvée dans le contrat : {sorted(fonctions)}. "
        "L'appariement par `operationId` a cassé."
    )


def test_une_route_qui_lit_un_corps_le_declare():
    """**Ce qu'on envoie fait partie du contrat.**

    Sans `requestBody`, Swagger affiche un bouton « Execute » sans champ, et un client généré
    poste une requête vide. La route existe, elle est documentée, et elle est inutilisable."""
    muettes = [
        f"{methode.upper()} {chemin}"
        for nom in _fonctions_a_corps_brut()
        for methode, chemin, operation in _operations_de(nom)
        if not operation.get("requestBody")
    ]

    assert not muettes, (
        f"Ces routes lisent un corps brut sans le déclarer : {sorted(muettes)}. "
        "Déclarez les types acceptés avec `openapi_extra={'requestBody': …}` — le contrat doit "
        "dire ce qu'il reçoit, pas seulement ce qu'il rend."
    )
