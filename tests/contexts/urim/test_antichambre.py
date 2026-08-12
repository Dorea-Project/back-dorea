"""**Préparer sans église** — Urim est l'antichambre, pas une pièce de la maison.

On entre par Urim sans rien savoir de Dorea, et Urim ne sait rien de vous : le rôle Dorea
`null` est le cas **normal**, pas le cas particulier. Jusqu'ici c'était faux — les trois routes
d'entrée portaient le tenant dans leur chemin, et la garde exigeait `PUBLISH_SERMON` *dans
cette église*. Le pasteur qui n'avait rejoint aucune assemblée n'avait aucune URL à appeler.

Ce fichier tient les quatre propriétés qui font tenir l'antichambre :

1. **Ouvrir n'exige rien.** Sans église, il n'y a personne à qui demander l'autorisation.
2. **Rien n'est réservé.** La réservation n'existe que pour ne pas facturer deux fois ; hors
   d'une église rien n'est facturé, et un compteur qui ne compte contre aucun plafond est un
   compteur qui ment.
3. **La propriété garde la relecture.** C'est la seule règle qui reste quand il n'y a plus
   d'église à interroger — et c'est elle qui a décidé qu'une préparation ne se rattache
   **jamais d'office** : le rattachement la rendrait lisible par les collègues.
4. **L'église ne perd rien.** Sur une préparation d'église, la garde reste ce qu'elle était.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.contexts.urim.application.study_service import UrimStudyService
from app.contexts.urim.domain.errors import PreparationIntrouvableError

from .test_study_service import (
    AUTEUR,
    EGLISE,
    MAINTENANT,
    _Acces,
    _index,
    _Modele,
    _Reservations,
    _Studies,
)

pytestmark = pytest.mark.asyncio


class _AccesQuiCompte(_Acces):
    """Une garde qui **note qu'on l'a consultée** — c'est tout l'objet du premier test."""

    def __init__(self) -> None:
        self.appels: list[object] = []

    async def ensure_may_prepare(self, *, account_id, church_id) -> None:
        self.appels.append(church_id)


class _ReservationsQuiComptent(_Reservations):
    def __init__(self) -> None:
        super().__init__()
        self.reservations: list[str] = []

    async def reserve(self, *, church_id, author_id, pericope_key, at):
        self.reservations.append(pericope_key)
        return uuid4()


def _service(acces=None, reservations=None) -> UrimStudyService:
    return UrimStudyService(
        studies=_Studies(),
        reservations=reservations or _ReservationsQuiComptent(),
        access=acces or _AccesQuiCompte(),
        index=_index(),
        clock=lambda: MAINTENANT,
        resolver=_Modele(),
    )


# ====================================================== 1. ouvrir n'exige aucune autorisation


async def test_ouvrir_sans_eglise_ne_demande_l_autorisation_de_personne():
    """Sans église, il n'y a personne à qui demander — la garde n'est pas consultée.

    Ce n'est pas un contournement : `ensure_may_prepare` posait une question de droit à une
    église, et il n'y en a pas. L'appeler avec `None` aurait obligé l'adaptateur à inventer
    une réponse."""
    acces = _AccesQuiCompte()
    service = _service(acces=acces)

    dto = await service.open(actor_account_id=AUTEUR, raw_input="Hébreux 13:1")

    assert acces.appels == []
    assert dto.record.church_id is None
    assert dto.record.author_id == AUTEUR


async def test_ouvrir_dans_une_eglise_demande_toujours_l_autorisation():
    """Le pendant du précédent — sinon le premier prouverait seulement qu'on a tout ouvert."""
    acces = _AccesQuiCompte()
    service = _service(acces=acces)

    await service.open(
        actor_account_id=AUTEUR, church_id=EGLISE, raw_input="Hébreux 13:1"
    )

    assert acces.appels == [EGLISE]


# ================================================================== 2. rien n'est réservé


async def test_sans_eglise_rien_n_est_reserve():
    """La réservation existe pour ne pas facturer deux fois le même travail.

    Hors d'une église, rien n'est facturé : en poser une donnerait un décompte sans plafond,
    c'est-à-dire un compteur qui ne compte contre rien."""
    reservations = _ReservationsQuiComptent()
    service = _service(reservations=reservations)

    await service.open(actor_account_id=AUTEUR, raw_input="Hébreux 13:1")

    assert reservations.reservations == []
    assert reservations.recles == []


async def test_dans_une_eglise_la_reservation_a_lieu():
    reservations = _ReservationsQuiComptent()
    service = _service(reservations=reservations)

    await service.open(
        actor_account_id=AUTEUR, church_id=EGLISE, raw_input="Hébreux 13:1"
    )

    assert len(reservations.reservations) == 1


# ============================================================ 3. la propriété garde la relecture


async def test_la_preparation_personnelle_d_un_autre_n_existe_pas():
    """⚠️ **« N'existe pas », et non « interdit ».**

    Répondre 403 confirmerait que la préparation existe — donc que cette personne prépare, sur
    quoi, et quand. Sur un objet privé, l'existence est elle-même une divulgation."""
    service = _service()
    dto = await service.open(actor_account_id=AUTEUR, raw_input="Hébreux 13:1")

    with pytest.raises(PreparationIntrouvableError):
        await service.get(actor_account_id=uuid4(), study_id=dto.record.id)


async def test_son_auteur_rouvre_la_sienne():
    service = _service()
    dto = await service.open(actor_account_id=AUTEUR, raw_input="Hébreux 13:1")

    relu = await service.get(actor_account_id=AUTEUR, study_id=dto.record.id)

    assert relu.record.id == dto.record.id


async def test_la_garde_de_propriete_couvre_aussi_l_ecriture():
    """La lecture n'est pas le seul chemin : décider et poser des éléments en sont d'autres.

    Une garde posée sur `get` seul laisserait un tiers **modifier** ce qu'il ne peut pas lire."""
    service = _service()
    dto = await service.open(actor_account_id=AUTEUR, raw_input="Hébreux 13:1")
    intrus = uuid4()

    with pytest.raises(PreparationIntrouvableError):
        await service.set_elements(
            actor_account_id=intrus, study_id=dto.record.id, elements=()
        )
    with pytest.raises(PreparationIntrouvableError):
        await service.decide(
            actor_account_id=intrus,
            study_id=dto.record.id,
            stage_code="resolve_passage",
            option_code="axe:christologie",
        )


# ========================================================== 4. l'église ne perd rien au passage


async def test_sur_une_preparation_d_eglise_c_est_toujours_l_eglise_qui_dit():
    """Non-régression : un travail d'église reste un objet d'église.

    Deux pasteurs d'une même assemblée peuvent se relire — la garde y est le droit de prêcher,
    pas la propriété, et l'antichambre ne devait pas changer ça au passage."""
    acces = _AccesQuiCompte()
    service = _service(acces=acces)
    dto = await service.open(
        actor_account_id=AUTEUR, church_id=EGLISE, raw_input="Hébreux 13:1"
    )
    collegue = uuid4()

    relu = await service.get(actor_account_id=collegue, study_id=dto.record.id)

    assert relu.record.id == dto.record.id
    assert acces.appels == [EGLISE, EGLISE]  # à l'ouverture, puis à la relecture
