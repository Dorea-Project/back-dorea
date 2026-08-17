"""Use case **du pasteur** — déposer un sermon (texte, ou fichier PDF/PPTX → texte).

Déposer un sermon est le seul acte d'écriture propre au pasteur, à côté de son agenda : autorité
**église-entière** `PUBLISH_SERMON` (pasteur / admin / owner). Le sermon naît **brouillon** ; le
digest IA et la publication viendront ensuite (S-1, S-2) — rien n'atteint le membre sans onction.

Un fichier (PDF/PPTX) est d'abord **normalisé en texte** par le `SermonTextExtractor` (S-5) ; le
chemin est ensuite identique au dépôt texte (l'IA ne voit que du texte).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from app._shared.domain.locale import DEFAULT_LOCALE
from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.application.ports import LocaleResolver
from app.contexts.iam.domain.permissions import Permission
from app.contexts.sermon.application.dtos import SermonDTO
from app.contexts.sermon.application.mapping import to_sermon_dto
from app.contexts.sermon.application.ports import SermonDigester, SermonTextExtractor
from app.contexts.sermon.application.upload_guard import ensure_declared_kind
from app.contexts.sermon.domain.aggregates import Sermon
from app.contexts.sermon.domain.enums import SermonSourceKind
from app.contexts.sermon.domain.errors import UnsupportedSermonFormatError
from app.contexts.sermon.domain.repositories import SermonRepository


class DepositSermon:
    def __init__(
        self,
        sermons: SermonRepository,
        access: GroupAccessPolicy,
        digester: SermonDigester | None = None,
        extractor: SermonTextExtractor | None = None,
        locales: LocaleResolver | None = None,
        *,
        clock,
    ) -> None:
        self._sermons = sermons
        self._access = access
        self._digester = digester
        self._extractor = extractor
        self._locales = locales
        self._clock = clock

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        title: str,
        content: str,
        preached_on: date,
        reference: str | None = None,
    ) -> SermonDTO:
        """Dépôt **texte** (S-0)."""
        await self._ensure_publisher(actor_account_id, tenant_id)
        return await self._deposit(
            actor_account_id=actor_account_id, tenant_id=tenant_id, title=title,
            text=content, source_kind=SermonSourceKind.TEXT, preached_on=preached_on,
            reference=reference,
        )

    async def execute_file(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        title: str,
        data: bytes,
        kind: SermonSourceKind,
        preached_on: date,
        reference: str | None = None,
    ) -> SermonDTO:
        """Dépôt **fichier** (S-5 : PDF/PPTX) — extrait le texte, puis même chemin que le texte."""
        await self._ensure_publisher(actor_account_id, tenant_id)
        if self._extractor is None:
            raise UnsupportedSermonFormatError("L'extraction de fichiers n'est pas configurée.")
        # DOREA-024 — le `kind` est **déclaré** par le client ; on recoupe les octets avant de
        # les confier au parseur. Ici et pas dans l'adaptateur : le contrôle doit tenir pour
        # tout extracteur branché derrière le port, y compris celui qui se facturera (S-6).
        ensure_declared_kind(data, kind)
        text = await self._extractor.extract(data, kind=kind)
        return await self._deposit(
            actor_account_id=actor_account_id, tenant_id=tenant_id, title=title,
            text=text, source_kind=kind, preached_on=preached_on, reference=reference,
        )

    async def _ensure_publisher(self, actor_account_id: UUID, tenant_id: UUID) -> None:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.PUBLISH_SERMON,
        )

    async def _deposit(
        self,
        *,
        actor_account_id: UUID,
        tenant_id: UUID,
        title: str,
        text: str,
        source_kind: SermonSourceKind,
        preached_on: date,
        reference: str | None,
    ) -> SermonDTO:
        sermon = Sermon.deposit(
            id=uuid4(),
            tenant_id=tenant_id,
            author_account_id=actor_account_id,
            title=title,
            raw_text=text,
            preached_on=preached_on,
            now=self._clock(),
            reference=reference,
            source_kind=source_kind,
        )
        # Digestion IA en un appel (résumé/capsules/Q&R) — le pasteur la relira à l'approbation.
        if self._digester is not None:
            # La langue de l'**église**, pas celle du pasteur : ce brouillon sera lu par toute
            # l'assemblée. Un pasteur qui a mis son compte en anglais ne fait pas basculer en
            # anglais le résumé d'un culte prêché en français.
            locale = (
                await self._locales.resolve_tenant(tenant_id)
                if self._locales is not None
                else DEFAULT_LOCALE
            )
            digest = await self._digester.digest(
                sermon.raw_text, title=sermon.title, reference=sermon.reference, locale=locale
            )
            sermon.attach_digest(digest)
        await self._sermons.add(sermon)
        return to_sermon_dto(sermon)
