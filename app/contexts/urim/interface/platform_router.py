"""Surface **Plateforme** de la curation Urim — là où un humain signe ce que le moteur dira.

Gardée par le jeton de service Plateforme, et c'est structurel, pas prudentiel : aucune table
`urim_corpus_*` ne porte de `church_id`. Curer change ce que **toutes** les églises lisent ;
le geste n'a pas la portée d'un tenant.

⚠️ **`reviewed_by` est saisi, pas déduit.** Le jeton de service ne porte aucune identité —
il dit *« la Plateforme »*, pas *« qui »*. Tant que la console d'administration Dorea n'existe
pas, le relecteur se nomme lui-même, et la surface refuse les noms qui ne désignent personne.
C'est moins solide qu'une identité authentifiée, et c'est écrit ici pour qu'on n'oublie pas de
le remplacer plutôt que de s'y habituer.

**Chaque écriture purge l'index** (gelé par processus) : sans cela une curation tout juste
signée resterait invisible jusqu'au redémarrage. Elle change aussi l'empreinte du corpus, donc
les préparations ouvertes signalent `corpus_drifted` — leur trace n'est plus celle du jour.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.contexts.tenant.interface.dependencies import require_platform_token
from app.contexts.urim.application.curation import (
    BearingDraft,
    CaveatDraft,
    ContextDraft,
    FeasibilityDraft,
    PericopeDraft,
)
from app.contexts.urim.interface.curation_schemas import (
    BearingsBody,
    CaveatBody,
    ContextBody,
    CoverageView,
    FeasibilityBody,
    PericopeBody,
    PericopeCreatedView,
    PericopeView,
)
from app.contexts.urim.interface.dependencies import CurationDep

router = APIRouter(dependencies=[Depends(require_platform_token)])


@router.get(
    "/urim/coverage",
    response_model=CoverageView,
    summary="L'état réel de la curation — la seule mesure honnête d'Urim",
)
async def coverage(curation: CurationDep) -> CoverageView:
    return CoverageView.from_report(await curation.coverage())


@router.get(
    "/urim/pericopes",
    response_model=list[PericopeView],
    summary="Les unités curées, et ce qui leur manque",
)
async def list_pericopes(curation: CurationDep, book: str | None = None) -> list[PericopeView]:
    return [PericopeView.from_summary(s) for s in await curation.list_pericopes(book)]


@router.post(
    "/urim/pericopes",
    response_model=PericopeCreatedView,
    status_code=status.HTTP_201_CREATED,
    summary="Curer une unité littéraire — des bornes, et pourquoi celles-ci",
)
async def create_pericope(payload: PericopeBody, curation: CurationDep) -> PericopeCreatedView:
    nouvelle = await curation.create_pericope(PericopeDraft(
        book=payload.book, start_ch=payload.start_ch, start_v=payload.start_v,
        end_ch=payload.end_ch, end_v=payload.end_v, label=payload.label,
        rationale=payload.rationale, source_ref=payload.source_ref,
        reviewed_by=payload.reviewed_by,
    ))
    return PericopeCreatedView(id=nouvelle)


@router.put(
    "/urim/pericopes/{pericope_id}/bearings",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Peser les DIX loci d'un coup — « absent » compris (S38)",
)
async def set_bearings(
    pericope_id: UUID, payload: BearingsBody, curation: CurationDep
) -> None:
    await curation.set_bearings(
        pericope_id,
        [
            BearingDraft(b.axis_code, b.strength, b.rationale, b.source_ref)
            for b in payload.bearings
        ],
        payload.reviewed_by,
    )


@router.post(
    "/urim/pericopes/{pericope_id}/caveats",
    status_code=status.HTTP_201_CREATED,
    summary="Ce que le texte ne dit PAS — exégétique, ou confessionnel",
)
async def add_caveat(
    pericope_id: UUID, payload: CaveatBody, curation: CurationDep
) -> dict[str, UUID]:
    nouveau = await curation.add_caveat(
        pericope_id,
        CaveatDraft(
            axis_code=payload.axis_code, caveat_kind=payload.caveat_kind,
            body=payload.body, source_ref=payload.source_ref,
            tradition_scope=payload.tradition_scope,
        ),
        payload.reviewed_by,
    )
    return {"id": nouveau}


@router.post(
    "/urim/pericopes/{pericope_id}/context",
    status_code=status.HTTP_201_CREATED,
    summary="Contexte historique ou littéraire — sourcé, ou rien",
)
async def add_context(
    pericope_id: UUID, payload: ContextBody, curation: CurationDep
) -> dict[str, UUID]:
    nouveau = await curation.add_context(
        pericope_id,
        ContextDraft(
            context_kind=payload.context_kind, body=payload.body,
            ordinal=payload.ordinal, source_ref=payload.source_ref,
        ),
        payload.reviewed_by,
    )
    return {"id": nouveau}


@router.put(
    "/urim/pericopes/{pericope_id}/feasibility",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Les couples plan x matière — un refus voyage avec son motif",
)
async def set_feasibility(
    pericope_id: UUID, payload: FeasibilityBody, curation: CurationDep
) -> None:
    await curation.set_feasibility(
        pericope_id,
        [
            FeasibilityDraft(
                plan_source=c.plan_source, subject_matter=c.subject_matter,
                feasible=c.feasible, proof_text_risk=c.proof_text_risk,
                refusal_reason=c.refusal_reason,
            )
            for c in payload.couples
        ],
        payload.reviewed_by,
    )


@router.delete(
    "/urim/pericopes/{pericope_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer une curation fautive — sans quoi une erreur de relecture serait définitive",
)
async def delete_pericope(pericope_id: UUID, curation: CurationDep) -> None:
    await curation.delete_pericope(pericope_id)
