"""Persistance des pièces publiées.

Rien ici ne raisonne — la règle du domaine reste dans `capture/piece.py`. Une seule chose
mérite d'être dite, parce qu'elle se casse en silence.

🔴 **`add` ne lève jamais sur une pièce déjà connue, et rend celle qui fait foi.**
L'appareil produit l'identifiant avant que le réseau existe (D64). Un pasteur qui appuie
deux fois sur « publier » dans un tunnel — ou dont la réponse s'est perdue en route —
renverra la même pièce. Un `INSERT` nu lèverait sur la clé primaire, la route rendrait une
erreur, et il recommencerait : jusqu'à ce qu'il abandonne, ou que son assemblée reçoive la
même prière trois fois.

⚠️ **Et le retour n'est pas symbolique.** Sur un doublon, c'est la **première** ligne qui
compte : son `media_url` désigne les octets déjà rangés, et son `published_at` dit quand la
pièce a réellement traversé. Rendre la seconde ferait dériver la date de publication à
chaque tentative, sur un objet dont l'assemblée lit justement la chronologie.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.capture.piece import Piece
from app.contexts.urim.infrastructure.persistence.models import UrimPieceModel


def _vers_domaine(ligne: UrimPieceModel) -> Piece:
    return Piece(
        id=ligne.id,
        capture_id=ligne.capture_id,
        church_id=ligne.church_id,
        author_id=ligne.author_id,
        title=ligne.title,
        start_ms=ligne.start_ms,
        end_ms=ligne.end_ms,
        media_url=ligne.media_url,
        cut_at=ligne.cut_at,
        published_at=ligne.published_at,
    )


class SqlPieceRepository:
    """Les pièces, en Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, piece: Piece) -> Piece:
        """Range la pièce, ou rend celle qui portait déjà cet identifiant."""
        await self._session.execute(
            pg_insert(UrimPieceModel)
            .values(
                id=piece.id,
                capture_id=piece.capture_id,
                church_id=piece.church_id,
                author_id=piece.author_id,
                title=piece.title,
                start_ms=piece.start_ms,
                end_ms=piece.end_ms,
                media_url=piece.media_url,
                cut_at=piece.cut_at,
                published_at=piece.published_at,
            )
            # Le doublon est l'ordinaire d'une file qui reprend, pas un incident.
            .on_conflict_do_nothing(index_elements=[UrimPieceModel.id])
        )

        # On relit plutôt que de rendre l'argument : sur un doublon, c'est la ligne déjà
        # présente qui fait foi — voir l'en-tête.
        rangee = await self.get(piece.id)
        return rangee if rangee is not None else piece

    async def get(self, piece_id: UUID) -> Piece | None:
        ligne = await self._session.get(UrimPieceModel, piece_id)
        return None if ligne is None else _vers_domaine(ligne)

    async def pour_eglise(self, church_id: UUID, *, limite: int = 50) -> tuple[Piece, ...]:
        lignes = await self._session.scalars(
            select(UrimPieceModel)
            .where(UrimPieceModel.church_id == church_id)
            .order_by(UrimPieceModel.published_at.desc())
            .limit(limite)
        )
        return tuple(_vers_domaine(ligne) for ligne in lignes)
