"""Routes **mobile** de la Présence (M6-0) — le responsable pointe sur le terrain.

Ouvrir une rencontre, marquer/dé-marquer présent (idempotent, hors-ligne-friendly), lire
le roster malin, clôturer. Authentifié par le JWT mobile (`CurrentActor`).
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.contexts.attendance.interface.dependencies import (
    AcknowledgeOccurrenceDep,
    AddVisitorDep,
    CancelAbsenceDep,
    CloseGatheringDep,
    ConvertVisitorDep,
    CreateGatheringDep,
    DeclareAbsenceDep,
    DeclareCadenceDep,
    GetCareListDep,
    GetCellHealthDep,
    GetGatheringRosterDep,
    GetGroupEffectifDep,
    GetGroupOverviewDep,
    GetGroupPulseDep,
    GetGroupTrendDep,
    GetMemberTrajectoryDep,
    GetMyPlannedAbsencesDep,
    ListGatheringVisitorsDep,
    MarkPresentDep,
    RemoveVisitorDep,
    SelfCheckInDep,
    UnmarkPresentDep,
)
from app.contexts.attendance.interface.schemas import (
    AcknowledgementResponse,
    AcknowledgeOccurrenceRequest,
    AddVisitorRequest,
    CadenceResponse,
    CareListResponse,
    CellHealthResponse,
    ConvertVisitorRequest,
    ConvertVisitorResponse,
    CreateGatheringRequest,
    DeclareAbsenceRequest,
    DeclareCadenceRequest,
    GatheringResponse,
    GroupEffectifResponse,
    GroupPulseResponse,
    GroupTrendResponse,
    GroupVitalsResponse,
    MemberTrajectoryResponse,
    PlannedAbsenceResponse,
    RosterResponse,
    SelfCheckInRequest,
    SelfCheckInResponse,
    VisitorResponse,
)
from app.contexts.auth.interface.dependencies import CurrentActor

router = APIRouter()


@router.post(
    "/tenants/{tenant_id}/groups/{group_id}/gatherings",
    response_model=GatheringResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ouvrir une rencontre de groupe (réunion, formation…)",
)
async def create_gathering(
    tenant_id: UUID,
    group_id: UUID,
    payload: CreateGatheringRequest,
    actor: CurrentActor,
    command: CreateGatheringDep,
) -> GatheringResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        type=payload.type,
        scheduled_at=payload.scheduled_at,
        title=payload.title,
    )
    return GatheringResponse.from_dto(dto)


@router.post(
    "/self-check-in",
    response_model=SelfCheckInResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Self-check-in : le membre tape le code de séance → présent (2ᵉ voix)",
)
async def self_check_in(
    payload: SelfCheckInRequest,
    actor: CurrentActor,
    command: SelfCheckInDep,
) -> SelfCheckInResponse:
    dto = await command.execute(actor_account_id=actor.account_id, code=payload.code)
    return SelfCheckInResponse.from_dto(dto)


@router.get(
    "/gatherings/{gathering_id}/roster",
    response_model=RosterResponse,
    summary="Roster malin : qui est attendu, qui est présent (absence déduite)",
)
async def get_roster(
    gathering_id: UUID,
    actor: CurrentActor,
    query: GetGatheringRosterDep,
) -> RosterResponse:
    dto = await query.execute(actor_account_id=actor.account_id, gathering_id=gathering_id)
    return RosterResponse.from_dto(dto)


@router.put(
    "/gatherings/{gathering_id}/present/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Marquer présent (idempotent)",
)
async def mark_present(
    gathering_id: UUID,
    account_id: UUID,
    actor: CurrentActor,
    command: MarkPresentDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id, gathering_id=gathering_id, account_id=account_id
    )


@router.delete(
    "/gatherings/{gathering_id}/present/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dé-marquer présent (idempotent)",
)
async def unmark_present(
    gathering_id: UUID,
    account_id: UUID,
    actor: CurrentActor,
    command: UnmarkPresentDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id, gathering_id=gathering_id, account_id=account_id
    )


@router.post(
    "/gatherings/{gathering_id}/close",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clôturer la rencontre (fige la trajectoire)",
)
async def close_gathering(
    gathering_id: UUID,
    actor: CurrentActor,
    command: CloseGatheringDep,
) -> None:
    await command.execute(actor_account_id=actor.account_id, gathering_id=gathering_id)


# --- M6-2 : pré-déclaration d'absence (la dignité de prévenir) ---


@router.post(
    "/tenants/{tenant_id}/absences",
    response_model=PlannedAbsenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Déclarer son absence sur une période (tag + du…au…)",
)
async def declare_absence(
    tenant_id: UUID,
    payload: DeclareAbsenceRequest,
    actor: CurrentActor,
    command: DeclareAbsenceDep,
) -> PlannedAbsenceResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        reason=payload.reason,
        from_date=payload.from_date,
        to_date=payload.to_date,
        note=payload.note,
    )
    return PlannedAbsenceResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/absences",
    response_model=list[PlannedAbsenceResponse],
    summary="Mes absences déclarées (actives)",
)
async def my_absences(
    tenant_id: UUID,
    actor: CurrentActor,
    query: GetMyPlannedAbsencesDep,
) -> list[PlannedAbsenceResponse]:
    dtos = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return [PlannedAbsenceResponse.from_dto(d) for d in dtos]


@router.delete(
    "/absences/{absence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Annuler une absence déclarée (la sienne)",
)
async def cancel_absence(
    absence_id: UUID,
    actor: CurrentActor,
    command: CancelAbsenceDep,
) -> None:
    await command.execute(actor_account_id=actor.account_id, absence_id=absence_id)


# --- M7-0 : pulsation de la cellule (l'intelligence pastorale) ---


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/pulse",
    response_model=GroupPulseResponse,
    summary="La pulsation de la cellule : état de marche par membre (soin, pas jugement)",
)
async def group_pulse(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentActor,
    query: GetGroupPulseDep,
) -> GroupPulseResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id
    )
    return GroupPulseResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/effectif",
    response_model=GroupEffectifResponse,
    summary="Effectif réel : membres vivants + candidats à revoir (suggestion, jamais auto)",
)
async def group_effectif(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentActor,
    query: GetGroupEffectifDep,
) -> GroupEffectifResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id
    )
    return GroupEffectifResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/care-list",
    response_model=CareListResponse,
    summary="Liste « à interpeller » sur toute l'église (soin ; autorité pastorale église-entière)",
)
async def care_list(
    tenant_id: UUID,
    actor: CurrentActor,
    query: GetCareListDep,
) -> CareListResponse:
    dto = await query.execute(actor_account_id=actor.account_id, tenant_id=tenant_id)
    return CareListResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/health",
    response_model=CellHealthResponse,
    summary="Santé de cellule : inscrits vs présents réels, ready_to_multiply honnête (M7-3)",
)
async def cell_health(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentActor,
    query: GetCellHealthDep,
) -> CellHealthResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id
    )
    return CellHealthResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/overview",
    response_model=GroupVitalsResponse,
    summary="Détail d'un groupe : infos + réalités (effectif réel, à-risque, multiplication)",
)
async def group_overview(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentActor,
    query: GetGroupOverviewDep,
) -> GroupVitalsResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id
    )
    return GroupVitalsResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/trend",
    response_model=GroupTrendResponse,
    summary="Tendance du groupe : monte-t-il ou fond-il ? (effectif réel semaine par semaine)",
)
async def group_trend(
    tenant_id: UUID,
    group_id: UUID,
    actor: CurrentActor,
    query: GetGroupTrendDep,
    weeks: int = 8,
) -> GroupTrendResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id, tenant_id=tenant_id, group_id=group_id, weeks=weeks
    )
    return GroupTrendResponse.from_dto(dto)


@router.get(
    "/tenants/{tenant_id}/groups/{group_id}/members/{account_id}/trajectory",
    response_model=MemberTrajectoryResponse,
    summary="Trajectoire d'un membre : sa frise + son histoire (comprendre avant de soigner)",
)
async def member_trajectory(
    tenant_id: UUID,
    group_id: UUID,
    account_id: UUID,
    actor: CurrentActor,
    query: GetMemberTrajectoryDep,
) -> MemberTrajectoryResponse:
    dto = await query.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        account_id=account_id,
    )
    return MemberTrajectoryResponse.from_dto(dto)


# --- M6-3 : visiteurs (visages nouveaux, l'entonnoir) ---


@router.post(
    "/gatherings/{gathering_id}/visitors",
    response_model=VisitorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Capturer un visiteur (visage nouveau, hors roster)",
)
async def add_visitor(
    gathering_id: UUID,
    payload: AddVisitorRequest,
    actor: CurrentActor,
    command: AddVisitorDep,
) -> VisitorResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        gathering_id=gathering_id,
        name=payload.name,
        phone=payload.phone,
    )
    return VisitorResponse.from_dto(dto)


@router.get(
    "/gatherings/{gathering_id}/visitors",
    response_model=list[VisitorResponse],
    summary="Les visiteurs d'une rencontre",
)
async def list_visitors(
    gathering_id: UUID,
    actor: CurrentActor,
    query: ListGatheringVisitorsDep,
) -> list[VisitorResponse]:
    dtos = await query.execute(actor_account_id=actor.account_id, gathering_id=gathering_id)
    return [VisitorResponse.from_dto(d) for d in dtos]


@router.post(
    "/gatherings/{gathering_id}/visitors/{visitor_id}/convert",
    response_model=ConvertVisitorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Convertir un visiteur en membre (invited) + l'inscrire à la cellule (entonnoir)",
)
async def convert_visitor(
    gathering_id: UUID,
    visitor_id: UUID,
    payload: ConvertVisitorRequest,
    actor: CurrentActor,
    command: ConvertVisitorDep,
) -> ConvertVisitorResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        visitor_id=visitor_id,
        phone=payload.phone,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    return ConvertVisitorResponse.from_dto(dto)


@router.delete(
    "/gatherings/{gathering_id}/visitors/{visitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un visiteur (saisi par erreur)",
)
async def remove_visitor(
    gathering_id: UUID,
    visitor_id: UUID,
    actor: CurrentActor,
    command: RemoveVisitorDep,
) -> None:
    await command.execute(
        actor_account_id=actor.account_id, gathering_id=gathering_id, visitor_id=visitor_id
    )


# --- Cadence : le rythme du groupe, et « pas de rencontre cette semaine » ---------------------
#
# Sans cette surface, `ManageCadence` et l'acquittement restaient écrits, testés, migrés — et
# appelés par personne. Le responsable ne pouvait pas déclarer une occurrence non tenue, et la
# couverture signalait des groupes aveugles à Noël alors que tout le monde savait pourquoi.


@router.post(
    "/tenants/{tenant_id}/groups/{group_id}/cadence",
    response_model=CadenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Déclarer le rythme attendu du groupe (une seule cadence active à la fois)",
)
async def declare_cadence(
    tenant_id: UUID,
    group_id: UUID,
    payload: DeclareCadenceRequest,
    actor: CurrentActor,
    command: DeclareCadenceDep,
) -> CadenceResponse:
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        frequency=payload.frequency,
        anchor_date=payload.anchor_date,
        active_from=payload.active_from,
        weekday=payload.weekday,
        day_of_month=payload.day_of_month,
        active_until=payload.active_until,
    )
    return CadenceResponse.from_dto(dto)


@router.post(
    "/tenants/{tenant_id}/groups/{group_id}/acknowledgements",
    response_model=AcknowledgementResponse,
    summary="« Pas de rencontre cette semaine » — motif connu, occurrence acquittée (idempotent)",
)
async def acknowledge_occurrence(
    tenant_id: UUID,
    group_id: UUID,
    payload: AcknowledgeOccurrenceRequest,
    actor: CurrentActor,
    command: AcknowledgeOccurrenceDep,
) -> AcknowledgementResponse:
    # Idempotent : re-poser le même acquittement renvoie l'existant. Un responsable qui tape
    # deux fois n'a pas à se demander s'il a créé un doublon.
    dto = await command.execute(
        actor_account_id=actor.account_id,
        tenant_id=tenant_id,
        group_id=group_id,
        occurrence_date=payload.occurrence_date,
        reason=payload.reason,
    )
    return AcknowledgementResponse.from_dto(dto)
