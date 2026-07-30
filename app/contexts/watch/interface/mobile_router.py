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
    CloseCaseDep,
    ListMyCasesDep,
    PendingAttemptsDep,
    RaiseConcernDep,
    SeeCaseDep,
    StartContactDep,
)
from app.contexts.watch.interface.schemas import (
    AnswerContactBody,
    CaseListView,
    CaseView,
    CloseCaseBody,
    ConcernAckView,
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
