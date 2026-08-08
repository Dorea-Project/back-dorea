"""Écriture du corpus curé. Rien ici ne juge — les gardes sont dans le service.

Une seule chose mérite d'être lue : la **couverture**. Elle se calcule en SQL parce que
c'est la seule mesure honnête de l'état d'Urim, et qu'une mesure honnête doit être facile
à obtenir. Tout le reste du moteur peut être parfait : hors des versets couverts, il
dégradera.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.application.curation import (
    BearingDraft,
    CaveatDraft,
    ContextDraft,
    CoverageReport,
    FeasibilityDraft,
    PericopeDraft,
    PericopeSummary,
)
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusBookNameModel,
    CorpusContextNoteModel,
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusHomileticFeasibilityModel,
    CorpusPericopeModel,
    CorpusVerseModel,
)


def _maintenant() -> datetime:
    return datetime.now(UTC)


class SqlCurationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add_pericope(self, draft: PericopeDraft, book_id: int) -> UUID:
        nouvelle = uuid4()
        self._s.add(CorpusPericopeModel(
            id=nouvelle, book_id=book_id,
            start_ch=draft.start_ch, start_v=draft.start_v,
            end_ch=draft.end_ch, end_v=draft.end_v,
            label=draft.label, rationale=draft.rationale, source_ref=draft.source_ref,
            reviewed_by=draft.reviewed_by, reviewed_at=_maintenant(),
        ))
        await self._s.flush()
        return nouvelle

    async def get_book_id(self, pericope_id: UUID) -> int | None:
        return await self._s.scalar(
            select(CorpusPericopeModel.book_id).where(CorpusPericopeModel.id == pericope_id)
        )

    async def replace_bearings(
        self, pericope_id: UUID, drafts: list[BearingDraft], reviewed_by: str
    ) -> None:
        # Remplacement en bloc : les dix loci forment un **acte de relecture**, pas dix
        # décisions séparées. Une mise à jour partielle laisserait un état mi-ancien
        # mi-nouveau qu'aucune signature ne couvrirait entièrement.
        await self._s.execute(
            delete(CorpusDoctrinalBearingModel).where(
                CorpusDoctrinalBearingModel.pericope_id == pericope_id
            )
        )
        quand = _maintenant()
        for d in drafts:
            self._s.add(CorpusDoctrinalBearingModel(
                pericope_id=pericope_id, axis_code=d.axis_code, strength=d.strength,
                rationale=d.rationale, source_ref=d.source_ref,
                reviewed_by=reviewed_by, reviewed_at=quand,
            ))
        await self._s.flush()

    async def add_caveat(
        self, pericope_id: UUID, draft: CaveatDraft, reviewed_by: str
    ) -> UUID:
        nouveau = uuid4()
        self._s.add(CorpusDoctrinalCaveatModel(
            id=nouveau, pericope_id=pericope_id, axis_code=draft.axis_code,
            body=draft.body, caveat_kind=draft.caveat_kind,
            tradition_scope=draft.tradition_scope, source_ref=draft.source_ref,
            reviewed_by=reviewed_by, reviewed_at=_maintenant(),
        ))
        await self._s.flush()
        return nouveau

    async def add_context(
        self, pericope_id: UUID, draft: ContextDraft, reviewed_by: str
    ) -> UUID:
        nouveau = uuid4()
        self._s.add(CorpusContextNoteModel(
            id=nouveau, pericope_id=pericope_id, context_kind=draft.context_kind,
            body=draft.body, ordinal=draft.ordinal, source_ref=draft.source_ref,
            reviewed_by=reviewed_by, reviewed_at=_maintenant(),
        ))
        await self._s.flush()
        return nouveau

    async def replace_feasibility(
        self, pericope_id: UUID, drafts: list[FeasibilityDraft], reviewed_by: str
    ) -> None:
        await self._s.execute(
            delete(CorpusHomileticFeasibilityModel).where(
                CorpusHomileticFeasibilityModel.pericope_id == pericope_id
            )
        )
        quand = _maintenant()
        for d in drafts:
            self._s.add(CorpusHomileticFeasibilityModel(
                pericope_id=pericope_id, plan_source=d.plan_source,
                subject_matter=d.subject_matter, feasible=d.feasible,
                refusal_reason=d.refusal_reason, proof_text_risk=d.proof_text_risk,
                reviewed_by=reviewed_by, reviewed_at=quand,
            ))
        await self._s.flush()

    async def resign_pericope(
        self, pericope_id: UUID, *, reviewed_by: str,
        label: str | None, rationale: str | None,
    ) -> bool:
        """La signature change, les bornes **non**.

        Déplacer les bornes en re-signant casserait silencieusement les pesées déjà accrochées :
        elles resteraient attachées à une unité qui n'est plus celle qu'on avait pesée. Pour
        d'autres bornes, on crée une autre unité — c'est plus long, et c'est honnête."""
        row = await self._s.get(CorpusPericopeModel, pericope_id)
        if row is None:
            return False
        row.reviewed_by = reviewed_by
        row.reviewed_at = datetime.now(UTC)
        if label is not None:
            row.label = label
        if rationale is not None:
            row.rationale = rationale
        await self._s.flush()
        return True

    async def delete_pericope(self, pericope_id: UUID) -> bool:
        row = await self._s.get(CorpusPericopeModel, pericope_id)
        if row is None:
            return False

        # ⚠️ **Les enfants se suppriment ici, explicitement.** Les clés étrangères vers
        # `urim_corpus_pericope` ne portent **pas** `ON DELETE CASCADE` — je l'avais supposé,
        # et le premier retrait réel a répondu 409. Vérifié : les trois FK sont nues.
        #
        # Et c'est bien ainsi : sur un corpus curé, effacer quatre tables doit se lire dans
        # le code. Une cascade rendrait silencieux l'effacement du travail d'un relecteur.
        for enfant in (
            CorpusDoctrinalBearingModel,
            CorpusDoctrinalCaveatModel,
            CorpusContextNoteModel,
            CorpusHomileticFeasibilityModel,
        ):
            await self._s.execute(
                delete(enfant).where(enfant.pericope_id == pericope_id)
            )
        await self._s.delete(row)
        await self._s.flush()
        return True

    async def list_pericopes(self, book_id: int | None) -> list[PericopeSummary]:
        libelles = dict(
            (await self._s.execute(
                select(CorpusBookNameModel.book_id, CorpusBookNameModel.label)
                .where(CorpusBookNameModel.language == "fr")
            )).all()
        )
        requete = select(CorpusPericopeModel).order_by(
            CorpusPericopeModel.book_id, CorpusPericopeModel.start_ch,
            CorpusPericopeModel.start_v,
        )
        if book_id is not None:
            requete = requete.where(CorpusPericopeModel.book_id == book_id)
        unites = (await self._s.execute(requete)).scalars().all()

        async def _compter(modele, pid: UUID) -> int:
            return await self._s.scalar(
                select(func.count()).select_from(modele).where(modele.pericope_id == pid)
            ) or 0

        resume = []
        for u in unites:
            resume.append(PericopeSummary(
                id=u.id, book=libelles.get(u.book_id, str(u.book_id)),
                start_ch=u.start_ch, start_v=u.start_v, end_ch=u.end_ch, end_v=u.end_v,
                label=u.label, reviewed_by=u.reviewed_by,
                n_bearings=await _compter(CorpusDoctrinalBearingModel, u.id),
                n_caveats=await _compter(CorpusDoctrinalCaveatModel, u.id),
                n_context=await _compter(CorpusContextNoteModel, u.id),
                n_feasibility=await _compter(CorpusHomileticFeasibilityModel, u.id),
            ))
        return resume

    async def coverage(self) -> CoverageReport:
        total = await self._s.scalar(select(func.count()).select_from(CorpusVerseModel)) or 0

        # Un verset est couvert s'il tombe dans une unité relue. La comparaison porte sur le
        # **couple (chapitre, verset)** et non sur deux colonnes indépendantes : sans cela,
        # une unité qui court de 5:16 à 6:2 couvrirait aussi 6:30.
        couverts = await self._s.scalar(text("""
            SELECT count(*) FROM urim_corpus_verse v
            WHERE EXISTS (
              SELECT 1 FROM urim_corpus_pericope p
              WHERE p.book_id = v.book_id
                AND (v.chapter, v.verse) >= (p.start_ch, p.start_v)
                AND (v.chapter, v.verse) <= (p.end_ch, p.end_v))
        """)) or 0

        n_unites = await self._s.scalar(
            select(func.count()).select_from(CorpusPericopeModel)
        ) or 0
        completes = await self._s.scalar(text("""
            SELECT count(*) FROM (
              SELECT p.id FROM urim_corpus_pericope p
              JOIN urim_corpus_doctrinal_bearing b ON b.pericope_id = p.id
              GROUP BY p.id HAVING count(*) >= 10) x
        """)) or 0

        par_locus = dict((await self._s.execute(text("""
            SELECT a.code, count(b.axis_code) FROM urim_corpus_doctrinal_axis a
            LEFT JOIN urim_corpus_doctrinal_bearing b ON b.axis_code = a.code
            GROUP BY a.code, a.ordinal ORDER BY a.ordinal
        """))).all())

        par_livre = dict((await self._s.execute(text("""
            SELECT n.label, count(*) FROM urim_corpus_pericope p
            JOIN urim_corpus_book_name n ON n.book_id = p.book_id AND n.language = 'fr'
            GROUP BY n.label ORDER BY count(*) DESC
        """))).all())

        return CoverageReport(
            verses_total=total, verses_covered=couverts,
            pericopes=n_unites, pericopes_completes=completes,
            par_locus=par_locus, par_livre=par_livre,
        )
