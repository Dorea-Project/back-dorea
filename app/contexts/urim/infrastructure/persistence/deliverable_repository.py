"""Persistance du livrable et de ses contrôles.

Les deux écritures tiennent dans un seul geste : un livrable `conforme` sans les lignes qui le
prouvent serait un verdict sans dossier.

Et la lecture des versions vit ici aussi, pour une raison mesurée : **l'index du corpus ne
charge le texte que de la version de repli**. Q9 exige de juger contre toutes celles qu'on
détient — le texte des autres se lit donc en base, au moment du contrôle. C'est un geste rare
(quelques diapositives, une fois par livrable) ; charger quatre versions entières dans l'index
ferait payer à chaque résolution le prix d'un contrôle hebdomadaire.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.deliverable.application.ports import (
    ControleRecord,
    LivrableRecord,
    TexteServi,
)
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.contexts.urim.infrastructure.persistence.models import (
    UrimCitationCheckModel,
    UrimDeliverableModel,
)


class SqlDeliverableRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, record: LivrableRecord, controles: list[ControleRecord]) -> None:
        """⚠️ **Le livrable est vidé AVANT ses contrôles, et l'ordre n'est pas cosmétique.**

        🔴 Un seul `flush` à la fin échouait contre PostgreSQL :
        `urim_citation_check_deliverable_id_fkey` — la ligne fille partait la
        première, la clé étrangère refusait, et l'insertion du parent n'était
        jamais émise puisque la transaction était déjà avortée.

        La cause est que ces deux modèles ne sont liés que par une clé étrangère
        **de table**, sans `relationship()` : l'unité de travail n'a alors aucune
        dépendance à trier et ordonne par nom de table — et
        `urim_citation_check` précède `urim_deliverable` dans l'alphabet.

        Le défaut ne pouvait pas se voir : les tests tournent sur SQLite, qui
        n'applique pas les clés étrangères sans `PRAGMA foreign_keys=ON`. Le
        livrable n'avait donc jamais été écrit contre une vraie base.

        Deux `flush` plutôt qu'une `relationship()` : celle-ci n'existerait que
        pour ordonner, et ouvrirait un chargement paresseux dont ce dépôt ne
        veut nulle part."""
        self._s.add(UrimDeliverableModel(
            id=record.id,
            preparation_id=record.preparation_id,
            kind=record.kind,
            format=record.format,
            generated_at=record.generated_at,
            validation=record.validation,
            validated_by=record.validated_by,
            validated_at=record.validated_at,
            corpus_snapshot=record.corpus_snapshot,
            content_fingerprint=record.content_fingerprint,
        ))
        # Le parent existe en base avant qu'une ligne fille ne le désigne.
        await self._s.flush()

        for controle in controles:
            self._s.add(UrimCitationCheckModel(
                deliverable_id=record.id,
                slide_no=controle.slide_no,
                reference=controle.reference,
                projected_text=controle.projected_text,
                version_id=controle.version_id,
                verdict=controle.verdict,
            ))
        await self._s.flush()

    async def get(self, deliverable_id: UUID) -> LivrableRecord | None:
        row = await self._s.get(UrimDeliverableModel, deliverable_id)
        if row is None:
            return None
        return LivrableRecord(
            id=row.id,
            preparation_id=row.preparation_id,
            kind=row.kind,
            format=row.format,
            generated_at=row.generated_at,
            validation=row.validation or "rejete",
            validated_by=row.validated_by,
            validated_at=row.validated_at,
            corpus_snapshot=row.corpus_snapshot,
            content_fingerprint=row.content_fingerprint,
        )

    async def controles(self, deliverable_id: UUID) -> list[ControleRecord]:
        rows = (await self._s.execute(
            select(UrimCitationCheckModel)
            .where(UrimCitationCheckModel.deliverable_id == deliverable_id)
            .order_by(UrimCitationCheckModel.slide_no)
        )).scalars()
        return [
            ControleRecord(
                slide_no=r.slide_no,
                reference=r.reference,
                projected_text=r.projected_text,
                verdict=r.verdict,
                # ⚠️ Le motif **n'est pas stocké** : il se recalcule à l'affichage. Le corpus
                # peut apprendre une version qu'il ignorait, et une phrase figée en base
                # continuerait d'accuser un texte que le corpus reconnaît désormais.
                rationale="",
                version_id=r.version_id,
            )
            for r in rows
        ]


class SqlVerseTextReader:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def textes(
        self,
        *,
        book_id: int,
        chapter: int,
        verse_start: int | None,
        verse_end: int | None,
        prefer_version_id: UUID | None = None,
    ) -> list[TexteServi]:
        requete = (
            select(
                CorpusVerseModel.version_id,
                CorpusVersionModel.label,
                CorpusVerseModel.verse,
                CorpusVerseModel.body,
            )
            .join(CorpusVersionModel, CorpusVersionModel.id == CorpusVerseModel.version_id)
            .where(CorpusVerseModel.book_id == book_id)
            .where(CorpusVerseModel.chapter == chapter)
            .order_by(CorpusVerseModel.version_id, CorpusVerseModel.verse)
        )
        if verse_start is not None:
            requete = requete.where(CorpusVerseModel.verse >= verse_start)
            requete = requete.where(
                CorpusVerseModel.verse <= (verse_end or verse_start)
            )

        par_version: dict[UUID, tuple[str, list[str]]] = {}
        for version_id, label, _verset, corps in (await self._s.execute(requete)).all():
            _, morceaux = par_version.setdefault(version_id, (label, []))
            morceaux.append(corps)

        servis = [
            TexteServi(version_id=vid, label=label, texte=" ".join(morceaux))
            for vid, (label, morceaux) in par_version.items()
        ]
        # La version de la préparation d'abord — une **préférence**, pas une priorité : c'est
        # `juger_parmi` qui fait gagner `exact` sur `extrait`, quel que soit le rang.
        servis.sort(key=lambda t: (t.version_id != prefer_version_id, t.label))
        return servis
