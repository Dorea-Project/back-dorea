"""La veille rend des nombres, jamais des gens — prouvé, pas promis (S14).

Une note de confidentialité dans une docstring ne tient pas six mois. Ces tests vérifient la
propriété **par construction** :

1. le type de sortie **n'a aucun champ capable de porter une identité** ;
2. le SQL compilé ne **mentionne** ni `subject_id` ni `owner_account_id` ;
3. le seuil de cinq est appliqué **dans la requête**, pas après ;
4. et la valeur du seuil est la même des deux côtés de la frontière.

Les trois premiers survivent à quelqu'un qui n'aura pas lu ces pages. C'est le but.
"""

import typing
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.watch.application.aggregates import (
    CONFIDENTIALITY_THRESHOLD,
    TopicCount,
)
from app.contexts.watch.infrastructure.persistence.aggregate_reader import SqlAggregateReader
from app.contexts.watch.infrastructure.persistence.models import SignalModel
from app.core.database import Base

_NOW = datetime(2026, 8, 4, tzinfo=UTC)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


def _signal(tenant_id: UUID, origin: str, *, days_ago: int = 1) -> SignalModel:
    return SignalModel(
        id=uuid4(),
        tenant_id=tenant_id,
        subject_id=uuid4(),  # nominatif en base — c'est bien la question
        origin=origin,
        status="open",
        reason="—",
        opened_at=_NOW - timedelta(days=days_ago),
        owner_account_id=uuid4(),
        priority=origin,
        episode_id=uuid4(),
    )


def _reader(session) -> SqlAggregateReader:
    return SqlAggregateReader(session, clock=lambda: _NOW)


# ------------------------------------------------------- la garde structurelle


def test_le_type_de_sortie_ne_peut_pas_porter_une_identite():
    """Aucun champ UUID — une implémentation pressée n'a **nulle part** où glisser un nom."""
    for field in fields(TopicCount):
        annotation = typing.get_type_hints(TopicCount)[field.name]
        assert annotation is not UUID, f"{field.name} peut porter une identité"
        assert "UUID" not in str(annotation), f"{field.name} peut porter une identité"


def test_la_requete_ne_lit_jamais_les_colonnes_nominatives(session):
    """Le SQL compilé ne mentionne pas `subject_id` : il n'est pas filtré, il n'est pas lu."""
    sql = str(_reader(session)._statement(uuid4(), _NOW).compile())
    assert "subject_id" not in sql
    assert "owner_account_id" not in sql
    assert "GROUP BY" in sql.upper() and "HAVING" in sql.upper()


# ------------------------------------------------------- le seuil, en base


async def test_un_groupe_sous_le_seuil_ne_quitte_pas_la_base(session):
    tenant = uuid4()
    for _ in range(CONFIDENTIALITY_THRESHOLD - 1):  # quatre : sous le seuil
        session.add(_signal(tenant, "absence"))
    await session.flush()

    assert await _reader(session).counts_by_origin(tenant, window_days=30) == ()


async def test_au_seuil_le_groupe_sort(session):
    tenant = uuid4()
    for _ in range(CONFIDENTIALITY_THRESHOLD):  # cinq, tout juste
        session.add(_signal(tenant, "absence"))
    await session.flush()

    counts = await _reader(session).counts_by_origin(tenant, window_days=30)
    assert len(counts) == 1
    assert counts[0].topic == "absence"
    assert counts[0].headcount == CONFIDENTIALITY_THRESHOLD


async def test_chaque_origine_est_jugee_separement(session):
    """Un groupe au-dessus ne fait pas passer un groupe en dessous."""
    tenant = uuid4()
    for _ in range(6):
        session.add(_signal(tenant, "declared"))
    for _ in range(2):
        session.add(_signal(tenant, "concern"))
    await session.flush()

    counts = await _reader(session).counts_by_origin(tenant, window_days=30)
    assert {c.topic for c in counts} == {"declared"}  # `concern` reste invisible


async def test_la_fenetre_borne_la_lecture(session):
    tenant = uuid4()
    for _ in range(6):
        session.add(_signal(tenant, "absence", days_ago=90))  # hors fenêtre
    await session.flush()

    assert await _reader(session).counts_by_origin(tenant, window_days=30) == ()


async def test_une_autre_eglise_n_est_jamais_agregee_avec_la_notre(session):
    mine, other = uuid4(), uuid4()
    for _ in range(6):
        session.add(_signal(other, "absence"))
    await session.flush()

    assert await _reader(session).counts_by_origin(mine, window_days=30) == ()


# ------------------------------------------------------- la frontière avec urim


def test_le_seuil_est_le_meme_des_deux_cotes_de_la_frontiere():
    """Les contextes ne partagent rien — donc la constante est écrite deux fois. Elles doivent
    rester égales, et c'est ce test qui le tient (les tests, eux, ont le droit de traverser)."""
    from app.contexts.urim.calendar.domain.models import (
        CONFIDENTIALITY_THRESHOLD as URIM_THRESHOLD,
    )

    assert URIM_THRESHOLD == CONFIDENTIALITY_THRESHOLD
