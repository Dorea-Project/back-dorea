"""Ce qu'une ligne **générée** n'a pas le droit de dire — et ce qu'un humain garde.

La règle est asymétrique, et c'est tout son intérêt. Le détecteur d'écarts avait mis en tête de
sa file la mise en garde de Romains 8:1-11 — l'une des six posées à la main, celle qui cite le
Texte Reçu. Elle est juste : un relecteur peut consulter un apparat critique et en répondre. Le
modèle, non.

Le troisième cas est celui qui a failli coûter cher : la *négation de doctrine* n'est **pas**
refusée, parce que huit des neuf lignes qu'elle attrapait étaient justes.
"""

from __future__ import annotations

import pytest

from app.contexts.urim.application.curation import (
    SIGNATAIRE_IA,
    verifier_forme_machine,
)
from app.contexts.urim.domain.errors import CurationInvalideError


@pytest.mark.parametrize(
    "corps",
    [
        "Le v. 1 est concerné par une variante textuelle : certains manuscrits ajoutent…",
        "L'apparat critique signale ici une leçon divergente.",
        "Selon les Pères, ce passage annonce la résurrection.",
        "La confession de La Rochelle tranche la question en ce sens.",
        "Le concile de Chalcédoine a fixé cette formulation.",
    ],
)
def test_la_machine_ne_peut_ni_citer_un_manuscrit_ni_invoquer_une_autorite(corps: str) -> None:
    with pytest.raises(CurationInvalideError):
        verifier_forme_machine(corps, SIGNATAIRE_IA)


@pytest.mark.parametrize(
    "corps",
    [
        "Le v. 1 est concerné par une variante textuelle : les éditions qui suivent le Texte "
        "Reçu ajoutent « qui ne marchent pas selon la chair ».",
        "Selon la tradition réformée, ce texte porte l'élection.",
    ],
)
def test_un_humain_garde_le_droit_de_citer_ce_dont_il_repond(corps: str) -> None:
    """⚠️ **La règle vise la machine, pas le corpus.**

    C'est exactement la mise en garde de Romains 8:1-11, écrite par un relecteur. L'interdire
    aurait mis en tête de file de relecture la seule ligne du corpus dont on soit sûr."""
    verifier_forme_machine(corps, "Richmond")


def test_la_negation_de_doctrine_n_est_pas_refusee() -> None:
    """🔴 Le refus qu'on a failli écrire, et qui aurait coûté huit bonnes lignes pour une mauvaise.

    Job 8 est un discours de Bildad, et le livre dira que les amis ont mal parlé de Dieu.
    Avertir que sa rétribution n'est pas une doctrine est la chose la plus utile qu'on puisse
    dire à qui prêche ce chapitre. Aucune expression régulière ne la sépare de la neuvième
    ligne, qui restreignait à tort Jean 14:2-3 — la différence est théologique, donc humaine.
    """
    bildad = (
        "La promesse de rétribution (v. 6-7) est conditionnée à la justice de Job et ne "
        "constitue pas une doctrine générale du salut ou de la grâce divine."
    )
    verifier_forme_machine(bildad, SIGNATAIRE_IA)


def test_une_ligne_ordinaire_passe() -> None:
    verifier_forme_machine(
        "Le texte ne précise pas si le serpent est une figure démoniaque.", SIGNATAIRE_IA
    )
