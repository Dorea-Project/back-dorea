"""Les sections d'un plan — **une liste fermée, mais qui sait lire**.

Le code de section était un texte libre, et le verrou du livrable s'y adosse : un client qui
envoie `Divisions` au lieu de `divisions` **refuserait son document à un pasteur qui a pourtant
écrit son plan**.

Fermer seul aurait déplacé le problème — au lieu d'un verrou contourné par une majuscule, un
plan refusé pour la même majuscule. D'où les deux moitiés, et il faut les deux :

1. **on canonise** — casse, accents, tirets, et les mots que les gens emploient vraiment ;
2. **on refuse ce qui reste**, en nommant la liste, et **en base** autant qu'au service.

⚠️ **Quinze codes, pas dix.** Braga en nomme dix ; les trois prédications réelles en portent
cinq de plus. Fermer aux dix aurait refusé à trois pasteurs sur trois les sections qu'ils
tiennent depuis toujours — exactement le défaut que le seuil adossé à la `proposition` avait
déjà fait commettre.
"""

from __future__ import annotations

import pytest

from app.contexts.urim.application.ports import ElementRecord
from app.contexts.urim.domain.errors import ElementInconnuError
from app.contexts.urim.domain.squelette import (
    CODES,
    ELEMENTS,
    ELEMENTS_OBSERVES,
    POINT_CENTRAL,
    code_canonique,
)

from .test_articulation import _preparation, _service, _StudiesAvecPlan
from .test_study_service import AUTEUR

pytestmark = pytest.mark.asyncio


# ============================================================ 1. la liste


async def test_la_liste_porte_les_dix_de_braga_et_les_cinq_observes():
    """La liste n'est pas la théorie d'un manuel : c'est ce que le manuel dit **plus** ce que
    les notes montrent."""
    assert len(CODES) == 15
    assert set(ELEMENTS) | set(ELEMENTS_OBSERVES) == set(CODES)
    for observe in ("objectif", "contexte", "definitions", "nb", "temoignage"):
        assert observe in CODES
    assert POINT_CENTRAL in CODES


# ============================================================ 2. on canonise d'abord


async def test_les_formes_que_les_gens_ecrivent_retombent_sur_leur_code():
    """**La moitié utile de la fermeture.** Le pasteur tape sur une tablette un vendredi soir :
    lui faire porter la graphie exacte d'un code interne serait une contrainte de programme."""
    assert code_canonique("Divisions") == "divisions"
    assert code_canonique("POINT") == "divisions"
    assert code_canonique("sous point") == "subdivisions"
    assert code_canonique("Sous-Point") == "subdivisions"
    assert code_canonique("Intro") == "introduction"
    assert code_canonique("Témoignage") == "temoignage"
    assert code_canonique("ccl") == "conclusion"


async def test_ce_qu_on_ne_sait_pas_ranger_n_est_pas_range_au_hasard():
    """Le couple. Rendre un code par défaut serait pire que refuser : la section se rangerait
    silencieusement sous une autre, et le pasteur s'en apercevrait en relisant son plan."""
    assert code_canonique("machin") is None
    assert code_canonique("") is None


# ============================================================ 3. le service


async def test_un_code_ecrit_autrement_est_accepte_et_range():
    studies = _StudiesAvecPlan()
    service = _service(studies)
    study_id = await _preparation(service, studies)

    await service.set_elements(
        actor_account_id=AUTEUR,
        study_id=study_id,
        elements=[ElementRecord("Divisions", 1, "1- Christ élevé.")],
    )

    assert studies.elements_ecrits[0].element_code == "divisions"


async def test_un_code_inconnu_est_refuse_et_le_motif_nomme_la_liste():
    """Un refus qui dit seulement « code invalide » laisse un pasteur devant un formulaire
    qu'il ne peut pas remplir. La liste est courte assez pour tenir dans la phrase."""
    studies = _StudiesAvecPlan()
    service = _service(studies)
    study_id = await _preparation(service, studies)

    with pytest.raises(ElementInconnuError) as refus:
        await service.set_elements(
            actor_account_id=AUTEUR,
            study_id=study_id,
            elements=[ElementRecord("digression", 1, "…")],
        )

    assert "digression" in str(refus.value)
    assert "divisions" in str(refus.value)  # la liste voyage avec le refus


async def test_un_seul_code_fautif_ne_passe_pas_en_douce():
    """Le plan est écrit **entier ou pas du tout** : accepter les bons et taire le refusé
    ferait disparaître une section sans que personne le dise."""
    studies = _StudiesAvecPlan()
    service = _service(studies)
    study_id = await _preparation(service, studies)

    with pytest.raises(ElementInconnuError):
        await service.set_elements(
            actor_account_id=AUTEUR,
            study_id=study_id,
            elements=[
                ElementRecord("divisions", 1, "1- Christ élevé."),
                ElementRecord("digression", 2, "…"),
            ],
        )

    assert studies.elements_ecrits == []


# ============================================================ 4. la base aussi


async def test_la_base_refuse_un_code_hors_liste():
    """⚠️ **La garde est en base, pas seulement au service.** Une garde applicative tombe au
    premier second chemin d'écriture — un import, un script de reprise, un correctif de nuit.

    Le couple : la ligne légitime que la base accepte, sa jumelle fautive qu'elle refuse."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.contexts.urim.infrastructure.persistence.models import (
        UrimPreparationElementModel,
        UrimPreparationModel,
    )
    from app.core.database import Base

    moteur = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with moteur.begin() as connexion:
        await connexion.run_sync(Base.metadata.create_all)
    fabrique = async_sessionmaker(moteur, expire_on_commit=False)

    prep = uuid4()
    async with fabrique() as session:
        session.add(UrimPreparationModel(
            id=prep, church_id=None, author_id=uuid4(), raw_input="Hébreux 13:1",
            service_timezone="Africa/Abidjan", status="ouverte",
            opened_at=datetime(2026, 8, 14, tzinfo=UTC),
        ))
        session.add(UrimPreparationElementModel(
            preparation_id=prep, element_code="divisions", ordinal=1, body="1- Christ élevé.",
        ))
        await session.commit()

        session.add(UrimPreparationElementModel(
            preparation_id=prep, element_code="digression", ordinal=2, body="…",
        ))
        with pytest.raises(IntegrityError):
            await session.commit()
    await moteur.dispose()
