"""Le catalogue tient debout tout seul — même famille de garde que `test_schema_integrity`.

Une traduction ne casse rien bruyamment : elle **manque**. Une clé sans entrée anglaise, un
`{title}` oublié dans la version anglaise, un paramètre inventé côté français — rien de tout cela
ne lève à l'import, et rien ne se voit en relecture. Ça se voit sur le téléphone d'un membre
d'Abidjan, un dimanche soir, sous la forme d'une notification vide ou d'une push qui n'est jamais
partie.

Ce fichier est ce qui rattrape ces trois-là avant qu'elles n'arrivent là-bas.
"""

import re

import pytest

from app._shared.domain.locale import Locale
from app._shared.messages import CATALOG, MessageKey, render

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _params_of(message) -> set[str]:
    return set(_PLACEHOLDER.findall(message.title)) | set(_PLACEHOLDER.findall(message.body))


@pytest.mark.parametrize("key", list(MessageKey), ids=lambda k: k.value)
def test_chaque_cle_parle_toutes_les_langues(key):
    """Une entrée incomplète est une notification muette pour la moitié des lecteurs."""
    assert set(CATALOG[key]) == set(Locale), f"« {key.value} » ne parle pas toutes les langues"


@pytest.mark.parametrize("key", list(MessageKey), ids=lambda k: k.value)
def test_les_langues_dune_cle_attendent_les_memes_parametres(key):
    """Le piège vrai : une traduction qui oublie `{title}` rend une phrase amputée, et une qui
    en invente un fait échouer le rendu — donc taire la push, pour cette langue seulement."""
    expected = None
    for locale, message in CATALOG[key].items():
        found = _params_of(message)
        if expected is None:
            expected = found
            continue
        assert found == expected, f"« {key.value} » : {locale} n'attend pas les mêmes paramètres"


@pytest.mark.parametrize("key", list(MessageKey), ids=lambda k: k.value)
def test_aucune_entree_nest_vide(key):
    for message in CATALOG[key].values():
        assert message.title.strip() and message.body.strip()


def test_le_catalogue_couvre_exactement_les_cles_declarees():
    """Ni clé orpheline dans l'énumération, ni entrée sans clé."""
    assert set(CATALOG) == set(MessageKey)


def test_le_contenu_humain_ressort_intact():
    """La frontière du chantier, vérifiée : Dorea ne retouche pas ce qu'un humain a écrit."""
    written_by_a_human = "Réunion des jeunes — « on se retrouve »"

    rendered = render(MessageKey.EVENT_PUBLISHED, Locale.EN, {"title": written_by_a_human})

    assert written_by_a_human in rendered.body


def test_une_langue_absente_retombe_sur_le_defaut_sans_lever(monkeypatch):
    """Ne devrait pas arriver (les tests ci-dessus l'interdisent), mais une clé muette vaut
    mieux qu'une exception sur le chemin d'une notification."""
    key = MessageKey.APPOINTMENT_CONFIRMED
    monkeypatch.setitem(CATALOG, key, {Locale.FR: CATALOG[key][Locale.FR]})

    assert render(key, Locale.EN).title == "Rendez-vous confirmé"
