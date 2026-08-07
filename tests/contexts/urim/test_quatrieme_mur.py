"""**Le quatrième mur — `plan ↮ modèle`** (S29), rendu exécutable avant le module qu'il garde.

Les trois autres murs séparent des contextes. Celui-ci sépare le **module** du **modèle**, et il
est le plus fragile des quatre — pas parce qu'il serait mal posé, mais parce que le transgresser
paraît serviable :

> *« Le module lit déjà la préparation, autant la passer au modèle pour qu'il comprenne mieux. »*

S'il reçoit le plan, le modèle décrira le sermon comme ayant **suivi** le plan. Il fabrique la
conformité — et détruit précisément ce que le Retour existe pour montrer.

---

`urim/capture/` n'existe pas encore. Ces tests seraient donc **vrais par vacuité**, exactement
comme les quatre tests d'architecture l'étaient tant que `PIPELINE` était vide. Et on connaît
maintenant le prix de cette vacuité : le premier étage réel a exposé un bug dormant dans le test
le plus important du dépôt.

D'où la même parade que le socle : **chaque test est doublé d'une preuve sur un témoin
volontairement fautif.** C'est le *détecteur* qui est testé, pas le vide.
"""

import pytest

from app.contexts.urim.capture import FORBIDDEN_IN_MODEL_PROMPT
from tests.contexts.urim.test_engine_architecture import attribute_names_read


class _PromptHonnete:
    """Ce qu'un constructeur de prompt a le droit de lire : le transcrit, et rien du plan."""

    def build(self, capture, deps):
        segments = capture.transcript_segments
        versets = capture.cited_verses
        return f"{segments} {versets}"


class _PromptQuiDonneLePlan:
    """Le témoin fautif — celui qu'un développeur bien intentionné écrira un jour.

    Il ne triche pas : il fait exactement ce qui *paraît* utile. C'est pour ça qu'il faut un test
    et pas une phrase dans une spec."""

    def build(self, capture, deps):
        segments = capture.transcript_segments
        plan = deps.preparation  # ⛔ le plan entre dans le contexte du modèle
        return f"{segments} {plan}"


def test_la_sonde_attrape_un_constructeur_qui_donne_le_plan_au_modele():
    """**Le détecteur, prouvé sur un cas réel.** Sans ce test, tous les autres seraient creux."""
    lus = attribute_names_read(_PromptQuiDonneLePlan.build)

    assert lus & FORBIDDEN_IN_MODEL_PROMPT


def test_la_sonde_laisse_passer_un_constructeur_honnete():
    """La sévérité ne doit pas refuser ce qui est juste : lire le transcrit est le travail même
    du module."""
    lus = attribute_names_read(_PromptHonnete.build)

    assert not (lus & FORBIDDEN_IN_MODEL_PROMPT)


def test_aucun_constructeur_de_prompt_de_la_capture_ne_lit_la_preparation():
    """Le vrai test — **vide aujourd'hui, et c'est dit**.

    Il balaiera `urim/capture/` dès que le module existera. Tant qu'il n'a rien à balayer, les
    deux tests ci-dessus portent la valeur : ils garantissent que le jour où le module arrive, la
    sonde qui l'attend fonctionne."""
    from app.contexts.urim import capture

    constructeurs = [
        objet
        for nom in dir(capture)
        if not nom.startswith("_")
        for objet in [getattr(capture, nom)]
        if callable(objet) and hasattr(objet, "build")
    ]

    for constructeur in constructeurs:
        lus = attribute_names_read(constructeur.build)
        interdits = lus & FORBIDDEN_IN_MODEL_PROMPT
        assert not interdits, (
            f"{constructeur.__name__} passe {sorted(interdits)} au modèle — "
            "le modèle ne voit jamais la préparation (S29)."
        )


def test_la_liste_des_interdits_n_est_jamais_vide():
    """Un garde dont la liste se vide ne garde plus rien, et il le fait **en vert**.

    Le même piège que le test qui itérait un `PIPELINE` vide : la suite reste au vert pendant que
    la protection a disparu."""
    assert FORBIDDEN_IN_MODEL_PROMPT


@pytest.mark.parametrize("indispensable", ["preparation", "plan"])
def test_les_deux_noms_qui_ne_doivent_jamais_sortir_de_la_liste(indispensable: str):
    """Les autres noms sont des variantes ; ces deux-là **sont** la règle.

    Les retirer viderait le mur en laissant le test au vert — c'est pourquoi ils sont épinglés
    nommément plutôt que comptés."""
    assert indispensable in FORBIDDEN_IN_MODEL_PROMPT
