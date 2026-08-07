"""Routes **mobile** du moteur de veille — le signalement par un tiers.

Une seule route d'écriture, partagée par les deux surfaces du document : le bouton de l'écran
Veille (responsable) et celui du Compagnon (membre). Elles n'ont jamais eu besoin de diverger —
c'est le même geste, et la résolution du propriétaire absorbe la différence de rôle.

Ce que cette route **ne fait pas**, et qui compte autant que ce qu'elle fait : elle ne notifie
personne. La personne concernée n'apprend jamais qu'un tiers a signalé, et l'émetteur reçoit
« Noté. » une fois, sans récapitulatif.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.watch.interface.dependencies import (
    AnswerContactDep,
    CaseContextDep,
    CloseCaseDep,
    DeclareGestureDep,
    DeclareLinkDep,
    FraternalReactsDep,
    ListMyCasesDep,
    PendingAttemptsDep,
    RaiseConcernDep,
    SeeCaseDep,
    StartContactDep,
    StopContactingMeDep,
)
from app.contexts.watch.interface.schemas import (
    AnswerContactBody,
    CaseContextView,
    CaseListView,
    CaseView,
    CloseCaseBody,
    ConcernAckView,
    DeclareGestureBody,
    DeclareLinkBody,
    FraternalReactListView,
    GestureListView,
    LinkAckView,
    NuanceListView,
    PendingAttemptListView,
    RaiseConcernBody,
    StartContactBody,
    StartedContactView,
)

router = APIRouter()


@router.get(
    "/nuances",
    response_model=NuanceListView,
    summary="La liste **fermée** des nuances — à afficher, jamais à saisir",
)
async def nuances() -> NuanceListView:
    return NuanceListView.all()


@router.post(
    "/tenants/{tenant_id}/concerns",
    response_model=ConcernAckView,
    status_code=status.HTTP_201_CREATED,
    summary="« Je m'en occupe cette semaine » — signaler une inquiétude sur quelqu'un d'autre",
)
async def raise_concern(
    tenant_id: UUID,
    payload: RaiseConcernBody,
    actor: CurrentActor,
    command: RaiseConcernDep,
) -> ConcernAckView:
    ack = await command.execute(
        emitter_account_id=actor.account_id,
        subject_account_id=payload.subject_account_id,
        tenant_id=tenant_id,
        nuance=payload.nuance,
    )
    return ConcernAckView(message=ack.message)


@router.get(
    "/gestures",
    response_model=GestureListView,
    summary="Les trois gestes — à afficher, jamais à saisir",
)
async def gestures() -> GestureListView:
    return GestureListView.all()


@router.post(
    "/tenants/{tenant_id}/gestures",
    response_model=ConcernAckView,
    status_code=status.HTTP_201_CREATED,
    summary="« Je suis passé le voir » — déclarer un geste posé pour quelqu'un d'autre",
)
async def declare_gesture(
    tenant_id: UUID,
    payload: DeclareGestureBody,
    actor: CurrentActor,
    command: DeclareGestureDep,
) -> ConcernAckView:
    """**Ce que cette route ne rend pas** est sa spécification.

    Elle ne dit pas si un cas existait — ce serait apprendre à un membre que quelqu'un est en
    veille. Elle ne rend aucun total, et rien ne relancera jamais celui qui n'a rien déclaré : ce
    serait dire le silence, et le produit s'interdit de le dire. Elle répond « Merci. », une fois.
    """
    ack = await command.execute(
        actor_account_id=actor.account_id,
        subject_account_id=payload.subject_account_id,
        tenant_id=tenant_id,
        gesture=payload.gesture,
    )
    return ConcernAckView(message=ack.message)


@router.post(
    "/tenants/{tenant_id}/links",
    response_model=LinkAckView,
    status_code=status.HTTP_201_CREATED,
    summary="« Voici par qui vous pouvez me rejoindre » — trois noms au plus",
)
async def declare_link(
    tenant_id: UUID,
    payload: DeclareLinkBody,
    actor: CurrentActor,
    command: DeclareLinkDep,
) -> LinkAckView:
    """**La personne nommée n'est jamais prévenue.**

    Sinon on fabrique une déclaration d'affinité semi-publique — le sociogramme par la petite
    porte — et la blessure du « je n'étais pas dans ses trois ». Le lien n'est pas un objet
    social, c'est un chemin de question."""
    ack = await command.execute(
        actor_account_id=actor.account_id,
        linked_account_id=payload.linked_account_id,
        tenant_id=tenant_id,
    )
    return LinkAckView(message=ack.message, remaining=ack.remaining)


@router.delete(
    "/tenants/{tenant_id}/links/{linked_account_id}",
    response_model=LinkAckView,
    summary="Retirer un proche — **sans motif**, et sans que personne l'apprenne",
)
async def remove_link(
    tenant_id: UUID,
    linked_account_id: UUID,
    actor: CurrentActor,
    command: DeclareLinkDep,
) -> LinkAckView:
    """**Aucun corps de requête, aucune justification.**

    C'est la clause qui compte le plus du lot, et elle existe pour un cas précis : le lien
    conjugal est celui qu'on a le plus de raisons de retirer. Exiger un motif ferait du retrait
    une négociation ; prévenir le retiré le rendrait impossible à exercer."""
    ack = await command.remove(
        actor_account_id=actor.account_id,
        linked_account_id=linked_account_id,
        tenant_id=tenant_id,
    )
    return LinkAckView(message="C'est retiré.", remaining=ack.remaining)


@router.get(
    "/tenants/{tenant_id}/fraternal-reacts",
    response_model=FraternalReactListView,
    summary="« Tu es passé voir Anna il y a un mois. Un mot ? » — vos gestes, pas leur silence",
)
async def fraternal_reacts(
    tenant_id: UUID, actor: CurrentActor, query: FraternalReactsDep
) -> FraternalReactListView:
    """**Ce que cette route ne rend pas** est, encore une fois, sa spécification.

    Elle ne dit pas depuis quand la personne n'a pas donné de nouvelles, ni pourquoi elle est
    proposée, ni si un cas existe sur elle. Elle rend ce que **vous** avez fait et quand — le
    reste appartient à la personne concernée, et à son responsable.

    Aucun texte n'est fourni non plus : le moteur donne un nom et une raison d'écrire, jamais les
    mots. Deux personnes qui recevraient la même phrase la rendraient sans valeur."""
    return FraternalReactListView.of(
        await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    )


# --- La file du responsable ---------------------------------------------------------------------


@router.get(
    "/tenants/{tenant_id}/my-cases",
    response_model=CaseListView,
    summary="Mes cas vivants, le plus urgent d'abord — les cas retenus n'y sont pas",
)
async def my_cases(
    tenant_id: UUID, actor: CurrentActor, query: ListMyCasesDep
) -> CaseListView:
    return CaseListView.of(
        await query.execute(account_id=actor.account_id, tenant_id=tenant_id)
    )


@router.post(
    "/tenants/{tenant_id}/cases/{case_id}/see",
    response_model=CaseView,
    summary="J'ai ouvert ce cas — alimente le seul indicateur qui anticipe l'abandon",
)
async def see_case(
    tenant_id: UUID, case_id: UUID, actor: CurrentActor, command: SeeCaseDep
) -> CaseView:
    return CaseView.of(
        await command.execute(
            signal_id=case_id, tenant_id=tenant_id, actor_account_id=actor.account_id
        )
    )


@router.post(
    "/tenants/{tenant_id}/cases/{case_id}/close",
    response_model=CaseView,
    summary="Fermer avec une issue **choisie** — fermer un cas est un acte humain",
)
async def close_case(
    tenant_id: UUID,
    case_id: UUID,
    payload: CloseCaseBody,
    actor: CurrentActor,
    command: CloseCaseDep,
) -> CaseView:
    return CaseView.of(
        await command.execute(
            signal_id=case_id,
            tenant_id=tenant_id,
            actor_account_id=actor.account_id,
            outcome=payload.outcome,
        )
    )


# --- La boucle boomerang ------------------------------------------------------------------------


@router.post(
    "/tenants/{tenant_id}/cases/{case_id}/contact",
    response_model=StartedContactView,
    status_code=status.HTTP_201_CREATED,
    summary="À appeler **avant** d'ouvrir WhatsApp ou le téléphone — l'effort s'écrit au départ",
)
async def start_contact(
    tenant_id: UUID,
    case_id: UUID,
    payload: StartContactBody,
    actor: CurrentActor,
    command: StartContactDep,
) -> StartedContactView:
    started = await command.execute(
        signal_id=case_id,
        tenant_id=tenant_id,
        by_account_id=actor.account_id,
        channel=payload.channel,
        person_label=payload.person_label,
    )
    return StartedContactView(attempt_id=started.attempt_id, prompt_at=started.prompt_at)


@router.get(
    "/tenants/{tenant_id}/pending-contacts",
    response_model=PendingAttemptListView,
    summary="Ce qu'on demande à la réouverture — borné à l'heure écoulée, une seule fois",
)
async def pending_contacts(
    tenant_id: UUID, actor: CurrentActor, query: PendingAttemptsDep
) -> PendingAttemptListView:
    return PendingAttemptListView.of(
        await query.execute(account_id=actor.account_id, tenant_id=tenant_id)
    )


@router.post(
    "/contacts/{attempt_id}/answer",
    response_model=ConcernAckView,
    summary="As-tu pu la joindre ? — répondu **une fois**, jamais réécrit",
)
async def answer_contact(
    attempt_id: UUID,
    payload: AnswerContactBody,
    actor: CurrentActor,
    command: AnswerContactDep,
) -> ConcernAckView:
    await command.execute(
        attempt_id=attempt_id, result=payload.result, commitment=payload.commitment
    )
    return ConcernAckView(message="Merci.")


@router.post(
    "/tenants/{tenant_id}/stop-contacting-me",
    response_model=ConcernAckView,
    summary="N'insistez plus — sans motif, immédiat, et définitif",
)
async def stop_contacting_me(
    tenant_id: UUID,
    actor: CurrentActor,
    command: StopContactingMeDep,
) -> ConcernAckView:
    """**Aucun corps de requête.** Pas de motif à donner, et pas de sujet à désigner : l'acteur est
    le sujet.

    Exiger une justification ferait de la sortie une négociation ; permettre de le poser pour
    quelqu'un d'autre en ferait, un jour, le moyen de se débarrasser d'un cas gênant."""
    stopped = await command.execute(
        tenant_id=tenant_id, actor_account_id=actor.account_id
    )
    return ConcernAckView(message=stopped.message)


@router.get(
    "/tenants/{tenant_id}/cases/{case_id}/context",
    response_model=CaseContextView,
    summary="Ce que vous relisez avant d'appeler — que du déjà-écrit, aucune conclusion",
)
async def case_context(
    tenant_id: UUID, case_id: UUID, actor: CurrentActor, query: CaseContextDep
) -> CaseContextView:
    """Six mois de lien en quatre lignes, assemblés par gabarits depuis des champs.

    Servi au **propriétaire du cas** et à personne d'autre : le même contrôle que le reste de
    l'écran, rien de nouveau à sécuriser."""
    return CaseContextView.of(
        await query.execute(
            signal_id=case_id, tenant_id=tenant_id, actor_account_id=actor.account_id
        )
    )
