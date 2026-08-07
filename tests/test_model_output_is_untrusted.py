"""DOREA-025 — la sortie d'un modèle est une entrée non fiable comme une autre.

`response_format={"type": "json_object"}` promet du **JSON**. Il ne promet ni la forme, ni les
types, ni la présence des clés. Un modèle qui répond `{"chapter": "trois"}`, une liste au lieu
d'un objet, ou du texte tronqué faisait lever le code — donc **500**, et un pasteur devant un
écran cassé un samedi soir.

Deux replis existaient déjà (`KeywordVerseResolver`, `KeywordSermonDigester`) : échouer
**doucement** vers eux est plus sûr que lever. Ces tests passent en revue les formes tordues
qu'un modèle produit réellement.
"""

import pytest

from app.contexts.mission.infrastructure.verse_resolver import _parse_reference
from app.contexts.sermon.infrastructure.digester import _from_json

_TORDUES = [
    pytest.param("pas du json du tout", id="texte brut"),
    pytest.param("", id="vide"),
    pytest.param("{tronqué", id="json tronque"),
    pytest.param("[1, 2, 3]", id="liste au lieu d'objet"),
    pytest.param('"une chaine"', id="chaine au lieu d'objet"),
    pytest.param("null", id="null"),
    pytest.param('{"found": true}', id="found sans les champs"),
    pytest.param(
        '{"found": true, "book": "Jean", "chapter": "trois", "verse": 16}',
        id="chapitre en lettres",
    ),
    pytest.param(
        '{"found": true, "book": "Jean", "chapter": [3], "verse": 16}',
        id="chapitre en liste",
    ),
    pytest.param('{"found": true, "book": "", "chapter": 3, "verse": 16}', id="livre vide"),
    pytest.param('{"found": true, "book": "Jean", "chapter": 0, "verse": 16}', id="chapitre zero"),
    pytest.param('{"found": true, "book": "Jean", "chapter": 3, "verse": -1}', id="verset negatif"),
]


@pytest.mark.parametrize("reponse", _TORDUES)
def test_aucune_reponse_tordue_ne_fait_lever_le_resolveur(reponse: str):
    """Rien ne lève, et rien n'est inventé : une forme douteuse rend `None`, pas un verset."""
    assert _parse_reference(reponse) is None


def test_une_reponse_correcte_passe():
    """Le jumeau légitime — la sévérité ne doit pas refuser ce qui est juste."""
    reference = _parse_reference('{"found": true, "book": "Jean", "chapter": 3, "verse": 16}')
    assert reference is not None
    assert (reference.book, reference.chapter, reference.verse) == ("Jean", 3, 16)


_DIGESTS_TORDUS = [
    pytest.param(None, id="null"),
    pytest.param([], id="liste"),
    pytest.param("texte", id="chaine"),
    pytest.param({"capsules": "pas une liste"}, id="capsules en chaine"),
    pytest.param({"capsules": ["une chaine", 42]}, id="capsules non-objets"),
    pytest.param({"questions": {"prompt": "objet au lieu de liste"}}, id="questions en objet"),
    pytest.param({"key_points": "pas une liste"}, id="points en chaine"),
]


@pytest.mark.parametrize("data", _DIGESTS_TORDUS)
def test_aucune_forme_tordue_ne_fait_lever_le_digesteur(data):
    """Ce qui n'est pas exploitable est ignoré — le digest sort vide, jamais en exception."""
    digest = _from_json(data)
    assert digest.capsules == () or all(c.body for c in digest.capsules)
    assert isinstance(digest.summary, str)


def test_le_digesteur_garde_ce_qui_est_bon_et_jette_le_reste():
    """Une capsule valide au milieu de déchets survit — on ne jette pas tout pour un intrus."""
    digest = _from_json(
        {
            "summary": "  La grâce  ",
            "key_points": ["un point", "", 3],
            "capsules": [{"title": "T", "body": "un corps"}, "intrus", {"body": ""}],
        }
    )
    assert digest.summary == "La grâce"
    assert len(digest.capsules) == 1
    assert digest.capsules[0].body == "un corps"
    assert "un point" in digest.key_points
