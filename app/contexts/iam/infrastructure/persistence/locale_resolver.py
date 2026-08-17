"""La chaîne *personne → église → `fr`*, en **une** requête.

Une jointure externe plutôt que deux passes : le fan-out d'une annonce à toute une église
demande la langue de plusieurs centaines de comptes d'un coup, et une requête par destinataire
tuerait la publication. `resolve_many` est donc la méthode portante, et `resolve` (un seul
compte) passe par elle.

Ce fichier est **le seul** endroit du dépôt qui touche `accounts.language` et `tenants.language`
— en lecture comme en écriture. C'est ce qui rend la règle vérifiable : le jour où l'on ajoute un
étage (la langue d'un appareil, celle d'un en-tête HTTP), il y a un fichier à changer, pas dix.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app._shared.domain.locale import DEFAULT_LOCALE, Locale, parse_locale
from app.contexts.iam.application.language import LanguageStore
from app.contexts.iam.application.ports import LocaleResolver
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.infrastructure.persistence.models import AccountModel, MembershipModel
from app.contexts.tenant.infrastructure.persistence.models import TenantModel


class SqlLocaleResolver(LocaleResolver):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_many(self, account_ids: Sequence[UUID]) -> dict[UUID, Locale]:
        # Dédoublonne en gardant l'ordre : le même compte peut être visé deux fois par un
        # fan-out (ciblé *et* diffusé), et `IN` n'a pas à porter le doublon.
        wanted = list(dict.fromkeys(account_ids))
        if not wanted:
            return {}

        rows = (
            await self._session.execute(
                select(
                    AccountModel.id,
                    AccountModel.language,
                    MembershipModel.last_transition_at,
                    TenantModel.language.label("church_language"),
                )
                .select_from(AccountModel)
                # Externe des deux côtés : un compte sans église (un chercheur de Mission, un
                # compte tout juste créé) doit **quand même** ressortir de la requête. Une
                # jointure interne le ferait disparaître, et l'appelant aurait un trou dans
                # son dictionnaire là où il attend une langue.
                .outerjoin(
                    MembershipModel,
                    (MembershipModel.account_id == AccountModel.id)
                    & (MembershipModel.closed_at.is_(None))
                    & (MembershipModel.status != MembershipStatus.CLOSED.value),
                )
                .outerjoin(TenantModel, TenantModel.id == MembershipModel.tenant_id)
                .where(AccountModel.id.in_(wanted))
            )
        ).all()

        # Une personne peut appartenir à plusieurs églises (une annexe est un tenant à part
        # entière, avec sa propre colonne `language`). On retient la **dernière appartenance
        # entrée en vigueur** : c'est l'église où elle se tient aujourd'hui.
        person: dict[UUID, Locale] = {}
        church: dict[UUID, _Church] = {}
        for row in rows:
            spoken = parse_locale(row.language)
            if spoken is not None:
                person[row.id] = spoken  # le choix de la personne gagne, l'église est ignorée
                continue
            if row.church_language is None:
                continue
            here = _Church(entered_at=row.last_transition_at, language=row.church_language)
            if here.supersedes(church.get(row.id)):
                church[row.id] = here

        resolved: dict[UUID, Locale] = {}
        for account_id in wanted:
            chosen = person.get(account_id)
            if chosen is None:
                latest = church.get(account_id)
                # Si l'église déclare une langue que Dorea ne parle pas, on ne remonte **pas**
                # à l'appartenance précédente : c'est bien cette église-là qui est la sienne.
                # Tomber au défaut reste vrai ; parler la langue d'une église qu'elle a quittée
                # serait faux.
                chosen = parse_locale(latest.language) if latest else None
            resolved[account_id] = chosen or DEFAULT_LOCALE
        return resolved


    async def resolve_tenant(self, tenant_id: UUID) -> Locale:
        declared = (
            await self._session.execute(
                select(TenantModel.language).where(TenantModel.id == tenant_id)
            )
        ).scalar_one_or_none()
        return parse_locale(declared) or DEFAULT_LOCALE


class SqlLanguageStore(LanguageStore):
    """Une colonne sur le compte. Pas de table, pas d'historique : la langue de quelqu'un est un
    réglage courant, pas un fait à conserver."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_language(self, *, account_id: UUID, language: Locale | None) -> None:
        # `None` s'écrit vraiment — c'est la réponse *« celle de mon église »*, pas un champ
        # laissé de côté. Un `COALESCE` ou un saut de l'écriture rendrait le retour impossible.
        await self._session.execute(
            update(AccountModel)
            .where(AccountModel.id == account_id)
            .values(language=language.value if language is not None else None)
        )


@dataclass(frozen=True, slots=True)
class _Church:
    """L'église d'où vient le repli, et la date qui départage quand il y en a plusieurs."""

    entered_at: datetime | None
    language: str

    def supersedes(self, incumbent: _Church | None) -> bool:
        """Une date bat l'absence de date ; `NULL` ne détrône jamais une date — mais le premier
        `NULL` s'installe, sinon un compte dont toutes les appartenances sont sans date
        n'aurait aucune église du tout."""
        if incumbent is None:
            return True
        if self.entered_at is None:
            return False
        return incumbent.entered_at is None or self.entered_at > incumbent.entered_at
