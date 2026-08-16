"""Poser sa langue — **et pouvoir revenir en arrière**, contre une vraie base.

Le chantier bilingue avait posé `accounts.language` (L-0) sans porte pour l'écrire : tout le
monde héritait de son église, et le membre anglophone d'une assemblée francophone — le cas qui a
lancé tout ceci — restait mal servi. Ce fichier garde la porte.

Ce qu'il vérifie surtout, c'est la chose la plus facile à casser : **`null` est une réponse**.
« Je suis la langue de mon église » est un choix qu'on doit pouvoir reprendre après avoir mis
l'anglais, et un réglage qui ne se défait pas n'est pas un réglage.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app._shared.domain.locale import Locale
from app.contexts.iam.application.language import SetMyLanguage
from app.contexts.iam.application.queries.get_my_profile import GetMyProfile
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.infrastructure.persistence.locale_resolver import (
    SqlLanguageStore,
    SqlLocaleResolver,
)
from app.contexts.iam.infrastructure.persistence.models import AccountModel, MembershipModel
from app.contexts.iam.infrastructure.persistence.profile_reader import SqlProfileReader
from app.contexts.tenant.infrastructure.persistence.models import TenantModel
from app.core.database import Base

_NOW = datetime(2026, 8, 16, tzinfo=UTC)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as opened:
        yield opened
    await engine.dispose()


def _account(*, language=None):
    return AccountModel(
        id=uuid4(), phone_number=f"+225{uuid4().int % 10**8:08d}", first_name="Kouassi",
        last_name="N'Guessan", language=language, birthday_scope="groups",
        is_phone_verified=True, is_email_verified=False, created_at=_NOW,
        created_by_type="self", status="active",
    )


def _church(*, language="fr"):
    return TenantModel(id=uuid4(), name="Bethel", language=language, created_at=_NOW)


def _belongs(account, church):
    return MembershipModel(
        id=uuid4(), account_id=account.id, tenant_id=church.id,
        status=MembershipStatus.CONFIRMED_MEMBER.value, last_transition_at=_NOW,
        created_at=_NOW, created_by_account_id=account.id, closed_at=None,
    )


def _command(session):
    return SetMyLanguage(SqlLanguageStore(session), SqlLocaleResolver(session))


class _AucuneAppartenance:
    async def execute(self, *, account_id):
        return []


async def test_poser_sa_langue_la_rend_effective(session):
    church = _church(language="fr")
    me = _account()
    session.add_all([church, me, _belongs(me, church)])
    await session.flush()

    result = await _command(session).execute(actor_account_id=me.id, language=Locale.EN)

    assert result.chosen is Locale.EN and result.resolved is Locale.EN


async def test_revenir_a_null_rend_la_parole_a_leglise(session):
    """Le test qui compte : « je suis la langue de mon église » doit se **reprendre**.

    Un `COALESCE` bien intentionné, ou une écriture sautée quand la valeur est nulle, rendrait
    le premier choix définitif — et personne ne s'en apercevrait avant qu'un membre demande
    pourquoi il ne peut plus revenir en français."""
    church = _church(language="fr")
    me = _account()
    session.add_all([church, me, _belongs(me, church)])
    await session.flush()
    command = _command(session)
    await command.execute(actor_account_id=me.id, language=Locale.EN)

    result = await command.execute(actor_account_id=me.id, language=None)

    assert result.chosen is None  # le réglage est bien effacé
    assert result.resolved is Locale.FR  # et l'église a repris la parole


async def test_le_reglage_suit_leglise_apres_coup(session):
    """`None` ne veut pas dire « français au moment où j'ai répondu » : le membre qui suit son
    église suit aussi ses changements."""
    church = _church(language="fr")
    me = _account()
    session.add_all([church, me, _belongs(me, church)])
    await session.flush()
    await _command(session).execute(actor_account_id=me.id, language=None)

    church.language = "en"  # l'église bascule
    await session.flush()

    assert await SqlLocaleResolver(session).resolve(me.id) is Locale.EN


async def test_poser_sa_langue_ne_touche_pas_celle_de_leglise(session):
    """Parler pour soi n'est pas parler pour l'assemblée : changer la langue de l'église est un
    acte de gouvernance, sur une autre surface."""
    church = _church(language="fr")
    me = _account()
    session.add_all([church, me, _belongs(me, church)])
    await session.flush()

    await _command(session).execute(actor_account_id=me.id, language=Locale.EN)

    assert await SqlLocaleResolver(session).resolve_tenant(church.id) is Locale.FR


async def test_poser_sa_langue_ne_touche_que_son_compte(session):
    church = _church(language="fr")
    me, other = _account(), _account()
    session.add_all([church, me, other, _belongs(me, church), _belongs(other, church)])
    await session.flush()

    await _command(session).execute(actor_account_id=me.id, language=Locale.EN)

    assert await SqlLocaleResolver(session).resolve(other.id) is Locale.FR


async def test_le_profil_rend_les_deux_moities(session):
    """Sans le réglage, l'écran ne sait pas quelle case cocher ; sans la langue effective,
    « je n'ai rien choisi » se confond avec « on m'a mis en français »."""
    church = _church(language="en")
    me = _account()  # aucun choix posé
    session.add_all([church, me, _belongs(me, church)])
    await session.flush()

    dto = await GetMyProfile(
        SqlProfileReader(session), _AucuneAppartenance(), SqlLocaleResolver(session)
    ).execute(account_id=me.id)

    assert dto.language is None  # je n'ai rien choisi
    assert dto.resolved_language is Locale.EN  # mais on me parle anglais, et je sais pourquoi
