"""Agrégat `Sermon` — le sermon déposé par le pasteur, qui va vivre au-delà du dimanche.

Le socle (S-0) : le **dépôt** d'un sermon en **texte** et son **cycle de vie**
`brouillon → approuvé → publié`. Le digest IA (résumé, capsules, questions/réponses) est produit
en **un seul appel** au dépôt (S-1), relu par le pasteur à l'approbation, puis **gelé** — le
compagnon au runtime ne fait que dérouler cet arbre approuvé. Ici, on plante le cycle et les graines
(format extensible, date du culte pour la présence déclarée).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.sermon.domain.digest import SermonDigest
from app.contexts.sermon.domain.enums import SermonSourceKind, SermonStatus
from app.contexts.sermon.domain.errors import (
    SermonContentRequiredError,
    SermonNotEditableError,
    SermonTitleRequiredError,
)


class Sermon(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        author_account_id: UUID,
        title: str,
        reference: str | None,
        source_kind: SermonSourceKind,
        raw_text: str,
        preached_on: date,
        status: SermonStatus,
        created_at: datetime,
        updated_at: datetime,
        approved_at: datetime | None,
        digest: SermonDigest | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.author_account_id = author_account_id  # le pasteur qui a prêché
        self.title = title
        self.reference = reference  # passage biblique principal (ex. « Jean 3.16 »)
        self.source_kind = source_kind
        self.raw_text = raw_text  # le texte extrait — la matière du digest IA (S-1)
        self.preached_on = preached_on  # le culte concerné (sert la présence déclarée, S-4)
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.approved_at = approved_at
        self.digest = digest  # le produit IA (résumé/capsules/Q&R) — pré-généré au dépôt (S-1)

    @classmethod
    def deposit(
        cls,
        *,
        id: UUID,
        tenant_id: UUID,
        author_account_id: UUID,
        title: str,
        raw_text: str,
        preached_on: date,
        now: datetime,
        reference: str | None = None,
        source_kind: SermonSourceKind = SermonSourceKind.TEXT,
    ) -> Sermon:
        title = title.strip()
        if not title:
            raise SermonTitleRequiredError("Le sermon doit porter un titre.")
        text = raw_text.strip()
        if not text:
            raise SermonContentRequiredError("Le sermon doit porter un texte à digérer.")
        ref = reference.strip() if reference else None
        return cls(
            id=id,
            tenant_id=tenant_id,
            author_account_id=author_account_id,
            title=title,
            reference=ref or None,
            source_kind=source_kind,
            raw_text=text,
            preached_on=preached_on,
            status=SermonStatus.DRAFT,
            created_at=now,
            updated_at=now,
            approved_at=None,
        )

    @property
    def is_published(self) -> bool:
        return self.status is SermonStatus.PUBLISHED

    def attach_digest(self, digest: SermonDigest) -> None:
        """Attache le digest IA (au dépôt). Il sera relu à l'approbation, puis gelé."""
        self.digest = digest

    def approve(self, *, now: datetime) -> None:
        """Le pasteur valide (et, dès S-1, relit le digest). Le contenu devient prêt à publier."""
        if self.status is not SermonStatus.DRAFT:
            raise SermonNotEditableError("Seul un brouillon peut être approuvé.")
        self.status = SermonStatus.APPROVED
        self.approved_at = now
        self.updated_at = now

    def publish(self, *, now: datetime) -> None:
        """Publie — rien de non approuvé n'atteint jamais le membre."""
        if self.status is not SermonStatus.APPROVED:
            raise SermonNotEditableError("Un sermon doit être approuvé avant d'être publié.")
        self.status = SermonStatus.PUBLISHED
        self.updated_at = now
