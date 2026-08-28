"""Routes **mobile** d'Urim — la préparation de prédication du pasteur.

Autorité `PUBLISH_SERMON`, église entière : c'est **la même personne** que celle qui
déposera le sermon, à un autre moment de son travail. Urim prépare, Sermon publie (D-B) —
la séparation est celle des modèles, jamais celle des gens.

⚠️ **Une ambiguïté revient en 200.** Une résolution qui hésite, un bornage contesté, un
couple homilétique impossible ne sont pas des erreurs HTTP : ce sont des issues du moteur
(`await_decision`, `refuse`) rendues avec leurs options et leur motif. Les transformer en
4xx ferait disparaître exactement ce que le produit veut montrer — c'est la raison d'être
du champ `outcome`.

Le livrable est exposé depuis le 2026-08-13, **et dans le bon ordre** : la soumission se fait
juger avant qu'un fichier existe. La route de rendu viendra avec les écrivains `.pptx`/`.docx`,
et ne servira que ce qui porte déjà `conforme` — un fichier produit est un fichier qui circule.
"""

from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.urim.application.ports import ElementRecord
from app.contexts.urim.deliverable.application.ports import DiapositiveSoumise
from app.contexts.urim.interface.dependencies import (
    ArchiveServiceDep,
    CorpusIndexDep,
    DeliverableServiceDep,
    StudyServiceDep,
)
from app.contexts.urim.interface.schemas import (
    ArchiveEntryView,
    ArchiveFromStudyBody,
    ArchiveManualBody,
    ArticulationBody,
    ArticulationView,
    ConcordanceView,
    CoverageView,
    DecisionBody,
    DeliverableBody,
    DeliverableView,
    ElementsBody,
    OpenStudyBody,
    PassageDetailView,
    PromotionBody,
    RenameBody,
    RepriseBody,
    ShelveBody,
    StudySummaryView,
    StudyView,
    SupportsBody,
    TurnBody,
)

router = APIRouter()


@router.get(
    "/studies",
    response_model=list[StudySummaryView],
    summary="Mon fil — ou en est chaque preparation, sans rejouer le moteur",
)
async def list_studies(
    actor: CurrentActor,
    service: StudyServiceDep,
    index: CorpusIndexDep,
    rangees: bool = False,
) -> list[StudySummaryView]:
    """L'ecran d'accueil.

    ⚠️ **Aucune phrase d'Urim n'est servie ici.** Le `say` et le `why` viennent
    du rejeu ; les rendre pour vingt lignes ferait tourner vingt pipelines a
    l'ouverture de l'application. Le fil dit ou l'on en est — le reste s'obtient
    en ouvrant la preparation.

    `rangees=true` rend l'inverse : ce que le pasteur a mis de cote. Sans cette
    porte, ranger vaudrait perdre — et le geste serait une trappe.
    """
    records = await service.list_mine(
        actor_account_id=actor.account_id, rangees=rangees
    )

    etiquettes = {p.id: p.label for p in index.pericopes}

    return [
        StudySummaryView.from_record(
            record,
            pericope_label=etiquettes.get(record.pericope_id) if record.pericope_id else None,
        )
        for record in records
    ]


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


@router.patch(
    "/studies/{study_id}",
    response_model=StudySummaryView,
    summary="Nommer une préparation — ou lui rendre le nom qu'elle avait toute seule",
)
async def rename_study(
    study_id: UUID,
    payload: RenameBody,
    actor: CurrentActor,
    service: StudyServiceDep,
    index: CorpusIndexDep,
) -> StudySummaryView:
    """Le titre écrit à la main.

    L'écran affichait la phrase d'ouverture tant que rien n'était résolu, puis
    l'étiquette de l'unité. Les deux sont justes, et aucun des deux n'est
    **choisi** : trois préparations ouvertes sur Romains se ressemblent dans un
    historique. Un titre vide efface et rend l'affichage automatique.
    """
    record = await service.rename(
        actor_account_id=actor.account_id, study_id=study_id, title=payload.title
    )

    etiquettes = {p.id: p.label for p in index.pericopes}

    return StudySummaryView.from_record(
        record,
        pericope_label=etiquettes.get(record.pericope_id) if record.pericope_id else None,
    )


@router.post(
    "/studies/{study_id}/rangement",
    response_model=StudySummaryView,
    summary="Ranger une préparation, ou la ressortir — rien n'est effacé",
)
async def shelve_study(
    study_id: UUID,
    payload: ShelveBody,
    actor: CurrentActor,
    service: StudyServiceDep,
    index: CorpusIndexDep,
) -> StudySummaryView:
    """Sortir du fil sans sortir de la base.

    ⚠️ **Ce n'est ni `abandonnee`, ni une suppression.** « Abandonnée » est posé
    par « reformuler » : la saisie rouvre sans rien conserver, c'est un
    renoncement. Ranger est le contraire — on garde, on ne veut simplement plus
    l'avoir en tête de liste, et `GET /studies?rangees=true` la retrouve.

    Il n'y a **pas de route de suppression**, et c'est une décision : une
    préparation est du travail, et le travail détruit ne revient pas.
    """
    record = await service.ranger(
        actor_account_id=actor.account_id, study_id=study_id, rangee=payload.rangee
    )

    etiquettes = {p.id: p.label for p in index.pericopes}

    return StudySummaryView.from_record(
        record,
        pericope_label=etiquettes.get(record.pericope_id) if record.pericope_id else None,
    )


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
        idempotency_key=payload.idempotency_key,
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


@router.post(
    "/studies/{study_id}/thread/{entry_id}/promotion",
    response_model=StudyView,
    summary="Faire d'une note un point du plan — le seul chemin du fil vers le document",
)
async def promouvoir(
    study_id: UUID,
    entry_id: UUID,
    payload: PromotionBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    """🔴 **C'est ici que le verrou se tient.**

    Tout ce qui s'écrit dans le fil est gardé, rangé, relisible — et n'atteint aucun fichier.
    Le livrable n'imprime que `preparation_element`. Une note ne devient imprimable qu'en
    passant par ce geste, que le pasteur seul déclenche.

    ⚠️ **On ajoute, on ne remplace pas.** Sa note est le plus souvent une remarque *sur* le
    point — « le deuxième, il faut parler de la loi » — pas le texte du point. L'écraser lui
    ferait perdre ce qu'il avait écrit.

    ⚠️ **Une fois, et une seule.** Reprendre deux fois la même note écrirait deux points
    identiques, et le pasteur ne saurait plus lequel est le sien."""
    return StudyView.avec_tour(
        await service.promouvoir(
            actor_account_id=actor.account_id,
            study_id=study_id,
            entry_id=entry_id,
            element_code=payload.element_code,
            ordinal=payload.ordinal,
        )
    )


@router.post(
    "/studies/{study_id}/squelette/reprises",
    response_model=StudyView,
    summary="Reprendre un point proposé — le seul chemin de la proposition vers le document",
)
async def reprendre(
    study_id: UUID,
    payload: RepriseBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> StudyView:
    """🔴 **Le même verrou qu'au fil, sur l'autre porte.**

    Urim propose un titre et trois ou quatre points, avec les versets qui les portent — mais
    cette proposition vit dans sa propre table, et le livrable n'imprime que
    `preparation_element`. Elle n'atteint donc un document que par ce geste, que le pasteur
    seul déclenche. *L'IA propose, l'homme dispose.*

    ⚠️ **Point par point, jamais en bloc.** C'est le coût du geste qui garantit qu'il a lu ce
    qu'il signe.

    ⚠️ **On ajoute à la fin, on n'écrase rien** — ses divisions restent les siennes. Et
    **une fois, et une seule** : deux points identiques, et il ne saurait plus lequel est le
    sien."""
    return StudyView.avec_tour(
        await service.reprendre(
            actor_account_id=actor.account_id,
            study_id=study_id,
            propose_code=payload.propose_code,
        )
    )


@router.post(
    "/studies/{study_id}/articulations",
    response_model=ArticulationView,
    summary="Faire articuler un point — dans l'atelier, jamais dans le document",
)
async def articuler(
    study_id: UUID,
    payload: ArticulationBody,
    actor: CurrentActor,
    service: StudyServiceDep,
) -> ArticulationView:
    """**La seule prose que produise Urim, et elle est demandée point par point.**

    Ce qui la rend acceptable n'est pas une promesse mais le chemin des données : le livrable
    n'imprime que ce que le pasteur a écrit dans son plan. Cette proposition vit dans sa propre
    table et n'atteint un document que s'il la reprend — donc s'il l'a lue.

    L'invite porte quatre interdits : aucun verset hors du texte fourni, aucun fait historique
    ou culturel, aucun point ajouté ni conclusion à sa place, aucune illustration — c'est ce
    que le pasteur apporte, et lui seul.

    Sans modèle, au plafond, ou sur un point vide : `disponible: false`, et rien ne casse."""
    propose = await service.articuler(
        actor_account_id=actor.account_id,
        study_id=study_id,
        element_code=payload.element_code,
        ordinal=payload.ordinal,
    )
    if propose is None:
        return ArticulationView(body="", transition="", model="", disponible=False)
    return ArticulationView(
        body=propose.body,
        transition=propose.transition,
        model=propose.model,
        disponible=True,
    )


# ====================================================================== LE LIVRABLE
#
# ⚠️ **Le contrôle est en amont du fichier, et il n'existe qu'une route pour l'instant.**
# Aucun octet n'est produit ici : un fichier produit est un fichier qui circule, et un contrôle
# d'après coup protège la base de données, pas l'assemblée. La route de rendu viendra avec les
# écrivains `.pptx`/`.docx`, et ne servira que ce qui porte déjà `conforme`.


@router.post(
    "/studies/{study_id}/deliverable",
    response_model=DeliverableView,
    status_code=status.HTTP_201_CREATED,
    summary="Soumettre ce qui sortira — et le faire juger avant qu'un fichier existe",
)
async def submit_deliverable(
    study_id: UUID,
    payload: DeliverableBody,
    actor: CurrentActor,
    service: DeliverableServiceDep,
) -> DeliverableView:
    """**Une citation altérée n'est pas une erreur HTTP.**

    La réponse revient en 201 avec `validation: "rejete"` et, diapositive par diapositive, ce
    qu'il a écrit et ce que le corpus porte. Un 422 ferait disparaître le seul écran où un
    verset abîmé se voit avant le dimanche — même raison que les issues du moteur.

    Le texte projeté est jugé contre **toutes les versions détenues**, et le verdict nomme celle
    qui le reconnaît : un pasteur cite la Bible qu'il a, et sur Romains 8:1 l'Ostervald porte
    une clause que la LSG omet. Le refuser reviendrait à l'accuser de falsifier un verset qu'il
    cite mot pour mot.

    Sans une division de son plan, rien n'est produit : le document met en page ce qu'il a
    écrit, il ne l'écrit pas à sa place."""
    dto = await service.soumettre(
        actor_account_id=actor.account_id,
        study_id=study_id,
        kind=payload.kind,
        diapositives=[
            DiapositiveSoumise(d.titre, d.reference, d.texte_projete)
            for d in payload.diapositives
        ],
    )
    return DeliverableView.from_dto(dto)


@router.get(
    "/deliverables/{deliverable_id}",
    response_model=DeliverableView,
    summary="Relire un dossier de validation — ce qui est monté à l'écran, et sous quelle version",
)
async def get_deliverable(
    deliverable_id: UUID, actor: CurrentActor, service: DeliverableServiceDep
) -> DeliverableView:
    """C'est cette lecture qui dispense de conserver le fichier : `citation_check` garde, par
    diapositive, la référence et le texte projeté. On sait exactement ce qui a été montré sans
    garder un octet de binaire."""
    dto = await service.relire(
        actor_account_id=actor.account_id, deliverable_id=deliverable_id
    )
    return DeliverableView.from_dto(dto)


#: Ce qu'un client doit recevoir comme type — les deux formats bureautiques, tels quels.
_TYPES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@router.get(
    "/deliverables/{deliverable_id}/fichier",
    response_class=Response,
    summary="Les octets — et seulement pour ce qui porte déjà « conforme »",
    responses={200: {"content": {t: {} for t in _TYPES.values()}}},
)
async def download_deliverable(
    deliverable_id: UUID,
    actor: CurrentActor,
    service: DeliverableServiceDep,
    format: str = Query(default="", pattern="^(pdf)?$"),
) -> Response:
    """**La première route du dépôt qui ne rend pas du JSON**, et la dernière porte du verrou.

    Un livrable rejeté rend **409**, et c'est le seul endroit où le contrôle devient un refus
    HTTP : le dossier de validation, lui, revient en 201 avec ses verdicts, parce que c'est ce
    que le produit veut montrer. Réclamer les octets de ce qui a été rejeté est autre chose —
    c'est demander précisément ce que le contrôle existe pour ne pas produire.

    **`?format=pdf`** convertit le fichier déjà rendu — jamais une seconde mise en page :
    deux moteurs pour le même document dérivent, et ils dérivent en silence. Si la
    conversion échoue ou que LibreOffice manque, **le format natif est servi** avec son
    type réel : *aucun mur un vendredi soir*. Le client lit le `Content-Type`, pas sa
    demande.

    ⚠️ **Rien n'est stocké.** Le fichier est produit à la demande et rendu dans la réponse :
    ranger les préparations privées de tous les prédicateurs derrière une URL publique
    contredirait la seule garde qui les protège. Ce que le serveur garde, c'est ce qui est monté
    à l'écran (`citation_check`), pas le binaire."""
    format_, octets = await service.rendre(
        actor_account_id=actor.account_id,
        deliverable_id=deliverable_id,
        format=format,
    )
    return Response(
        content=octets,
        media_type=_TYPES[format_],
        headers={
            "Content-Disposition": (
                f'attachment; filename="preparation-{deliverable_id}.{format_}"'
            )
        },
    )


# ====================================================================== L'ARCHIVE
#
# `urim_preached` était **lue par l'étage du thème et écrite par personne** : la phrase
# « vous avez déjà prêché cet axe récemment » n'a jamais atteint quiconque. Ces routes sont
# l'écrivain qui manquait.
#
# L'archive est clée sur **l'auteur** : elle le suit s'il change d'église, et survit à la
# résiliation. Aucune route ne la lit pour quelqu'un d'autre.


@router.post(
    "/studies/{study_id}/preached",
    response_model=ArchiveEntryView,
    status_code=status.HTTP_201_CREATED,
    summary="J'ai prêché cette préparation — le geste, jamais une déduction",
)
async def archive_study(
    study_id: UUID,
    payload: ArchiveFromStudyBody,
    actor: CurrentActor,
    service: ArchiveServiceDep,
) -> ArchiveEntryView:
    """**Rien ne s'archive parce qu'une date est passée.**

    Le Pasteur X a préparé autour de six passages proposés et prêché le Psaume 125, qui
    n'était dans aucun des six. Une archive remplie par le calendrier aurait enregistré un
    sermon qui n'a jamais eu lieu, sous un axe qu'il n'a pas prêché — et la couverture du
    canon aurait menti dès la première semaine.

    ⚠️ **L'archive est celle de qui archive.** Deux pasteurs d'une même église se relisent ;
    si le second prêche à partir du travail du premier, c'est **sa** prédication. Rien ne peut
    donc salir l'archive d'un autre."""
    dto = await service.record_from_study(
        actor_account_id=actor.account_id,
        study_id=study_id,
        preached_on=payload.preached_on,
        capture_kind=payload.capture_kind,
    )
    return ArchiveEntryView.from_dto(dto)


@router.post(
    "/preached",
    response_model=ArchiveEntryView,
    status_code=status.HTTP_201_CREATED,
    summary="Archiver un sermon sans préparation — prêché ailleurs, ou avant Dorea",
)
async def archive_manually(
    payload: ArchiveManualBody,
    actor: CurrentActor,
    service: ArchiveServiceDep,
) -> ArchiveEntryView:
    """On peut prêcher sans avoir préparé, et l'archive doit l'accepter — sinon elle ne
    mesure que ce qui est passé par l'outil, ce qui n'est pas la même chose que le ministère
    de quelqu'un.

    La référence est lue **dans la notation du pasteur** (`Hb 2v29`, `Jn14v28`) et vérifiée
    contre le corpus : `Hb 2v29` est refusée parce qu'*« Hébreux 2 compte 18 versets »* —
    on dit ce qui manque au corpus, jamais ce qui manque au pasteur."""
    dto = await service.record_manually(
        actor_account_id=actor.account_id,
        reference=payload.reference,
        preached_on=payload.preached_on,
        church_id=payload.church_id,
        axis_code=payload.axis_code,
        theme=payload.theme,
        capture_kind=payload.capture_kind,
    )
    return ArchiveEntryView.from_dto(dto)


@router.get(
    "/preached",
    response_model=list[ArchiveEntryView],
    summary="Mon archive — ce que j'ai prêché, et quand",
)
async def list_archive(
    actor: CurrentActor,
    service: ArchiveServiceDep,
    limit: int = Query(default=300, ge=1, le=1000),
) -> list[ArchiveEntryView]:
    dtos = await service.list_mine(actor_account_id=actor.account_id, limit=limit)
    return [ArchiveEntryView.from_dto(d) for d in dtos]


@router.get(
    "/preached/couverture",
    response_model=CoverageView,
    summary="Où je suis allé dans l'Écriture, et sous quels loci — des faits, aucune consigne",
)
async def coverage(actor: CurrentActor, service: ArchiveServiceDep) -> CoverageView:
    """**L'archive informe, elle n'interdit rien** — et elle ne propose rien non plus.

    Aucun « vous n'avez pas prêché l'eschatologie depuis quatorze mois, voici un texte » :
    un moteur qui déduit d'un tableau ce qu'il faut prêcher dimanche décide de la chaire.
    Aucun score, aucune série, aucun pourcentage de complétude — ce serait mesurer la
    fidélité d'un homme et transformer une aide en performance à tenir.

    Un pasteur qui lit « pneumatologie : aucun sermon rangé depuis dix-huit mois » comprend
    seul. C'est la même économie que partout ailleurs : nommer suffit."""
    dto = await service.coverage(actor_account_id=actor.account_id)
    return CoverageView.from_dto(dto)


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

