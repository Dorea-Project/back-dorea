"""Persistance des demandes d'interprétation.

Rien ici ne raisonne — les transitions restent dans `capture/interpretation.py`. Une seule
chose mérite d'être dite, parce qu'elle se casse en silence.

🔴 **`add` ne lève jamais sur une demande déjà là, et rend celle qui fait foi.** *Une pièce,
une langue, une fois* : un pasteur qui appuie deux fois, ou dont la réponse s'est perdue en
route, ne doit pas ouvrir un second travail dans la file de l'équipe. Un `INSERT` nu lèverait
sur l'index unique, la route rendrait une erreur, et il recommencerait — jusqu'à ce qu'un
interprète découvre trois fois la même prière à traduire.

⚠️ **Le conflit se lit sur `(piece_id, language)`, pas sur la clé primaire.** L'identifiant
vient de l'appareil et change à chaque tentative si le client en produit un neuf ; la paire,
elle, désigne le travail. C'est elle qui dit « c'est la même demande ».
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.capture.interpretation import (
    Interpretation,
    InterpretationEtat,
)
from app.contexts.urim.infrastructure.persistence.models import UrimInterpretationModel


def _vers_domaine(ligne: UrimInterpretationModel) -> Interpretation:
    return Interpretation(
        id=ligne.id,
        piece_id=ligne.piece_id,
        church_id=ligne.church_id,
        requested_by=ligne.requested_by,
        language=ligne.language,
        state=InterpretationEtat(ligne.state),
        requested_at=ligne.requested_at,
        media_url=ligne.media_url,
        refused_reason=ligne.refused_reason,
        taken_at=ligne.taken_at,
        settled_at=ligne.settled_at,
    )


class SqlInterpretationRepository:
    """Les demandes d'interprétation, en Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, demande: Interpretation) -> Interpretation:
        await self._session.execute(
            pg_insert(UrimInterpretationModel)
            .values(
                id=demande.id,
                piece_id=demande.piece_id,
                church_id=demande.church_id,
                requested_by=demande.requested_by,
                language=demande.language,
                state=demande.state.value,
                requested_at=demande.requested_at,
            )
            # Redemander la même chose est l'ordinaire d'un réseau qui coupe.
            .on_conflict_do_nothing(
                index_elements=[
                    UrimInterpretationModel.piece_id,
                    UrimInterpretationModel.language,
                ]
            )
        )

        rangee = await self._pour(demande.piece_id, demande.language)
        return rangee if rangee is not None else demande

    async def get(self, demande_id: UUID) -> Interpretation | None:
        ligne = await self._session.get(UrimInterpretationModel, demande_id)
        return None if ligne is None else _vers_domaine(ligne)

    async def pour_piece(self, piece_id: UUID) -> tuple[Interpretation, ...]:
        lignes = await self._session.scalars(
            select(UrimInterpretationModel)
            .where(UrimInterpretationModel.piece_id == piece_id)
            .order_by(UrimInterpretationModel.requested_at)
        )
        return tuple(_vers_domaine(ligne) for ligne in lignes)

    async def save(self, demande: Interpretation) -> None:
        ligne = await self._session.get(UrimInterpretationModel, demande.id)
        if ligne is None:
            return

        ligne.state = demande.state.value
        ligne.media_url = demande.media_url
        ligne.refused_reason = demande.refused_reason
        ligne.taken_at = demande.taken_at
        ligne.settled_at = demande.settled_at

    async def _pour(self, piece_id: UUID, language: str) -> Interpretation | None:
        ligne = await self._session.scalar(
            select(UrimInterpretationModel).where(
                UrimInterpretationModel.piece_id == piece_id,
                UrimInterpretationModel.language == language,
            )
        )
        return None if ligne is None else _vers_domaine(ligne)
