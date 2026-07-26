"""Use case `DecideSubjectConsent` — le sujet accepte, ou refuse, d'être nommé.

Une annonce qui dit la maladie de quelqu'un attend son accord avant de paraître. Personne ne
consent à sa place : ni le pasteur, ni le responsable, ni l'auteur de l'annonce. C'est la seule
opération du module dont l'autorité n'est pas un rôle mais **une identité**.

Le refus est terminal : l'annonce ne paraîtra jamais, et aucun effet de veille n'est posé. Ce
n'est pas une censure du responsable — c'est la personne qui garde ce qui la regarde.

L'accord donné plus tard **rejoue** les effets, toujours datés de l'événement : accepter le 20
une maladie survenue le 12 neutralise depuis le 12, pas depuis le 20.
"""

from __future__ import annotations

from uuid import UUID

from app.contexts.announcements.application.dtos import AnnouncementDTO
from app.contexts.announcements.application.mapping import to_announcement_dto
from app.contexts.announcements.application.watch_effects import EmitAnnouncementFacts
from app.contexts.announcements.domain.errors import (
    AnnouncementNotFoundError,
    NotTheSubjectError,
)
from app.contexts.announcements.domain.repositories import (
    AnnouncementRepository,
    AnnouncementSubjectRepository,
)


class DecideSubjectConsent:
    def __init__(
        self,
        announcements: AnnouncementRepository,
        subjects: AnnouncementSubjectRepository,
        watch_effects: EmitAnnouncementFacts | None = None,
        *,
        clock,
    ) -> None:
        self._announcements = announcements
        self._subjects = subjects
        self._watch_effects = watch_effects
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, announcement_id: UUID, accept: bool
    ) -> AnnouncementDTO:
        announcement = await self._announcements.get(announcement_id)
        if announcement is None:
            raise AnnouncementNotFoundError("Annonce introuvable.")

        all_subjects = await self._subjects.list_for(announcement_id)
        mine = next(
            (s for s in all_subjects if s.account_id == actor_account_id and s.awaits_consent),
            None,
        )
        if mine is None:
            raise NotTheSubjectError("Aucun accord n'est attendu de vous sur cette annonce.")

        now = self._clock()
        if accept:
            mine.grant(now=now)
        else:
            mine.refuse(now=now)
        await self._subjects.save(mine)

        if not accept:
            # Un seul refus suffit : on ne publie pas une annonce amputée de son sujet.
            announcement.decline()
            await self._announcements.save(announcement)
        elif not any(s.awaits_consent for s in all_subjects):
            # Dernier accord attendu : l'annonce entre dans le fil, et les effets se posent.
            announcement.release()
            await self._announcements.save(announcement)
            if self._watch_effects is not None:
                await self._watch_effects.execute(
                    announcement=announcement, subjects=all_subjects
                )

        return to_announcement_dto(
            announcement,
            viewer_account_id=actor_account_id,
            subject_account_ids={s.account_id for s in all_subjects},
        )
