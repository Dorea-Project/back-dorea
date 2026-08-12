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

from app.contexts.urim.application.ports import AucuneSortie
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
    def __init__(self, *, epuise: bool = False) -> None:
        super().__init__(epuise=epuise)
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


async def test_sans_eglise_la_reservation_a_lieu_aussi():
    """La réservation porte désormais **deux** décomptes : celui d'une église, celui d'une
    personne — et c'est la même chose pour la même raison : *rouvrir le même texte n'est pas
    un second travail*.

    Ce test disait le contraire hier, et c'était juste hier : sans quota personnel, une
    réservation sans église aurait compté contre rien. Le quota lui donne un sujet, et sans
    elle il compterait les hésitations du samedi soir au lieu des textes préparés."""
    reservations = _ReservationsQuiComptent()
    service = _service(reservations=reservations)

    await service.open(actor_account_id=AUTEUR, raw_input="Hébreux 13:1")

    assert len(reservations.reservations) == 1


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


# ============================================ 4. le quota éteint l'assistance, jamais Urim


class _ModeleQuiCompte(_Modele):
    """Un modèle qui **note qu'on l'a appelé** — épuisé, il ne doit plus l'être du tout."""

    def __init__(self) -> None:
        super().__init__(axes=(), passages=(), flags=())
        self.appels = 0

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


class _SortieOuverte:
    """Ce que sera un compte payé — la classe qui n'existe pas encore en production."""

    async def is_unlimited(self, account_id) -> bool:
        return True


def _service_avec(modele, *, epuise: bool, tier=None) -> UrimStudyService:
    return UrimStudyService(
        studies=_Studies(),
        reservations=_ReservationsQuiComptent(epuise=epuise),
        access=_AccesQuiCompte(),
        index=_index(),
        clock=lambda: MAINTENANT,
        resolver=modele,
        **({"tier": tier} if tier is not None else {}),
    )


async def test_le_quota_epuise_eteint_le_modele_et_rien_d_autre():
    """⚠️ **Ce n'est pas un mur.**

    Le pasteur garde le corpus, les pesées, la concordance, le contrôle de référence — tout le
    déterministe. Il perd les propositions par le sens et les axes. C'est le comportement
    `DEGRADE` et les adaptateurs `Null*`, qui sont des états de production (S12/S37)."""
    modele = _ModeleQuiCompte()
    service = _service_avec(modele, epuise=True)

    dto = await service.open(actor_account_id=AUTEUR, raw_input="Hébreux 13:1")

    assert modele.appels == 0
    assert dto.record.id is not None  # la préparation existe, et elle a tourné
    assert dto.outcome  # le moteur a rendu un verdict, pas une erreur


async def test_tant_que_le_quota_tient_le_modele_sert():
    """Le pendant — sinon le précédent prouverait seulement qu'on a débranché le modèle."""
    modele = _ModeleQuiCompte()
    service = _service_avec(modele, epuise=False)

    await service.open(actor_account_id=AUTEUR, raw_input="je veux prêcher sur le pardon")

    assert modele.appels > 0


async def test_la_sortie_rend_le_quota_sans_effet():
    """Payer, ou appartenir à une église qui a payé. La sortie est consultée **avant** de
    couper — un compte illimité ne se compte pas."""
    modele = _ModeleQuiCompte()
    service = _service_avec(modele, epuise=True, tier=_SortieOuverte())

    await service.open(actor_account_id=AUTEUR, raw_input="je veux prêcher sur le pardon")

    assert modele.appels > 0


async def test_la_sortie_de_production_repond_non():
    """⚠️ **`AucuneSortie` est branchée en production, et elle dit la vérité.**

    `business_accounts` enregistre une carte prépayée sans aucun cycle de facturation, et
    l'abonnement d'église n'existe qu'en note de design. Tant qu'il en est ainsi, le quota
    doit rester haut : un plafond sans sortie n'est pas un plafond, c'est un cul-de-sac."""
    assert await AucuneSortie().is_unlimited(AUTEUR) is False


async def test_le_texte_prepare_avec_le_modele_est_facture_une_fois():
    """« Réserver n'est pas consommer » — et consommer se compte **par texte**, pas par appel.

    C'est ce qui fait qu'hésiter le samedi soir ne coûte rien : rouvrir la même péricope
    retombe sur la même réservation, dont la date est déjà posée."""
    reservations = _ReservationsQuiComptent(epuise=False)
    service = UrimStudyService(
        studies=_Studies(), reservations=reservations, access=_AccesQuiCompte(),
        index=_index(), clock=lambda: MAINTENANT, resolver=_ModeleQuiCompte(),
    )

    await service.open(actor_account_id=AUTEUR, raw_input="je veux prêcher sur le pardon")

    assert len(reservations.factures) == 1


async def test_sans_modele_branche_rien_n_est_facture():
    """Pas de clé Mistral : `NullVerseResolver` sert le silence, et le silence est gratuit.

    Les deux silences se confondent volontairement — pas de clé, ou quota épuisé — parce que
    dans les deux cas aucun appel n'a eu lieu."""
    reservations = _ReservationsQuiComptent(epuise=False)
    service = UrimStudyService(
        studies=_Studies(), reservations=reservations, access=_AccesQuiCompte(),
        index=_index(), clock=lambda: MAINTENANT,
    )

    await service.open(actor_account_id=AUTEUR, raw_input="je veux prêcher sur le pardon")

    assert reservations.factures == []


# ========================================================== 5. l'église ne perd rien au passage


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
