"""Le culte que le compagnon ouvre — **contre une vraie base**, parce que c'est là qu'était le mal.

C'était la seule voix de Dorea qui ne se rendait pas à l'envoi mais s'**écrivait en base** :
`title = 'Culte'`, gravé au moment de la création de la rencontre. Une église anglophone lisait
donc « Culte » dans son historique de présence, et aucun rendu ne pouvait le rattraper — la ligne
existait déjà.

Ce n'était d'ailleurs pas un titre : c'était le mot français pour le type `service`. Le titre
reste ce qu'un humain nomme lui-même (« Culte de Pâques ») ; une rencontre qui n'a d'autre nom
que ce qu'elle est porte `NULL`, et le client la nomme dans la langue de son lecteur.

Le test tape la base plutôt que la commande : un fake aurait accepté n'importe quel titre.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.attendance.domain.enums import GatheringType
from app.contexts.attendance.infrastructure.persistence.models import GatheringModel
from app.contexts.sermon.infrastructure.culte_attendance import SermonCulteAttendanceAdapter
from app.core.database import Base

_NOW = datetime(2026, 8, 16, 11, 0, tzinfo=UTC)
_SUNDAY = date(2026, 8, 16)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


async def _culte(session, tenant):
    return (
        await session.execute(select(GatheringModel).where(GatheringModel.tenant_id == tenant))
    ).scalars().all()


async def test_le_culte_nest_pas_intitule_en_francais(session):
    """Aucun mot d'aucune langue n'entre en base : la rencontre porte son **type**."""
    tenant, member = uuid4(), uuid4()

    await SermonCulteAttendanceAdapter(session).mark_declared_present(
        tenant_id=tenant, member_account_id=member, on_date=_SUNDAY, now=_NOW
    )

    (gathering,) = await _culte(session, tenant)
    assert gathering.title is None
    assert gathering.type == GatheringType.SERVICE.value  # c'est lui qui la nomme, côté client
    assert gathering.group_id is None  # église-entière


async def test_deux_declarations_ouvrent_toujours_un_seul_culte(session):
    """La garde d'origine (DOREA-009) tient toujours : le titre n'entrait pas dans la clé, et
    le retirer ne devait donc rien changer au get-or-create."""
    tenant, awa, kouassi = uuid4(), uuid4(), uuid4()
    adapter = SermonCulteAttendanceAdapter(session)

    await adapter.mark_declared_present(
        tenant_id=tenant, member_account_id=awa, on_date=_SUNDAY, now=_NOW
    )
    await adapter.mark_declared_present(
        tenant_id=tenant, member_account_id=kouassi, on_date=_SUNDAY, now=_NOW
    )

    assert len(await _culte(session, tenant)) == 1
