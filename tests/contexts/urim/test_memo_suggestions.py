"""Les suggestions du modèle sont **gardées, pas redemandées**.

⚠️ **C'est d'abord une affaire de déterminisme.** Le rejeu prétend rendre ce que le pasteur a
vu ; sans mémo il *recalcule*, et se trouve d'accord tant que `mistral-small-latest` ne bouge
pas. C'est un alias mouvant : le jour où il change, une préparation d'hier rejoue autrement
pendant que la trace affirme le contraire. `model` est à ce mémo ce que `corpus_snapshot` est à
la préparation.

Le coût vient en second, et il est réel : le bloc conviction partait à **chaque** rejeu — chaque
ouverture d'écran, chaque refus — pour rendre mot pour mot ce qui venait d'être rendu. Le
scénario du 12/08 l'a chiffré : trois refus successifs coûtaient neuf appels et une dizaine de
secondes pour n'apprendre rien.

Un test qui compterait les appels sur une doublure sans mémo mesurerait un service que la
production n'a plus.
"""

from __future__ import annotations

import pytest

from .test_study_service import AUTEUR, EGLISE, MAINTENANT, _index, _Modele, _Studies

from app.contexts.urim.application.study_service import (  # isort: skip
    UrimStudyService,
    _empreinte_de_la_demande,
)
from .test_antichambre import _AccesQuiCompte, _ReservationsQuiComptent  # isort: skip

pytestmark = pytest.mark.asyncio

SAISIE = "l'amour fraternel n'existe plus dans l'eglise"
ETAGE = "weigh_conviction"


class _ModeleQuiCompte(_Modele):
    """Il note **chaque** appel — c'est la seule chose que ce fichier mesure."""

    def __init__(self) -> None:
        super().__init__(
            axes=(), passages=(), flags=("accusation",),
        )
        self.appels = 0
        self._model = "mistral-small-latest"

    async def resolve(self, text):
        self.appels += 1
        return await super().resolve(text)

    async def axes(self, text):
        self.appels += 1
        return await super().axes(text)

    async def lever(self, text):
        self.appels += 1
        return await super().lever(text)

    async def passages(self, text):
        self.appels += 1
        return await super().passages(text)


def _service(modele) -> UrimStudyService:
    return UrimStudyService(
        studies=_Studies(), reservations=_ReservationsQuiComptent(),
        access=_AccesQuiCompte(), index=_index(), clock=lambda: MAINTENANT,
        resolver=modele,
    )


async def _ouvrir(service):
    return await service.open(
        actor_account_id=AUTEUR, church_id=EGLISE, raw_input=SAISIE
    )


# ======================================================== le mémo évite les appels


async def test_relire_une_preparation_ne_rappelle_pas_le_modele():
    """🔴 **Le coût était par lecture, pas par ouverture.**

    La mesure du 11/08 annonçait « 0,05 ¢ par ouverture ». C'était faux : le bloc conviction
    repartait à chaque rejeu, donc un pasteur qui revenait six fois sur son écran payait six
    fois — et voyait six fois le même résultat, puisque la température est à zéro."""
    modele = _ModeleQuiCompte()
    service = _service(modele)
    dto = await _ouvrir(service)
    apres_ouverture = modele.appels

    await service.get(actor_account_id=AUTEUR, study_id=dto.record.id)
    await service.get(actor_account_id=AUTEUR, study_id=dto.record.id)

    assert apres_ouverture > 0, "l'ouverture doit bien interroger le modèle"
    assert modele.appels == apres_ouverture, "une relecture a rappelé le modèle"


async def test_ecarter_une_option_ne_rappelle_pas_le_modele():
    """Le geste que le scénario du 12/08 a mis en cause : trois refus, neuf appels, rien appris.

    Écarter est censé être léger — il coûtait le tour complet."""
    modele = _ModeleQuiCompte()
    service = _service(modele)
    dto = await _ouvrir(service)
    apres_ouverture = modele.appels
    codes = [o[0] for o in dto.options][:3]

    for code in codes:
        await service.dismiss(
            actor_account_id=AUTEUR, study_id=dto.record.id,
            stage_code=ETAGE, option_code=code,
        )

    assert modele.appels == apres_ouverture


async def test_le_memo_garde_ce_que_le_modele_a_offert():
    """Ce qui est relu doit être ce qui a été rendu, sinon le mémo ment sur le rejeu."""
    modele = _ModeleQuiCompte()
    service = _service(modele)
    dto = await _ouvrir(service)

    memo = service.studies.memos[
        (dto.record.id, _empreinte_de_la_demande("conviction", SAISIE))
    ]

    assert memo.flags == ("accusation",)
    assert memo.model == "mistral-small-latest", "le mémo doit dire QUI a répondu"


async def test_chaque_question_a_son_memo():
    """🔴 **Une seule ligne par préparation les faisait s'écraser.**

    Le chemin conviction demande les loci, les drapeaux et les passages ; le chemin impasse ne
    demande que des passages, sur la **même saisie**. Rangés ensemble, chaque rejeu redemandait
    au modèle celle que l'autre venait de chasser — et les compteurs d'appels l'ont montré
    avant que je ne le voie."""
    modele = _ModeleQuiCompte()
    service = _service(modele)
    dto = await _ouvrir(service)

    empreintes = {h for (etude, h) in service.studies.memos if etude == dto.record.id}

    assert empreintes == {
        _empreinte_de_la_demande("conviction", SAISIE),
        _empreinte_de_la_demande("impasse", SAISIE),
    }


async def test_une_reponse_vide_est_une_reponse_et_se_garde():
    """⚠️ **Le bon critère n'est pas « le résultat est-il vide ? » mais « a-t-on demandé ? ».**

    J'avais conditionné l'écriture à un résultat non vide, pour ne pas figer une ignorance.
    Faux : un modèle interrogé qui ne trouve rien **a répondu**, et ne pas le garder le fait
    redemander à chaque rejeu — le gaspillage même qu'on venait supprimer. C'est ce chemin-là
    qui rappelait le modèle à chaque refus.

    Le modèle de ce banc ne rend aucun passage : le mémo du chemin impasse est donc vide, et
    il existe quand même."""
    modele = _ModeleQuiCompte()
    service = _service(modele)
    dto = await _ouvrir(service)

    memo = service.studies.memos[
        (dto.record.id, _empreinte_de_la_demande("impasse", SAISIE))
    ]

    assert memo.passages == ()


# ======================================================== l'empreinte discrimine


async def test_l_empreinte_couvre_le_chemin_et_pas_seulement_la_saisie():
    """« citation » et « conviction » ne posent pas la même question au modèle.

    Ne condenser que la saisie ferait servir à un pasteur qui corrige son mode d'entrée la
    réponse à la question qu'il vient précisément d'abandonner."""
    assert _empreinte_de_la_demande("conviction", SAISIE) != _empreinte_de_la_demande(
        "impasse", SAISIE
    )


async def test_l_empreinte_ignore_les_variations_de_forme():
    """Elle passe par la normalisation partagée : accents, casse et ponctuation ne changent pas
    la question posée, et un mémo qui raterait sur une majuscule ne servirait jamais."""
    assert _empreinte_de_la_demande(
        "conviction", "L'amour Fraternel !"
    ) == _empreinte_de_la_demande("conviction", "l'amour fraternel")


# ======================================================== on n'écrit pas le silence


async def test_sans_modele_branche_aucun_memo_n_est_ecrit():
    """⚠️ **Le silence ne se garde pas.**

    Sans clé — ou quota épuisé — les trois listes sont vides. Les mémoriser ferait passer une
    absence pour une réponse, et le pasteur qui branche une clé ensuite ne verrait jamais rien
    venir : le mémo vide répondrait à sa place, pour toujours."""
    service = UrimStudyService(
        studies=_Studies(), reservations=_ReservationsQuiComptent(),
        access=_AccesQuiCompte(), index=_index(), clock=lambda: MAINTENANT,
    )

    await _ouvrir(service)

    assert service.studies.memos == {}, "le silence d'un modèle absent a été gardé"


# ======================================================== la facturation suit le mémo


async def test_un_tour_servi_depuis_le_memo_n_est_pas_facture():
    """Compter une relecture serait faire payer deux fois le même travail — exactement ce que
    la réservation existe pour empêcher."""
    modele = _ModeleQuiCompte()
    reservations = _ReservationsQuiComptent()
    service = UrimStudyService(
        studies=_Studies(), reservations=reservations, access=_AccesQuiCompte(),
        index=_index(), clock=lambda: MAINTENANT, resolver=modele,
    )
    dto = await service.open(
        actor_account_id=AUTEUR, church_id=EGLISE, raw_input=SAISIE
    )
    factures = len(reservations.factures)

    await service.get(actor_account_id=AUTEUR, study_id=dto.record.id)

    assert factures == 1, "l'ouverture doit être facturée une fois"
    assert len(reservations.factures) == factures
