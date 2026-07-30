"""Les Annonces comme **source** du moteur de veille — elles émettent, elles n'écrivent pas.

Une annonce qui nomme quelqu'un produit un `LIFE_EVENT_ANNOUNCED` par sujet, et s'arrête là.
Ce qu'il advient — neutraliser, ouvrir un cas, retirer de la veille — n'est plus décidé ici :
c'est l'affaire de l'engine, qui interprète, arbitre et matérialise. Le contexte Annonces ne
connaît plus ni les absences planifiées, ni M7.

Deux gardes restent de ce côté-ci, parce qu'elles relèvent de la publication et non de la veille :

- **le consentement.** Un sujet dont le rôle est intime et qui n'a pas encore accepté d'être
  nommé n'émet aucun fait. Rien n'entre au ledger tant qu'il n'a pas dit oui — c'est plus fort
  qu'un filtre en aval, puisqu'il n'y a rien à filtrer ;
- **l'idempotence de l'identité du fait.** `fact_id` est dérivé de `(annonce, personne)` : rejouer
  une publication, ou rejouer le backfill, ne produit jamais deux faits pour le même sujet.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from app.contexts.announcements.domain.aggregates import Announcement, AnnouncementSubject
from app.contexts.watch.application.intake import Intake, warn_if_disconnected
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import ANNOUNCEMENTS

_FACT_NAMESPACE = uuid5(NAMESPACE_URL, "dorea:watch:life_event_announced")


def fact_id_for(announcement_id: UUID, account_id: UUID) -> UUID:
    """Identité **dérivée**, donc stable : la même paire donne toujours le même fait."""
    return uuid5(_FACT_NAMESPACE, f"{announcement_id}:{account_id}")


def build_fact(
    announcement: Announcement, subject: AnnouncementSubject, *, recorded_at
) -> Fact:
    """Le fait tel que la source le propose — daté de l'**événement**, pas de la publication."""
    assert announcement.tenant_id is not None  # garanti par l'appelant
    return Fact(
        fact_id=fact_id_for(announcement.id, subject.account_id),
        tenant_id=announcement.tenant_id,
        occurred_at=announcement.event_date,
        recorded_at=recorded_at,
        source=ANNOUNCEMENTS,
        kind=FactKind.LIFE_EVENT_ANNOUNCED,
        subject_kind=SubjectKind.PERSON,
        subject_id=subject.account_id,
        payload={
            "announcement_id": str(announcement.id),
            "category": announcement.category.value,
            "role": subject.role.value,
            "effects": [e.value for e in subject.effects],
            "declared_duration_days": subject.declared_duration_days,
            "actor_account_id": str(announcement.author_account_id),
        },
    )


class EmitAnnouncementFacts:
    """Fait entrer dans le moteur les sujets **effectifs** d'une annonce."""

    def __init__(self, intake: Intake | None, *, clock) -> None:
        warn_if_disconnected("announcements", intake)
        self._intake = intake
        self._clock = clock

    async def execute(
        self, *, announcement: Announcement, subjects: list[AnnouncementSubject]
    ) -> list[AnnouncementSubject]:
        # Une annonce plateforme n'appartient à aucune église : elle n'a pas de veille à toucher.
        if self._intake is None or announcement.tenant_id is None:
            return []

        recorded_at = self._clock()
        emitted: list[AnnouncementSubject] = []
        for subject in subjects:
            if not subject.is_effective:
                continue  # accord attendu, ou refusé : rien n'entre
            result = await self._intake.submit(
                build_fact(announcement, subject, recorded_at=recorded_at)
            )
            if result.accepted:
                emitted.append(subject)
        return emitted
