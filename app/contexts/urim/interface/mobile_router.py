"""Routes **mobile** d'Urim — la préparation de prédication du pasteur.

Autorité `PUBLISH_SERMON`, église entière : c'est **la même personne** que celle qui
déposera le sermon, à un autre moment de son travail. Urim prépare, Sermon publie (D-B) —
la séparation est celle des modèles, jamais celle des gens.

⚠️ **Une ambiguïté revient en 200.** Une résolution qui hésite, un bornage contesté, un
couple homilétique impossible ne sont pas des erreurs HTTP : ce sont des issues du moteur
(`await_decision`, `refuse`) rendues avec leurs options et leur motif. Les transformer en
4xx ferait disparaître exactement ce que le produit veut montrer — c'est la raison d'être
du champ `outcome`.

Le livrable (diapositives, contrôle de citation) n'est **pas** exposé : les étapes 2 à 4
du chantier restent verrouillées (§11), et une route qui rendrait un fichier non contrôlé
irait contre la règle qui veut qu'une citation projetée soit vérifiée.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.urim.application.ports import ElementRecord
from app.contexts.urim.interface.dependencies import StudyServiceDep
from app.contexts.urim.interface.schemas import (
    DecisionBody,
    ElementsBody,
    OpenStudyBody,
    StudyView,
)

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}/studies",
    response_model=StudyView,
    status_code=status.HTTP_201_CREATED,
    summary="Ouvrir une préparation — le moteur tourne jusqu'à ce qu'il ait besoin de vous",
)
async def open_study(
    tenant_id: UUID,
    payload: OpenStudyBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    dto = await service.open(
        actor_account_id=actor.account_id,
        church_id=tenant_id,
        raw_input=payload.raw_input,
        entry_origin=payload.entry_origin,
        service_date=payload.service_date,
    )
    return StudyView.from_dto(dto)


@router.get(
    "/studies/{study_id}",
    response_model=StudyView,
    summary="Relire une préparation — la trace est rejouée, jamais relue d'un journal",
)
async def get_study(
    study_id: UUID, actor: CurrentActor, service: StudyServiceDep
) -> StudyView:
    dto = await service.get(actor_account_id=actor.account_id, study_id=study_id)
    return StudyView.from_dto(dto)


@router.post(
    "/studies/{study_id}/decisions",
    response_model=StudyView,
    summary="Répondre à un étage qui rend la main — le pipeline repart du début",
)
async def decide(
    study_id: UUID,
    payload: DecisionBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    dto = await service.decide(
        actor_account_id=actor.account_id,
        study_id=study_id,
        stage_code=payload.stage_code,
        option_code=payload.option_code,
    )
    return StudyView.from_dto(dto)


@router.put(
    "/studies/{study_id}/elements",
    response_model=StudyView,
    summary="Renseigner le squelette homilétique — champs libres, aucun imposé",
)
async def set_elements(
    study_id: UUID,
    payload: ElementsBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    dto = await service.set_elements(
        actor_account_id=actor.account_id,
        study_id=study_id,
        elements=[
            ElementRecord(e.element_code, e.ordinal, e.body) for e in payload.elements
        ],
    )
    return StudyView.from_dto(dto)
