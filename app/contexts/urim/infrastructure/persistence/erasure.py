"""Effacement du contenu Urim d'un compte — mise en œuvre du port `AccountContentEraser`.

Ce fichier vit dans `urim` et non dans `auth` pour une raison simple : c'est ici que
les tables sont connues. Auth sait fermer un compte ; il n'a pas à apprendre ce qu'une
préparation contient pour le détruire.

## L'ordre n'est pas décoratif

Deux tables pointent vers `urim_preparation` **sans** `ON DELETE CASCADE` —
`urim_preached` et `urim_deliverable` : supprimer les préparations d'abord ferait
échouer la transaction sur une contrainte, et un compte à demi effacé est pire qu'un
compte intact, puisque plus personne ne sait ce qu'il en reste. Les enfants partent
donc avant leurs parents, et tout tient dans **une seule transaction** : celle de la
requête qui l'a demandé.

## Ce qui n'est pas effacé

`urim_usage_window` est un compteur **d'église**, pas une donnée personnelle : il ne
porte aucun `author_id` et son plafond concerne une communauté. Le corpus biblique,
lui, n'appartient à personne.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.auth.application.ports import AccountContentEraser
from app.contexts.urim.infrastructure.persistence.models import (
    UrimCaptureJobModel,
    UrimCaptureModel,
    UrimCitedVerseModel,
    UrimDeliverableModel,
    UrimPreachedModel,
    UrimPreparationModel,
    UrimReflectionModel,
    UrimStudyReservationModel,
    UrimTranscriptSegmentModel,
)


class SqlUrimContentEraser(AccountContentEraser):
    """Efface préparations, captures, retours et réservations d'un auteur."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def erase(self, account_id: UUID) -> None:
        preparations = (
            await self._session.scalars(
                select(UrimPreparationModel.id).where(UrimPreparationModel.author_id == account_id)
            )
        ).all()

        captures = (
            await self._session.scalars(
                select(UrimCaptureModel.id).where(UrimCaptureModel.author_id == account_id)
            )
        ).all()

        # --- Ce qui pend aux captures : lié par `capture_id`, sans clé étrangère
        # (intégrité applicative assumée côté modèles) — donc rien ne partirait tout seul.
        if captures:
            for model in (
                UrimCaptureJobModel,
                UrimTranscriptSegmentModel,
                UrimCitedVerseModel,
            ):
                await self._session.execute(delete(model).where(model.capture_id.in_(captures)))

        await self._session.execute(
            delete(UrimCaptureModel).where(UrimCaptureModel.author_id == account_id)
        )

        # --- Ce qui pend aux préparations sans cascade
        await self._session.execute(
            delete(UrimPreachedModel).where(UrimPreachedModel.author_id == account_id)
        )

        if preparations:
            # Les contrôles de citation cascadent depuis le livrable ; le livrable, lui,
            # ne cascade pas depuis la préparation.
            await self._session.execute(
                delete(UrimDeliverableModel).where(
                    UrimDeliverableModel.preparation_id.in_(preparations)
                )
            )

        # --- Les racines. Éléments, écartés, appuis, tentatives et suggestions
        # s'en vont avec elles (`ON DELETE CASCADE`).
        await self._session.execute(
            delete(UrimPreparationModel).where(UrimPreparationModel.author_id == account_id)
        )

        await self._session.execute(
            delete(UrimReflectionModel).where(UrimReflectionModel.author_id == account_id)
        )

        # Le grand livre du quota personnel : quels textes, quels mois. C'est une trace
        # d'activité nominative, elle part avec le reste.
        await self._session.execute(
            delete(UrimStudyReservationModel).where(
                UrimStudyReservationModel.author_id == account_id
            )
        )

        await self._session.flush()
