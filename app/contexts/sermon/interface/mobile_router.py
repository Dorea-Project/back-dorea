"""Routes **mobile** du module Sermon — le pasteur qui dépose et fait vivre son sermon.

Déposer (brouillon), relire, approuver, publier. Autorité `PUBLISH_SERMON` (toute l'église).
JWT mobile. Le membre, lui, verra les **capsules** publiées dans le fil (S-2), pas ce texte brut.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Request, status

from app._shared.interface.request_body import read_body_capped
from app.api.deps import SettingsDep
from app.contexts.auth.interface.dependencies import CurrentActor
from app.contexts.sermon.domain.enums import SermonSourceKind
from app.contexts.sermon.interface.dependencies import (
    AdvanceCompanionDep,
    AnswerAttendanceDep,
    ApproveSermonDep,
    DepositSermonDep,
    GetSermonDep,
    ListTenantSermonsDep,
    PublishSermonDep,
    StartCompanionDep,
)
from app.contexts.sermon.interface.schemas import (
    AnswerAttendanceBody,
    CompanionCardView,
    DepositSermonBody,
    SermonListView,
    SermonView,
)

# R0 — l'alias déprécié de la reconnaissance emprunte **tout** à `watch` : la commande, sa
# dépendance et ses deux schémas. Rien n'en est recopié ici, sans quoi les deux URL finiraient
# par ne plus décrire le même geste.
from app.contexts.watch.interface.dependencies import DepositGratitudeDep
from app.contexts.watch.interface.schemas import (
    DepositGratitudeBody,
    GratitudeDepositedView,
)

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}",
    response_model=SermonView,
    status_code=status.HTTP_201_CREATED,
    summary="Déposer un sermon (texte) — il naît brouillon, en attente d'approbation",
)
async def deposit_sermon(
    tenant_id: UUID,
    payload: DepositSermonBody,
    actor: CurrentActor,
    command: DepositSermonDep,
) -> SermonView:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        title=payload.title,
        content=payload.content,
        preached_on=payload.preached_on,
        reference=payload.reference,
    )
    return SermonView.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}/upload",
    response_model=SermonView,
    status_code=status.HTTP_201_CREATED,
    summary="Déposer un sermon depuis un fichier PDF/PPTX (corps brut) → texte extrait, brouillon",
)
async def upload_sermon(
    tenant_id: UUID,
    title: str,
    preached_on: date,
    kind: SermonSourceKind,
    request: Request,
    actor: CurrentActor,
    command: DepositSermonDep,
    settings: SettingsDep,
    reference: str | None = None,
) -> SermonView:
    # Lecture **bornée** du fichier (anti-DoS mémoire) avant extraction/parsing. Le `kind` est
    # ici **déclaré** : les octets sont recoupés contre lui en amont du parseur, dans le use case
    # (`application/upload_guard.ensure_declared_kind`) — après l'autorisation, avant l'extraction.
    data = await read_body_capped(request, max_bytes=settings.sermon_max_bytes)
    dto = await command.execute_file(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        title=title,
        data=data,
        kind=kind,
        preached_on=preached_on,
        reference=reference,
    )
    return SermonView.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}",
    response_model=SermonListView,
    summary="Les sermons de l'église (tous statuts) — la vue du pasteur",
)
async def list_sermons(
    tenant_id: UUID,
    actor: CurrentActor,
    query: ListTenantSermonsDep,
) -> SermonListView:
    dtos = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return SermonListView.from_dtos(dtos)


@router.get(
    "/{sermon_id}",
    response_model=SermonView,
    summary="Ouvrir un sermon pour le relire",
)
async def get_sermon(
    sermon_id: UUID,
    actor: CurrentActor,
    query: GetSermonDep,
) -> SermonView:
    dto = await query.execute(actor_account_id=actor.account_id, sermon_id=sermon_id)
    return SermonView.from_dto(dto)


@router.post(
    "/{sermon_id}/approve",
    response_model=SermonView,
    summary="Approuver un brouillon — le pasteur y met son onction (relira le digest dès S-1)",
)
async def approve_sermon(
    sermon_id: UUID,
    actor: CurrentActor,
    command: ApproveSermonDep,
) -> SermonView:
    dto = await command.execute(actor_account_id=actor.account_id, sermon_id=sermon_id)
    return SermonView.from_dto(dto)


@router.post(
    "/{sermon_id}/publish",
    response_model=SermonView,
    summary="Publier un sermon approuvé (rien de non approuvé n'atteint le membre)",
)
async def publish_sermon(
    sermon_id: UUID,
    actor: CurrentActor,
    command: PublishSermonDep,
) -> SermonView:
    dto = await command.execute(actor_account_id=actor.account_id, sermon_id=sermon_id)
    return SermonView.from_dto(dto)


# --- Le compagnon (membre) — conversation privée, déterministe ---


@router.post(
    "/{sermon_id}/companion",
    response_model=CompanionCardView,
    summary="Ouvrir (ou reprendre) le compagnon d'un sermon publié → la question d'entrée",
)
async def start_companion(
    sermon_id: UUID,
    actor: CurrentActor,
    command: StartCompanionDep,
) -> CompanionCardView:
    dto = await command.execute(actor_account_id=actor.account_id, sermon_id=sermon_id)
    return CompanionCardView.from_dto(dto)


@router.post(
    "/companion/{session_id}/attendance",
    response_model=CompanionCardView,
    summary="Répondre « as-tu vécu le culte ? » → consolidation (oui) ou enseignement (non)",
)
async def answer_attendance(
    session_id: UUID,
    payload: AnswerAttendanceBody,
    actor: CurrentActor,
    command: AnswerAttendanceDep,
) -> CompanionCardView:
    dto = await command.execute(
        actor_account_id=actor.account_id, session_id=session_id, attended=payload.attended
    )
    return CompanionCardView.from_dto(dto)


@router.post(
    "/companion/{session_id}/next",
    response_model=CompanionCardView,
    summary="Étape suivante du compagnon (à la fin, un mot de clôture)",
)
async def advance_companion(
    session_id: UUID,
    actor: CurrentActor,
    command: AdvanceCompanionDep,
) -> CompanionCardView:
    dto = await command.execute(actor_account_id=actor.account_id, session_id=session_id)
    return CompanionCardView.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}/gratitude",
    response_model=GratitudeDepositedView,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    summary="[Déprécié → /api/mobile/watch/tenants/{tenant_id}/gratitude] Déposer un sujet "
            "de reconnaissance",
)
async def deposit_gratitude_alias(
    tenant_id: UUID,
    payload: DepositGratitudeBody,
    actor: CurrentActor,
    command: DepositGratitudeDep,
) -> GratitudeDepositedView:
    """**R0 — alias temporaire. Le geste a déménagé, pas changé.**

    La commande, ses schémas et sa route vivent maintenant dans `watch`, où le fait, l'interpreter
    et la source `COMPANION` étaient déjà. Cette URL reste ouverte parce que le client mobile est
    dans un autre dépôt et ne se déploie pas en même temps que celui-ci : la couper d'un coup
    ferait disparaître, sans prévenir, la seule parole du membre qui dise que ça va.

    **Aucune duplication en dessous** : même commande, mêmes schémas, même dépendance — importés
    de `watch`. Deux implémentations divergeraient, et le client verrait deux contrats pour un
    même geste.

    ⚠️ **À supprimer avec le contexte (R4)**, ou dès que le client mobile appelle la nouvelle URL,
    selon ce qui vient en premier. Un alias qu'on oublie de retirer n'est plus une transition,
    c'est une seconde API.
    """
    accepted = await command.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, subject=payload.subject
    )
    return GratitudeDepositedView(is_life_sign=accepted)
