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

from fastapi import APIRouter, Query, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.urim.application.ports import ElementRecord
from app.contexts.urim.interface.dependencies import StudyServiceDep
from app.contexts.urim.interface.schemas import (
    ConcordanceView,
    DecisionBody,
    ElementsBody,
    OpenStudyBody,
    PassageDetailView,
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


@router.get(
    "/tenants/{tenant_id}/lemmes",
    response_model=ConcordanceView,
    summary="Où ce mot de l'original paraît-il ailleurs — la concordance",
)
async def concordance(
    tenant_id: UUID,
    actor: CurrentActor,
    service: StudyServiceDep,
    lemme: str = Query(min_length=1, max_length=60, examples=["ὑπόδημα"]),
) -> ConcordanceView:
    """**Le pasteur ne s'arrête pas au mot ; il veut savoir ce qu'il porte.**

    C'est la première pierre du module de recherche, et la seule qui ne puisse rien inventer.
    Une note historique — *« chez les Hébreux les esclaves allaient pieds nus »* — dirait plus,
    et pourrait se tromper sans que personne dans l'assemblée ne le vérifie. La concordance,
    elle, montre le texte : sur `ὑπόδημα`, Jean-Baptiste indigne de délier la sandale — la
    tâche de l'esclave —, les disciples envoyés sans sandales, et le père qui fait **chausser**
    son fils venu se proposer comme mercenaire.

    Lecture pure : aucun appel de modèle, aucune écriture."""
    dto = await service.concordance(
        actor_account_id=actor.account_id, church_id=tenant_id, lemme=lemme
    )
    return ConcordanceView.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/passages",
    response_model=PassageDetailView,
    summary="En savoir plus sur un passage — sans ouvrir de préparation",
)
async def explorer_passage(
    tenant_id: UUID,
    actor: CurrentActor,
    service: StudyServiceDep,
    ref: str = Query(min_length=2, max_length=80, examples=["Luc 10:25-37"]),
) -> PassageDetailView:
    """Le pasteur à qui l'on propose six passages veut les ouvrir **avant** de choisir.

    Jusqu'ici il fallait en ouvrir une préparation pour lire les pesées et les mises en garde :
    donc réserver, écrire, et s'engager sur un texte qu'on voulait seulement regarder. Cette
    route est en lecture pure — on peut l'appeler six fois de suite sans conséquence."""
    dto = await service.explorer(
        actor_account_id=actor.account_id, church_id=tenant_id, reference=ref
    )
    return PassageDetailView.from_dto(dto)
