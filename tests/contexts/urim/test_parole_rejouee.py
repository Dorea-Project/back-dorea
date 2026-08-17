"""Une parole ne se rejoue pas deux fois.

Decider et ecarter posent un etat : les renvoyer donne le meme resultat, et un
client sans reseau peut donc les mettre en file sans precaution. Une **parole**,
non. Le serveur y repond — repondeur, et parfois modele — et la renvoyer
couterait un second passage, un appel de plus, et peut-etre une autre phrase que
celle que le pasteur a deja lue.

Ces tests gardent la cle, et surtout **le moment ou elle se pose** : apres le
geste, jamais avant. La reclamer d'abord serait plus simple et perdrait la
parole — un geste qui echoue laisserait sa cle brulee, et le renvoi serait
ignore.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.contexts.urim.application.ports import PreparationRecord
from app.contexts.urim.application.study_service import UrimStudyService

AUTEUR = UUID("20aff920-5f30-530b-848a-b5483d9ce5d7")
ETUDE = UUID("3f6c1b2e-0000-4000-8000-000000000001")
CLE = "urim-7f3a91c0d4e2"


class _Depot:
    """Un depot en memoire — ce qui compte est ce qui est **ecrit**."""

    def __init__(self, record: PreparationRecord) -> None:
        self.record = record
        self.sauvegardes: list[str | None] = []

    async def get(self, study_id: UUID) -> PreparationRecord | None:
        return self.record if study_id == self.record.id else None

    async def save(self, record: PreparationRecord) -> None:
        self.record = record
        self.sauvegardes.append(record.last_turn_key)


class _CheminPris(Exception):
    """Le marqueur : atteindre ceci prouve que la cle n'a pas court-circuite."""


class _Reservations:
    async def usage(self, *args, **kwargs):
        raise _CheminPris


class _Service(UrimStudyService):
    """Le vrai `dire`, mais sans moteur derriere.

    On ne remplace que ce que la question n'interroge pas : le rejeu, la
    permission, et la conduite du tour. Ce qui reste execute est **le chemin de
    la cle**, celui qu'on vient eprouver.
    """

    def __init__(self, depot: _Depot) -> None:
        self.studies = depot
        self.reservations = _Reservations()
        self.clock = lambda: datetime(2026, 8, 17, 21, 14, tzinfo=UTC)

    async def _charger(self, study_id: UUID) -> PreparationRecord:
        record = await self.studies.get(study_id)
        assert record is not None
        return record

    async def _ensure_owner_or_preacher(self, actor_account_id, record) -> None:
        return None

    async def _rejouer(self, record, *, persist: bool = True):
        return _DtoNu(record)


class _DtoNu:
    """Juste assez pour que `dire` ne s'ecroule pas."""

    def __init__(self, record: PreparationRecord) -> None:
        self.record = record
        self.trace: list[tuple[str, str]] = [("weigh_conviction", "motif")]
        self.options: list = []
        self.outcome = "await_decision"
        self.reponse: str | None = None
        self.resolved_label = None


def _record(**kw) -> PreparationRecord:
    defauts = dict(
        id=ETUDE,
        church_id=None,
        author_id=AUTEUR,
        raw_input="l'amour fraternel n'existe plus dans l'église",
        status="ouverte",
    )
    return PreparationRecord(**{**defauts, **kw})


async def test_une_cle_deja_vue_ne_rejoue_rien():
    """Le cas qui justifie la colonne : le client renvoie ce qu'il avait en file."""
    depot = _Depot(_record(last_turn_key=CLE))
    service = _Service(depot)

    dto = await service.dire(
        actor_account_id=AUTEUR,
        study_id=ETUDE,
        raw_input="quel plan je peux tenir sur ce texte ?",
        idempotency_key=CLE,
    )

    # L'etat est rendu — c'est ce que le client attendait — et rien n'a ete
    # ecrit : pas de second passage du repondeur, donc pas d'appel de modele.
    assert dto.record is depot.record
    assert depot.sauvegardes == []


async def test_une_cle_differente_passe():
    """Deux paroles distinctes en file doivent etre traitees toutes les deux."""
    depot = _Depot(_record(last_turn_key=CLE))
    service = _Service(depot)

    with pytest.raises(_CheminPris):
        # Atteindre le marqueur **est** la preuve que la cle n'a pas
        # court-circuite le chemin : le tour allait etre conduit.
        await service.dire(
            actor_account_id=AUTEUR,
            study_id=ETUDE,
            raw_input="et sur un autre axe ?",
            idempotency_key="urim-une-autre-cle",
        )


async def test_sans_cle_le_comportement_est_celui_d_avant():
    """Aucun client existant ne casse : le champ est optionnel."""
    depot = _Depot(_record(last_turn_key=CLE))
    service = _Service(depot)

    with pytest.raises(_CheminPris):
        await service.dire(
            actor_account_id=AUTEUR,
            study_id=ETUDE,
            raw_input="quel plan je peux tenir sur ce texte ?",
        )


async def test_la_cle_ne_se_pose_pas_avant_le_geste():
    """**La regle qui protege la parole.**

    Si la cle etait reclamee d'abord, un geste qui echoue laisserait sa cle
    brulee : le renvoi serait ignore, et la phrase du pasteur perdue sans que
    personne ne le sache. Ici, un geste qui leve n'ecrit rien.
    """
    depot = _Depot(_record())
    service = _Service(depot)

    with pytest.raises(_CheminPris):
        await service.dire(
            actor_account_id=AUTEUR,
            study_id=ETUDE,
            raw_input="quel plan je peux tenir sur ce texte ?",
            idempotency_key=CLE,
        )

    assert depot.sauvegardes == []
    assert depot.record.last_turn_key is None


async def test_la_cle_se_pose_sur_une_parole_traitee():
    depot = _Depot(_record())
    service = _Service(depot)

    await service._marquer_parole(ETUDE, CLE)

    assert depot.sauvegardes == [CLE]
    assert depot.record.last_turn_key == CLE


async def test_marquer_une_preparation_disparue_ne_leve_pas():
    """Une preparation supprimee entre le geste et la marque : on n'insiste pas."""
    depot = _Depot(_record())
    service = _Service(depot)

    await service._marquer_parole(uuid4(), CLE)

    assert depot.sauvegardes == []
