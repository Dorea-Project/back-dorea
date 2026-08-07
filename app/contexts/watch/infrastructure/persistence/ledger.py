"""Implémentation SQLAlchemy du ledger. Append-only : ni `save`, ni `delete`, par construction."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.watch.application.intake import FactLedger
from app.contexts.watch.application.interpreters.self_declaration import DeclarationKind
from app.contexts.watch.application.ports import (
    DeclaredLink,
    DeclaredLinkReader,
    GestureReader,
    GestureSeen,
    GestureTowards,
)
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.infrastructure.persistence.models import FactLedgerModel


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _to_consent(raw: dict | None) -> ConsentProof | None:
    if not raw:
        return None
    return ConsentProof(
        given_by=UUID(raw["given_by"]),
        scope=ConsentScope(raw["scope"]),
        given_at=_aware(_parse(raw["given_at"])),
        revocable=bool(raw.get("revocable", True)),
    )


def _parse(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)


def _signer(raw: dict | None) -> UUID | None:
    """Qui a signé ce fait. `None` si le type n'exige aucune preuve — on ne devine pas d'auteur."""
    if not raw or not raw.get("given_by"):
        return None
    return UUID(raw["given_by"])


def _to_fact(row: FactLedgerModel) -> Fact:
    return Fact(
        fact_id=row.fact_id,
        tenant_id=row.tenant_id,
        occurred_at=_aware(row.occurred_at),
        recorded_at=_aware(row.recorded_at),
        source=row.source,
        kind=FactKind(row.kind),
        subject_kind=SubjectKind(row.subject_kind),
        subject_id=row.subject_id,
        payload=dict(row.payload or {}),
        payload_version=row.payload_version,
        consent=_to_consent(row.consent),
        seq=row.seq,
    )


class SqlGestureReader(GestureReader):
    """Relit les gestes au journal. **Aucune écriture**, et volontairement à part du ledger.

    `FactLedger` porte le contrat d'écriture append-only ; y greffer des requêtes de lecture
    métier en ferait, à la longue, le dépôt fourre-tout du contexte. Une classe distincte sur la
    même table dit ce qu'elle est : une vue."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def gestures_by(
        self, *, actor_account_id, tenant_id, before, limit: int = 5
    ) -> list[GestureTowards]:
        """Le filtre porte sur le **signataire**, pas sur le sujet — d'où le passage par la preuve
        de consentement. Il n'existe pas d'index dessus ; la fenêtre `before` et la limite le
        rendent borné, et cette lecture ne tourne que sur demande d'une personne pour elle-même."""
        stmt = (
            select(
                FactLedgerModel.subject_id,
                FactLedgerModel.payload,
                FactLedgerModel.occurred_at,
                FactLedgerModel.consent,
            )
            .where(
                FactLedgerModel.tenant_id == tenant_id,
                FactLedgerModel.kind == FactKind.GESTURE_DONE.value,
                FactLedgerModel.occurred_at <= before,
            )
            .order_by(FactLedgerModel.occurred_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return fold_my_gestures(
            (
                (subject_id, dict(payload or {}), _aware(at), _signer(consent))
                for subject_id, payload, at, consent in rows
            ),
            actor_account_id=actor_account_id,
            limit=limit,
        )

    async def gestures_between(
        self, *, subject_id, tenant_id, since, until, limit: int = 3
    ) -> list[GestureSeen]:
        stmt = (
            select(
                FactLedgerModel.payload,
                FactLedgerModel.occurred_at,
                FactLedgerModel.consent,
            )
            .where(
                FactLedgerModel.tenant_id == tenant_id,
                FactLedgerModel.subject_id == subject_id,
                FactLedgerModel.kind == FactKind.GESTURE_DONE.value,
                FactLedgerModel.occurred_at >= since,
                FactLedgerModel.occurred_at < until,
            )
            .order_by(FactLedgerModel.occurred_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            GestureSeen(
                kind=(payload or {}).get("kind", ""),
                occurred_at=_aware(at),
                # L'auteur vit dans la **preuve de consentement**, pas dans le payload : c'est là
                # qu'il a signé, et c'est ce qui rend impossible d'émettre un geste au nom de
                # quelqu'un qui n'a rien fait.
                by_account_id=_signer(consent),
            )
            for payload, at, consent in rows
        ]


class SqlDeclaredLinkReader(DeclaredLinkReader):
    """Replie le journal en liens actifs. **Aucune table**, aucune projection à maintenir.

    Un champ « mes proches » que personne n'a intérêt à tenir à jour pourrit en trois mois — c'est
    le raisonnement qui a déjà écarté un `current_referent_id` sur la personne. Ici il n'y a rien
    à tenir : la suite des déclarations *est* l'état, et on la replie à la lecture."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def declared_links(self, *, subject_id, tenant_id) -> list[DeclaredLink]:
        stmt = (
            select(FactLedgerModel.payload, FactLedgerModel.occurred_at)
            .where(
                FactLedgerModel.tenant_id == tenant_id,
                FactLedgerModel.subject_id == subject_id,
                FactLedgerModel.kind == FactKind.SELF_DECLARATION.value,
            )
            .order_by(FactLedgerModel.seq)
        )
        rows = (await self._session.execute(stmt)).all()
        return fold_declared_links(
            (dict(payload or {}), _aware(at)) for payload, at in rows
        )


def fold_my_gestures(entries, *, actor_account_id, limit) -> list[GestureTowards]:
    """**Une personne, une fois.** Le pli, partagé avec la doublure de test.

    Si Jean est passé trois fois voir Anna, il ne doit voir qu'une proposition — et datée du
    **dernier** passage, sinon on lui rappellerait une visite qu'il a déjà répétée. Le tri
    descendant fait que la première rencontrée est la plus récente."""
    seen: dict[UUID, GestureTowards] = {}
    for subject_id, payload, at, signer in entries:
        if signer != actor_account_id or subject_id in seen:
            continue
        seen[subject_id] = GestureTowards(
            subject_id=subject_id, kind=payload.get("kind", ""), occurred_at=at
        )
    ordered = sorted(seen.values(), key=lambda g: g.occurred_at, reverse=True)
    return ordered[:limit]


def fold_declared_links(entries) -> list[DeclaredLink]:
    """Le pli, **partagé avec la doublure de test** : deux versions auraient divergé en silence.

    Dernière déclaration gagnante par personne nommée, dans l'ordre du journal. Un retrait n'efface
    rien — le journal ne se corrige pas, on ajoute un fait qui dit autre chose."""
    latest: dict[UUID, tuple[datetime, bool]] = {}
    for payload, at in entries:
        if payload.get("kind") != DeclarationKind.LINK_DECLARED.value:
            continue
        linked = payload.get("linked_account_id")
        if not linked:
            continue
        latest[UUID(str(linked))] = (at, str(payload.get("active", "true")) == "true")
    active = [
        DeclaredLink(linked_account_id=who, declared_at=when)
        for who, (when, still) in latest.items()
        if still
    ]
    active.sort(key=lambda link: link.declared_at, reverse=True)
    return active


class SqlFactLedger(FactLedger):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, fact: Fact) -> Fact:
        row = FactLedgerModel(
            fact_id=fact.fact_id,
            tenant_id=fact.tenant_id,
            occurred_at=fact.occurred_at,
            recorded_at=fact.recorded_at,
            source=fact.source,
            kind=fact.kind.value,
            subject_kind=fact.subject_kind.value,
            subject_id=fact.subject_id,
            payload=dict(fact.payload),
            payload_version=fact.payload_version,
            consent=(
                {
                    "given_by": str(fact.consent.given_by),
                    "scope": fact.consent.scope.value,
                    "given_at": fact.consent.given_at.isoformat(),
                    "revocable": fact.consent.revocable,
                }
                if fact.consent is not None
                else None
            ),
        )
        self._session.add(row)
        await self._session.flush()  # assigne `seq` — la place du fait dans l'ordre total
        return fact.sealed(row.seq)

    async def exists(self, fact_id: UUID) -> bool:
        stmt = select(FactLedgerModel.seq).where(FactLedgerModel.fact_id == fact_id).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def stream(self, tenant_id: UUID) -> AsyncIterator[Fact]:
        """Le journal d'une église, dans l'ordre où il a été écrit — **un flux**, pas une liste.

        Un curseur serveur : deux cent mille faits ne montent pas en mémoire pour être rejoués.
        L'ordre est celui de `seq`, le seul ordre total dont on dispose — les dates ne suffisent
        pas (`recorded_at` peut être à égalité, `occurred_at` peut remonter le temps), et sans
        ordre total l'invariant de déterminisme n'est pas testable.

        Le tri est donc fait par la base, une fois, au lieu d'être refait en mémoire après coup."""
        stmt = (
            select(FactLedgerModel)
            .where(FactLedgerModel.tenant_id == tenant_id)
            .order_by(FactLedgerModel.seq)
            .execution_options(yield_per=500)
        )
        result = await self._session.stream_scalars(stmt)
        async for row in result:
            yield _to_fact(row)
