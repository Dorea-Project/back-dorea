"""Agrégat `CompanionSession` — la conversation **privée** d'un membre avec un sermon (S-3).

Le compagnon déroule l'**arbre gelé** du digest, de façon **déterministe** (zéro appel IA) :
1. « As-tu vécu le culte aujourd'hui ? » (oui / non) ;
2. **oui** → le Q&R de **consolidation** ; **non** → les **points essentiels** (le rattrapage).

L'agrégat ne porte que l'**état** (a-t-il répondu ? où en est-il ?) — le *contenu* vient du digest
du sermon, combiné au runtime par la couche application. Le « non » n'est jamais un reproche.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.sermon.domain.enums import CompanionStatus
from app.contexts.sermon.domain.errors import CompanionClosedError


class CompanionSession(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        sermon_id: UUID,
        tenant_id: UUID,
        member_account_id: UUID,
        attended: bool | None,
        step: int,
        status: CompanionStatus,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.sermon_id = sermon_id
        self.tenant_id = tenant_id
        self.member_account_id = member_account_id
        self.attended = attended  # None tant que la question d'entrée n'a pas reçu de réponse
        self.step = step  # index dans la branche (consolidation ou enseignement)
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def start(
        cls,
        *,
        id: UUID,
        sermon_id: UUID,
        tenant_id: UUID,
        member_account_id: UUID,
        now: datetime,
    ) -> CompanionSession:
        return cls(
            id=id,
            sermon_id=sermon_id,
            tenant_id=tenant_id,
            member_account_id=member_account_id,
            attended=None,
            step=0,
            status=CompanionStatus.IN_PROGRESS,
            created_at=now,
            updated_at=now,
        )

    @property
    def is_completed(self) -> bool:
        return self.status is CompanionStatus.COMPLETED

    def answer_attendance(self, attended: bool, *, now: datetime) -> None:
        if self.status is not CompanionStatus.IN_PROGRESS or self.attended is not None:
            raise CompanionClosedError("La question d'entrée a déjà reçu une réponse.")
        self.attended = attended
        self.step = 0
        self.updated_at = now

    def advance(self, *, now: datetime) -> None:
        if self.status is not CompanionStatus.IN_PROGRESS or self.attended is None:
            raise CompanionClosedError("Réponds d'abord à la question d'entrée.")
        self.step += 1
        self.updated_at = now

    def complete(self, *, now: datetime) -> None:
        self.status = CompanionStatus.COMPLETED
        self.updated_at = now
