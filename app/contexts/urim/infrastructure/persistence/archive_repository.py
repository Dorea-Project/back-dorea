"""Persistance de l'archive du prédicateur.

Rien ici ne raisonne. Les deux lectures portent en revanche une décision de produit chacune,
et c'est le SQL qui la tient :

- **la couverture compte des passages DISTINCTS** (`COUNT(DISTINCT …)`), parce qu'un lieu
  visité deux fois reste un lieu ;
- **la distribution compte des prédications**, parce que prêcher deux fois le même axe devant
  deux assemblées est deux fois ce travail-là.

Écrire l'un à la place de l'autre ne lèverait aucune erreur — ça rendrait seulement un
graphique faux, et personne ne le vérifierait.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.application.ports import AxisTally, BookCoverage, PreachedRecord
from app.contexts.urim.infrastructure.persistence.models import UrimPreachedModel


def _vers_record(row: UrimPreachedModel) -> PreachedRecord:
    return PreachedRecord(
        id=row.id,
        author_id=row.author_id,
        preached_on=row.preached_on,
        church_id=row.church_id,
        preparation_id=row.preparation_id,
        pericope_id=row.pericope_id,
        book_id=row.book_id,
        start_ch=row.start_ch,
        start_v=row.start_v,
        end_ch=row.end_ch,
        end_v=row.end_v,
        axis_code=row.axis_code,
        theme=row.theme,
        capture_kind=row.capture_kind,
    )


class SqlArchiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, record: PreachedRecord) -> None:
        self._s.add(UrimPreachedModel(
            id=record.id,
            preparation_id=record.preparation_id,
            church_id=record.church_id,
            author_id=record.author_id,
            preached_on=record.preached_on,
            pericope_id=record.pericope_id,
            book_id=record.book_id,
            start_ch=record.start_ch,
            start_v=record.start_v,
            end_ch=record.end_ch,
            end_v=record.end_v,
            axis_code=record.axis_code,
            theme=record.theme,
            capture_kind=record.capture_kind,
        ))
        await self._s.flush()

    async def list_for(self, author_id: UUID, *, limit: int) -> list[PreachedRecord]:
        rows = (await self._s.execute(
            select(UrimPreachedModel)
            .where(UrimPreachedModel.author_id == author_id)
            .order_by(UrimPreachedModel.preached_on.desc())
            .limit(limit)
        )).scalars()
        return [_vers_record(r) for r in rows]

    async def coverage(self, author_id: UUID) -> list[BookCoverage]:
        """Deux prédications du même texte ne rendent pas un canon deux fois plus large —
        mais elles restent deux faits. On rend donc les deux nombres.

        ⚠️ **Le `COUNT(DISTINCT (a,b,c,d))` évident n'est pas portable.** Postgres compte
        volontiers un tuple distinct ; SQLite refuse plus d'un argument dans un agrégat
        `DISTINCT` — et la base de test se construit depuis les modèles, en SQLite. La requête
        échouerait donc **uniquement en production**, ce qui est exactement le mode de panne
        que `confessionnel_borne` a coûté une correction à comprendre : *une garde qui n'existe
        que là où personne ne la vérifie*.

        On groupe donc par les bornes — ce que les deux bases savent faire — et on replie par
        livre ici. L'archive d'un pasteur compte une ligne par semaine : il n'y a rien à
        optimiser contre."""
        rows = (await self._s.execute(
            select(
                UrimPreachedModel.book_id,
                UrimPreachedModel.start_ch,
                UrimPreachedModel.start_v,
                UrimPreachedModel.end_ch,
                UrimPreachedModel.end_v,
                func.count(),
                func.max(UrimPreachedModel.preached_on),
            )
            .where(UrimPreachedModel.author_id == author_id)
            .where(UrimPreachedModel.book_id.is_not(None))
            .group_by(
                UrimPreachedModel.book_id,
                UrimPreachedModel.start_ch,
                UrimPreachedModel.start_v,
                UrimPreachedModel.end_ch,
                UrimPreachedModel.end_v,
            )
        )).all()

        par_livre: dict[int, BookCoverage] = {}
        for livre, _sc, _sv, _ec, _ev, combien, dernier in rows:
            acquis = par_livre.get(livre)
            if acquis is None:
                par_livre[livre] = BookCoverage(
                    book_id=livre, passages=1, preachings=combien,
                    last_preached_on=dernier,
                )
                continue
            acquis.passages += 1
            acquis.preachings += combien
            acquis.last_preached_on = max(acquis.last_preached_on, dernier)
        return [par_livre[livre] for livre in sorted(par_livre)]

    async def distribution(self, author_id: UUID) -> list[AxisTally]:
        # `axis_code` NULL forme un rayon comme les autres : `GROUP BY` le garde, et c'est
        # voulu — « non rangé » est un état, pas une absence de donnée.
        rows = (await self._s.execute(
            select(
                UrimPreachedModel.axis_code,
                func.count(),
                func.max(UrimPreachedModel.preached_on),
            )
            .where(UrimPreachedModel.author_id == author_id)
            .group_by(UrimPreachedModel.axis_code)
        )).all()
        return [
            AxisTally(axis_code=axe, preachings=total, last_preached_on=dernier)
            for axe, total, dernier in rows
        ]
