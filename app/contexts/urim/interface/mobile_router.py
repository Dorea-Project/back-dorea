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
    SupportsBody,
    TurnBody,
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
    return StudyView.avec_tour(dto)


@router.get(
    "/studies/{study_id}",
    response_model=StudyView,
    summary="Relire une préparation — la trace est rejouée, jamais relue d'un journal",
)
async def get_study(
    study_id: UUID, actor: CurrentActor, service: StudyServiceDep
) -> StudyView:
    dto = await service.get(actor_account_id=actor.account_id, study_id=study_id)
    return StudyView.avec_tour(dto)


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
    return StudyView.avec_tour(dto)


@router.post(
    "/studies/{study_id}/turns",
    response_model=StudyView,
    summary="Parler en cours de préparation — une phrase libre, pas un code d'option",
)
async def parler(
    study_id: UUID,
    payload: TurnBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    """**Le trou 2 du contrat** — le tour 5 de la maquette n'avait aucune route.

    `raw_input` n'existait qu'à l'ouverture ; après, il n'y avait que `/decisions` avec un code
    d'option. Or *« Quel plan je peux tenir sur ce texte ? »* est le geste le plus naturel une
    fois le texte sous les yeux, et le client n'avait rien à appeler pour lui.

    Aucun `stage_code` dans le corps, et c'est ce qui distingue ce geste d'une décision : le
    pasteur parle, il ne répond pas à un formulaire. L'étage, le serveur le connaît.

    ⚠️ **La liaison passe avant le modèle, toujours.** « Ecclésiologie », « le deuxième »,
    « non, pas celui-là » désignent ce qui est à l'écran et se résolvent par comparaison de
    chaînes — zéro appel, aucune erreur possible. Le modèle ne voit que le reste, et il ne
    fait que **classer** : il n'écrit jamais un mot que le pasteur lira.

    La réponse est un `StudyView` entier, comme partout — l'état n'a pas bougé si le tour n'a
    conclu à aucun geste, et c'est `turn.say` qui porte la phrase du répondeur."""
    dto = await service.dire(
        actor_account_id=actor.account_id,
        study_id=study_id,
        raw_input=payload.raw_input,
    )
    return StudyView.avec_tour(dto)


@router.post(
    "/studies/{study_id}/dismissals",
    response_model=StudyView,
    summary="Écarter une option — elle reste dans la liste, marquée et reléguée",
)
async def dismiss(
    study_id: UUID,
    payload: DecisionBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    """**Écarter n'est pas décider**, d'où une route distincte plutôt qu'un mode de `decisions`.

    Décider fait avancer le pipeline ; écarter ne fait avancer aucun étage — il apprend
    seulement au tour suivant de ne pas reproposer ce qu'on vient de repousser. Le moteur
    rejouant à chaque lecture, sans ce geste il n'a aucun moyen de s'en souvenir.

    Le corps est celui d'une décision : ce sont les mêmes coordonnées — un étage, une option."""
    dto = await service.dismiss(
        actor_account_id=actor.account_id,
        study_id=study_id,
        stage_code=payload.stage_code,
        option_code=payload.option_code,
    )
    return StudyView.avec_tour(dto)


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
    return StudyView.avec_tour(dto)


@router.put(
    "/studies/{study_id}/supports",
    response_model=StudyView,
    summary="La chaîne de textes — et le contrôle de référence qui va avec",
)
async def set_supports(
    study_id: UUID,
    payload: SupportsBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    """**Un sermon convoque une chaîne ; le modèle n'en tenait qu'un maillon.**

    Deux prédications du Pasteur X : huit textes, puis douze. Et dans la seconde, deux
    références inexistantes — `Hb 2v29` dans un chapitre qui compte 18 versets, `Ph 28v9` dans
    une épître qui en a quatre. Urim savait le dire depuis le premier jour et ne l'avait jamais
    dit : le pasteur ne soumettait que son passage principal.

    Les saisies sont lues **dans sa notation** (`Hb 2v29`, `Jn14v28`, `Eph 1v20-22`), et une
    saisie illisible n'interrompt rien : elle reste dans la liste avec son motif. Refuser les
    douze pour une faute de frappe serait le contraire du service rendu."""
    dto = await service.set_supports(
        actor_account_id=actor.account_id,
        study_id=study_id,
        saisies=payload.supports,
    )
    return StudyView.avec_tour(dto)


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


# ====================================================================== L'ANTICHAMBRE
#
# Les mêmes gestes, sans église. Urim s'installe seul : le pasteur qui n'a rejoint aucune
# assemblée — le cas **normal**, pas le cas particulier — n'avait jusqu'ici aucune URL à
# appeler, puisque le tenant était dans le chemin.
#
# ⚠️ **Les routes `/tenants/{id}/…` restent, et ne sont pas dépréciées.** Elles ne sont pas
# une ancienne façon de faire la même chose : elles disent *« je prépare dans l'espace de
# cette église »*, ce qui rattache le travail à l'assemblée et le rend lisible par les
# collègues qui y prêchent. Deux gestes différents, deux URL.


@router.post(
    "/studies",
    response_model=StudyView,
    status_code=status.HTTP_201_CREATED,
    summary="Ouvrir une préparation personnelle — sans église, sans rôle, sans permission",
)
async def open_personal_study(
    payload: OpenStudyBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    """Préparer n'exige rien d'autre que d'être authentifié.

    Il n'y a personne à qui demander l'autorisation : sans église, aucune permission ne
    s'applique. La préparation appartient à son auteur, et à lui seul — c'est la propriété,
    et non un rôle, qui la garde à la relecture."""
    dto = await service.open(
        actor_account_id=actor.account_id,
        raw_input=payload.raw_input,
        entry_origin=payload.entry_origin,
        service_date=payload.service_date,
    )
    return StudyView.avec_tour(dto)


@router.get(
    "/lemmes",
    response_model=ConcordanceView,
    summary="La concordance — sans église",
)
async def personal_concordance(
    actor: CurrentActor,
    service: StudyServiceDep,
    lemme: str = Query(min_length=1, max_length=60, examples=["ὑπόδημα"]),
) -> ConcordanceView:
    """Le corpus ne porte aucun `church_id` : cette lecture n'a jamais rien eu d'ecclésial."""
    dto = await service.concordance(actor_account_id=actor.account_id, lemme=lemme)
    return ConcordanceView.from_dto(dto)


@router.get(
    "/passages",
    response_model=PassageDetailView,
    summary="En savoir plus sur un passage — sans église",
)
async def explorer_passage_personnel(
    actor: CurrentActor,
    service: StudyServiceDep,
    ref: str = Query(min_length=2, max_length=80, examples=["Luc 10:25-37"]),
) -> PassageDetailView:
    """Lecture pure du corpus, comme au-dessus — et pour la même raison."""
    dto = await service.explorer(actor_account_id=actor.account_id, reference=ref)
    return PassageDetailView.from_dto(dto)

