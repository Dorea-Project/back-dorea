"""**Ce que le pasteur a écarté** — la moitié du dialogue qui ne se stockait nulle part.

Urim gardait ce qui avait été choisi et rien de ce qui avait été décliné. Sur un formulaire ça
ne se voit pas ; dans une conversation de onze tours, ça devient la chose la plus irritante
qu'un logiciel puisse faire — et c'est structurel, pas un oubli : **le moteur rejoue à chaque
lecture**, donc sans mémoire du refus il repropose au tour suivant ce qu'on vient de repousser.

Quatre propriétés, et la première est celle qui a décidé de la forme :

1. **Écarter n'efface pas.** L'option revient, marquée et reléguée en fin de liste.
2. **Le refus survit au rejeu**, sinon il ne sert à rien.
3. **Décider reprend** ce qu'on avait écarté, sans geste supplémentaire.
4. **Le refus est porté par le couple `(étage, option)`**, pas par le code seul.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.contexts.urim.domain.errors import PreparationIntrouvableError

from .test_study_service import AUTEUR, EGLISE, MAINTENANT, _index, _Modele, _service

pytestmark = pytest.mark.asyncio

#: L'étage qui rend la main sur une saisie qui ne résout pas — celui qui offre les dix loci.
ETAGE = "weigh_conviction"


async def _ouvrir_sur_une_intention(service):
    return await service.open(
        actor_account_id=AUTEUR, church_id=EGLISE,
        raw_input="l'amour fraternel n'existe plus dans l'eglise",
    )


def _codes(dto) -> list[str]:
    return [o[0] for o in dto.options]


def _ecartees(dto) -> set[str]:
    return {o[0] for o in dto.options if o[4]}


# ===================================================== 1. écarter n'efface pas


async def test_une_option_ecartee_reste_dans_la_liste():
    """⚠️ **La retirer serait plus simple à écrire et faux à lire.**

    Le pasteur ne saurait plus ce qu'Urim lui avait proposé, ni qu'il l'avait repoussé — et il
    ne pourrait pas revenir dessus. C'est la règle des couples refusés, qui voyagent avec les
    faisables : *les cacher laisserait croire qu'on n'y a pas pensé*."""
    service = _service()
    dto = await _ouvrir_sur_une_intention(service)
    cible = _codes(dto)[0]

    apres = await service.dismiss(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code=ETAGE, option_code=cible,
    )

    assert cible in _codes(apres), "l'option écartée a disparu de la liste"
    assert _ecartees(apres) == {cible}


async def test_l_option_ecartee_descend_en_fin_de_liste():
    """Marquée **et** reléguée : la marque seule laisserait le refus en tête de l'écran."""
    service = _service()
    dto = await _ouvrir_sur_une_intention(service)
    premier = _codes(dto)[0]

    apres = await service.dismiss(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code=ETAGE, option_code=premier,
    )

    assert _codes(apres)[-1] == premier


async def test_l_ordre_du_moteur_est_preserve_pour_le_reste():
    """Le tri est **stable** : l'ordre des options est une décision d'étage, et on ne fait que
    descendre ce qui a été repoussé."""
    service = _service()
    dto = await _ouvrir_sur_une_intention(service)
    avant = _codes(dto)
    cible = avant[0]

    apres = await service.dismiss(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code=ETAGE, option_code=cible,
    )

    assert [c for c in _codes(apres) if c != cible] == [c for c in avant if c != cible]


# ===================================================== 2. le refus survit au rejeu


async def test_le_refus_survit_a_la_relecture():
    """C'est **tout l'objet** de la table : le moteur rejoue à chaque lecture et ne se souvient
    de rien. Un refus qui ne survit pas au rejeu ne sert strictement à rien."""
    service = _service()
    dto = await _ouvrir_sur_une_intention(service)
    cible = _codes(dto)[0]
    await service.dismiss(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code=ETAGE, option_code=cible,
    )

    relu = await service.get(actor_account_id=AUTEUR, study_id=dto.record.id)

    assert _ecartees(relu) == {cible}


async def test_ecarter_deux_fois_est_un_seul_fait():
    """La clé primaire est le triplet lui-même — une ligne en double n'aurait rien à raconter."""
    service = _service()
    dto = await _ouvrir_sur_une_intention(service)
    cible = _codes(dto)[0]

    for _ in range(3):
        apres = await service.dismiss(
            actor_account_id=AUTEUR, study_id=dto.record.id,
            stage_code=ETAGE, option_code=cible,
        )

    assert _ecartees(apres) == {cible}
    assert len(service.studies.ecartees) == 1


async def test_ecarter_ne_fait_avancer_aucun_etage():
    """Écarter n'est pas décider. Rejouer en écrivant enregistrerait une tentative de
    résolution que personne n'a faite."""
    service = _service()
    dto = await _ouvrir_sur_une_intention(service)
    tentatives = len(service.studies.attempts)

    await service.dismiss(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code=ETAGE, option_code=_codes(dto)[0],
    )

    assert len(service.studies.attempts) == tentatives


# ===================================================== 3. décider reprend


async def test_decider_sur_une_option_ecartee_la_reprend():
    """Choisir ce qu'on avait repoussé dit assez qu'on le reprend.

    Exiger un geste de restauration d'abord serait demander une formalité pour une intention
    déjà claire — et le pasteur qui change d'avis ne comprendrait pas pourquoi on lui résiste."""
    service = _service()
    dto = await _ouvrir_sur_une_intention(service)
    cible = next(c for c in _codes(dto) if c.startswith("axe:"))
    await service.dismiss(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code=ETAGE, option_code=cible,
    )

    await service.decide(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code=ETAGE, option_code=cible,
    )

    assert service.studies.ecartees == set()


# ===================================================== 4. le couple (étage, option)


async def test_le_refus_ne_porte_que_sur_l_etage_ou_il_a_eu_lieu():
    """Le même code peut être offert par deux étages ; l'écarter à l'un ne dit rien de l'autre.

    Filtrer sur le code seul aurait fait disparaître d'un écran un choix repoussé sur un autre —
    et personne n'aurait compris pourquoi."""
    service = _service()
    dto = await _ouvrir_sur_une_intention(service)
    cible = _codes(dto)[0]

    apres = await service.dismiss(
        actor_account_id=AUTEUR, study_id=dto.record.id,
        stage_code="un_autre_etage", option_code=cible,
    )

    assert _ecartees(apres) == set(), "un refus posé ailleurs a marqué cet étage-ci"


# ===================================================== la garde


async def test_un_tiers_ne_peut_pas_ecarter_dans_la_preparation_d_un_autre():
    """La même garde que la relecture : sur une préparation personnelle, c'est la propriété."""
    service = _service()
    dto = await service.open(actor_account_id=AUTEUR, raw_input="l'amour fraternel")

    with pytest.raises(PreparationIntrouvableError):
        await service.dismiss(
            actor_account_id=uuid4(), study_id=dto.record.id,
            stage_code=ETAGE, option_code="axe:christologie",
        )


async def test_le_depot_sql_tient_le_refus_contre_une_vraie_base():
    """La doublure prouve le service ; elle ne prouve pas la table.

    Idempotence, restauration, et le fait que le couple `(étage, option)` est bien la clé —
    trois choses qui se décident dans le schéma, pas dans le code."""
    from datetime import UTC, datetime
    from uuid import uuid4 as _uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.contexts.urim.application.ports import PreparationRecord
    from app.contexts.urim.infrastructure.persistence.study_repository import (
        SqlStudyRepository,
    )
    from app.core.database import Base

    moteur = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with moteur.begin() as cnx:
        await cnx.run_sync(Base.metadata.create_all)
    fabrique = async_sessionmaker(moteur, expire_on_commit=False)
    maintenant = datetime(2026, 8, 12, tzinfo=UTC)

    async with fabrique() as session:
        depot = SqlStudyRepository(session)
        etude = _uuid4()
        await depot.add(PreparationRecord(
            id=etude, church_id=None, author_id=AUTEUR, raw_input="l'amour fraternel",
            service_timezone="Africa/Abidjan", status="ouverte", opened_at=maintenant,
        ))

        await depot.dismiss(
            study_id=etude, stage_code=ETAGE, option_code="axe:christologie",
            at=maintenant,
        )
        await depot.dismiss(
            study_id=etude, stage_code=ETAGE, option_code="axe:christologie",
            at=maintenant,
        )
        assert await depot.list_dismissals(etude) == [(ETAGE, "axe:christologie")]

        # Même code, autre étage : c'est un second fait, pas le même.
        await depot.dismiss(
            study_id=etude, stage_code="resolve_passage",
            option_code="axe:christologie", at=maintenant,
        )
        assert len(await depot.list_dismissals(etude)) == 2

        await depot.restore(
            study_id=etude, stage_code=ETAGE, option_code="axe:christologie"
        )
        assert await depot.list_dismissals(etude) == [
            ("resolve_passage", "axe:christologie")
        ]

    await moteur.dispose()


async def test_la_doublure_a_la_signature_du_port():
    """⚠️ Le garde-fou du dépôt : une doublure plus permissive que le vrai port ne prouve rien.

    C'est ainsi que le 500 des ouvertures avait survécu à 192 tests — `record_attempt` était
    appelé sans un argument obligatoire, et aucune doublure ne l'exigeait."""
    from app.contexts.urim.application.ports import StudyRepository
    from app.contexts.urim.infrastructure.persistence.study_repository import (
        SqlStudyRepository,
    )

    service = _service(index=_index(), modele=_Modele())
    attendues = {"dismiss", "restore", "list_dismissals"}
    for nom in attendues:
        assert hasattr(service.studies, nom), f"la doublure ignore {nom}"
        assert hasattr(SqlStudyRepository, nom), f"le dépôt SQL ignore {nom}"
        assert hasattr(StudyRepository, nom), f"le port ignore {nom}"
    assert MAINTENANT is not None
