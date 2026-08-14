"""Le délai maximum du modèle — **la garde qui manquait là où tout le reste était prévu**.

Cet adaptateur est bâti sur une phrase : *« une panne du modèle n'est jamais une panne
d'Urim »*. Le repli déterministe reprend, et le pasteur ne voit pas la différence.

🐛 **Mais le repli ne se déclenche que sur une ERREUR.** Un appel qui *pend* n'échoue pas : il
attend. Mesuré le 2026-08-14 sur une préparation réelle — résolveur construit à 15:35:44,
réponse à 16:10:35, **un seul appel entre les deux**. Trente-cinq minutes, sans une ligne de
journal, et le pasteur attend avec la requête.

Deux propriétés, et la seconde est celle qui rend la première utile :

1. au-delà du délai, l'appel rend `None` — donc le chemin déterministe reprend ;
2. l'échec est **compté et nommé**, parce qu'un mode de panne invisible est un mode de panne
   qui revient.
"""

from __future__ import annotations

import asyncio

import pytest

from app.contexts.urim.adapters import mistral as adaptateur

pytestmark = pytest.mark.asyncio


class _ClientQuiPend:
    """Un client qui ne répond jamais — exactement ce qui a figé la préparation réelle."""

    def __init__(self) -> None:
        self.chat = self
        self.appels = 0

    async def complete_async(self, **_kwargs):
        self.appels += 1
        await asyncio.sleep(3600)
        raise AssertionError("jamais atteint")


class _ClientQuiRepond:
    def __init__(self) -> None:
        self.chat = self

    async def complete_async(self, **_kwargs):
        class _Message:
            content = '{"ok": true}'

        class _Choix:
            message = _Message()

        class _Reponse:
            choices = (_Choix(),)
            usage = None

        return _Reponse()


def _assistant(client) -> adaptateur.MistralAssistant:
    """Un assistant sans SDK — on remplace le transport, on garde la logique."""
    objet = object.__new__(adaptateur.MistralAssistant)
    objet._client = client
    objet._model = "essai"
    objet.echecs = 0
    return objet


async def test_un_appel_qui_pend_rend_none_au_lieu_d_attendre(monkeypatch):
    """**La propriété qui coûtait trente-cinq minutes.** Sans elle, rien ne coupe : ni le SDK
    (dont on ne peut pas vérifier les paramètres — `Mistral.__init__` expose `*args`), ni
    l'appelant, qui attend une réponse ou une erreur et n'en reçoit aucune."""
    monkeypatch.setattr(adaptateur, "DELAI_MODELE", 0.05)
    client = _ClientQuiPend()
    assistant = _assistant(client)

    rendu = await asyncio.wait_for(
        assistant.demander("système", "texte", etiquette="essai"), 5
    )

    assert rendu is None
    assert client.appels == 1


async def test_le_delai_depasse_est_compte_comme_un_echec():
    """⚠️ **Un mode de panne invisible est un mode de panne qui revient.**

    `echecs` est ce que l'appelant photographie avant et après pour décider s'il garde un
    mémo. Un délai dépassé qui ne s'y compterait pas ferait enregistrer une préparation vide
    **pour toujours** — c'est le raisonnement écrit sur le compteur lui-même."""
    import app.contexts.urim.adapters.mistral as module

    original = module.DELAI_MODELE
    module.DELAI_MODELE = 0.05
    try:
        assistant = _assistant(_ClientQuiPend())
        await assistant.demander("système", "texte")
        assert assistant.echecs == 1
    finally:
        module.DELAI_MODELE = original


async def test_un_appel_normal_n_est_pas_coupe():
    """Le couple : la garde ne doit rien casser de ce qui répond."""
    assistant = _assistant(_ClientQuiRepond())
    assert await assistant.demander("système", "texte") == '{"ok": true}'
    assert assistant.echecs == 0


async def test_le_delai_est_large_devant_les_appels_reels():
    """Les appels mesurés tiennent en 2 à 8 secondes. Un délai trop court couperait une
    lenteur réelle et ferait perdre au pasteur l'assistance qu'il attend — la garde doit
    trancher une connexion morte, pas une journée chargée."""
    assert adaptateur.DELAI_MODELE >= 30
