"""Le **compagnon** (S-3) — la conversation privée qui déroule l'arbre gelé du digest.

Trois gestes, tous déterministes (zéro appel IA) :
- `StartCompanion` — ouvre (ou **reprend**) la session d'un membre sur un sermon **publié** ; rend
  la **question d'entrée** (« as-tu vécu le culte ? »).
- `AnswerAttendance` — oui → branche **consolidation** (Q&R), non → branche **enseignement** (les
  points essentiels). Le « non » n'est jamais un reproche : c'est le rattrapage, la main tendue.
- `AdvanceCompanion` — pas suivant ; à la fin, un mot de clôture.

La session est **privée** (seul son membre y accède). Le contenu vient du **digest** du sermon ;
l'agrégat ne porte que l'état — on les combine ici.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.iam.domain.repositories import MembershipRepository
from app.contexts.sermon.application.dtos import CompanionCardDTO
from app.contexts.sermon.application.ports import CulteAttendancePort
from app.contexts.sermon.domain.aggregates import Sermon
from app.contexts.sermon.domain.companion import CompanionSession
from app.contexts.sermon.domain.digest import SermonDigest
from app.contexts.sermon.domain.errors import (
    CompanionSessionNotFoundError,
    NotAChurchMemberError,
    NotSessionOwnerError,
    SermonNotFoundError,
    SermonNotPublishedError,
)
from app.contexts.sermon.domain.repositories import (
    CompanionSessionRepository,
    SermonRepository,
)

_ATTENDANCE_PROMPT = "As-tu vécu le culte aujourd'hui ?"


def _branch(session: CompanionSession, digest: SermonDigest | None) -> list:
    """La branche courante : consolidation (questions) si présent, sinon enseignement (points)."""
    if digest is None or session.attended is None:
        return []
    return list(digest.questions) if session.attended else list(digest.key_points)


def _closing_prompt(attended: bool | None) -> str:
    if attended:
        return "Que cette Parole demeure en toi cette semaine."
    return "Merci d'avoir pris ce temps. La porte reste ouverte — reviens quand tu veux."


def _card(session: CompanionSession, digest: SermonDigest | None) -> CompanionCardDTO:
    if session.attended is None:
        return CompanionCardDTO(
            session_id=session.id, stage="attendance", prompt=_ATTENDANCE_PROMPT,
            guidance=None, index=0, total=0, done=False,
        )
    branch = _branch(session, digest)
    total = len(branch)
    if session.is_completed or session.step >= total:
        return CompanionCardDTO(
            session_id=session.id, stage="closing", prompt=_closing_prompt(session.attended),
            guidance=None, index=total, total=total, done=True,
        )
    item = branch[session.step]
    if session.attended:  # CompanionQuestion (prompt + guidance)
        return CompanionCardDTO(
            session_id=session.id, stage="consolidation", prompt=item.prompt,
            guidance=item.guidance, index=session.step, total=total, done=False,
        )
    return CompanionCardDTO(  # point essentiel (texte)
        session_id=session.id, stage="teaching", prompt=str(item),
        guidance=None, index=session.step, total=total, done=False,
    )


async def _load_sermon(sermons: SermonRepository, sermon_id: UUID) -> Sermon:
    sermon = await sermons.get(sermon_id)
    if sermon is None:
        raise SermonNotFoundError("Sermon introuvable.", details={"sermon_id": str(sermon_id)})
    return sermon


async def _load_own_session(
    sessions: CompanionSessionRepository, *, session_id: UUID, member_account_id: UUID
) -> CompanionSession:
    session = await sessions.get(session_id)
    if session is None:
        raise CompanionSessionNotFoundError(
            "Session introuvable.", details={"session_id": str(session_id)}
        )
    if session.member_account_id != member_account_id:
        raise NotSessionOwnerError("Cette conversation est privée.")
    return session


class StartCompanion:
    def __init__(
        self,
        sessions: CompanionSessionRepository,
        sermons: SermonRepository,
        memberships: MembershipRepository,
        *,
        clock,
    ) -> None:
        self._sessions = sessions
        self._sermons = sermons
        self._memberships = memberships
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, sermon_id: UUID
    ) -> CompanionCardDTO:
        sermon = await _load_sermon(self._sermons, sermon_id)
        if not sermon.is_published:
            raise SermonNotPublishedError(
                "Ce sermon n'est pas encore publié.", details={"sermon_id": str(sermon_id)}
            )
        if await self._memberships.get_active(actor_account_id, sermon.tenant_id) is None:
            raise NotAChurchMemberError(
                "Rejoins d'abord cette église pour vivre le compagnon.",
                details={"tenant_id": str(sermon.tenant_id)},
            )
        session = await self._sessions.find_active(actor_account_id, sermon_id)
        if session is None:
            session = CompanionSession.start(
                id=uuid4(), sermon_id=sermon_id, tenant_id=sermon.tenant_id,
                member_account_id=actor_account_id, now=self._clock(),
            )
            await self._sessions.add(session)
        return _card(session, sermon.digest)  # reprend là où on en était


class AnswerAttendance:
    def __init__(
        self,
        sessions: CompanionSessionRepository,
        sermons: SermonRepository,
        culte: CulteAttendancePort | None = None,
        *,
        clock,
    ) -> None:
        self._sessions = sessions
        self._sermons = sermons
        self._culte = culte
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, session_id: UUID, attended: bool
    ) -> CompanionCardDTO:
        session = await _load_own_session(
            self._sessions, session_id=session_id, member_account_id=actor_account_id
        )
        sermon = await _load_sermon(self._sermons, session.sermon_id)
        session.answer_attendance(attended, now=self._clock())
        if not _branch(session, sermon.digest):  # rien à dérouler → clôture directe
            session.complete(now=self._clock())
        await self._sessions.save(session)
        # « oui » → présence DÉCLARÉE au culte du jour (axe physique, additive). Jamais un « non ».
        if attended and self._culte is not None:
            await self._culte.mark_declared_present(
                tenant_id=session.tenant_id,
                member_account_id=session.member_account_id,
                on_date=sermon.preached_on,
                now=self._clock(),
            )
        return _card(session, sermon.digest)


class AdvanceCompanion:
    def __init__(
        self,
        sessions: CompanionSessionRepository,
        sermons: SermonRepository,
        *,
        clock,
    ) -> None:
        self._sessions = sessions
        self._sermons = sermons
        self._clock = clock

    async def execute(
        self, *, actor_account_id: UUID, session_id: UUID
    ) -> CompanionCardDTO:
        session = await _load_own_session(
            self._sessions, session_id=session_id, member_account_id=actor_account_id
        )
        sermon = await _load_sermon(self._sermons, session.sermon_id)
        total = len(_branch(session, sermon.digest))
        if session.step + 1 >= total:
            session.complete(now=self._clock())  # dernier pas → clôture
        else:
            session.advance(now=self._clock())
        await self._sessions.save(session)
        return _card(session, sermon.digest)
