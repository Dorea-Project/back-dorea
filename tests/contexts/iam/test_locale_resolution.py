"""Dans quelle langue Dorea parle à quelqu'un — contre une vraie base.

Le cas qui a lancé le chantier tient en une phrase : *il y a des églises anglophones même en
Côte d'Ivoire*. Il en cache un second, plus fin, et c'est lui qui décide de la forme du
résolveur : **un anglophone dans une église francophone**. Une langue par église seule en
ferait un mal-servi permanent ; d'où deux étages, et le `NULL` qui veut dire *« je suis la
langue de mon église »* plutôt que *« français »*.

Le reste de ce fichier vérifie surtout que la chaîne **ne s'arrête pas trop tôt** : une valeur
illisible doit laisser passer le maillon suivant, et un compte sans église doit quand même
ressortir avec une langue — le premier client est le fan-out des notifications, qui est
best-effort et ne doit jamais casser sur une langue manquante.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app._shared.domain.locale import DEFAULT_LOCALE, Locale, coerce_locale, parse_locale
from app.contexts.iam.domain.enums import MembershipStatus
from app.contexts.iam.infrastructure.persistence.locale_resolver import SqlLocaleResolver
from app.contexts.iam.infrastructure.persistence.models import AccountModel, MembershipModel
from app.contexts.tenant.infrastructure.persistence.models import TenantModel
from app.core.database import Base

_NOW = datetime(2026, 8, 16, tzinfo=UTC)
_BEFORE = datetime(2025, 1, 1, tzinfo=UTC)


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
        id=uuid4(), phone_number=f"+225{uuid4().int % 10**8:08d}", language=language,
        is_phone_verified=True, is_email_verified=False, created_at=_NOW,
        created_by_type="self", status="active",
    )


def _church(*, language="fr"):
    return TenantModel(id=uuid4(), name="Bethel", language=language, created_at=_NOW)


def _belongs(account, church, *, since=_NOW, status=MembershipStatus.CONFIRMED_MEMBER,
             closed_at=None):
    return MembershipModel(
        id=uuid4(), account_id=account.id, tenant_id=church.id, status=status.value,
        last_transition_at=since, created_at=_NOW, created_by_account_id=account.id,
        closed_at=closed_at,
    )


# --- L'objet-valeur ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("fr", Locale.FR), ("en", Locale.EN),
        ("FR", Locale.FR), ("  en  ", Locale.EN),
        # Dorea distingue les langues, pas les régions : un anglophone d'Abidjan et un
        # anglophone de Londres lisent le même « Appointment confirmed ».
        ("fr-CI", Locale.FR), ("en_GB", Locale.EN), ("EN-us", Locale.EN),
    ],
)
def test_ce_qui_designe_une_langue_que_dorea_parle(raw, expected):
    assert parse_locale(raw) is expected


@pytest.mark.parametrize("raw", [None, "", "   ", "es", "wo", "xx-YY", "-"])
def test_ce_qui_nen_designe_aucune_ne_rend_pas_le_defaut(raw):
    """`None`, pas `fr` — et c'est tout l'intérêt.

    Si une valeur illisible rendait déjà le défaut, la chaîne s'arrêterait au premier maillon
    et l'église ne serait jamais consultée."""
    assert parse_locale(raw) is None


def test_le_bout_de_chaine_rend_toujours_une_langue():
    assert coerce_locale("es") is DEFAULT_LOCALE
    assert coerce_locale(None) is DEFAULT_LOCALE
    assert coerce_locale("en") is Locale.EN


# --- La chaîne personne → église → fr ------------------------------------------------------


async def test_langlophone_dans_une_eglise_francophone(session):
    """Le cas qui justifie les deux étages : son église parle français, lui non."""
    church = _church(language="fr")
    him = _account(language="en")
    session.add_all([church, him, _belongs(him, church)])
    await session.flush()

    resolved = await SqlLocaleResolver(session).resolve_many([him.id])

    assert resolved[him.id] is Locale.EN


async def test_sans_choix_pose_on_suit_son_eglise(session):
    """`NULL` ne veut pas dire « français » : il veut dire « la langue de mon église »."""
    church = _church(language="en")
    her = _account(language=None)
    session.add_all([church, her, _belongs(her, church)])
    await session.flush()

    resolved = await SqlLocaleResolver(session).resolve_many([her.id])

    assert resolved[her.id] is Locale.EN


async def test_une_valeur_illisible_laisse_passer_leglise(session):
    """Le compte porte `es`, que Dorea ne parle pas. Il hérite de son église — il ne tombe pas
    directement au défaut, sinon le second maillon de la chaîne ne servirait jamais."""
    church = _church(language="en")
    them = _account(language="es")
    session.add_all([church, them, _belongs(them, church)])
    await session.flush()

    resolved = await SqlLocaleResolver(session).resolve_many([them.id])

    assert resolved[them.id] is Locale.EN


async def test_sans_eglise_on_tombe_au_defaut(session):
    """Un compte tout juste créé, un chercheur de Mission : personne derrière qui hériter."""
    orphan = _account()
    session.add(orphan)
    await session.flush()

    resolved = await SqlLocaleResolver(session).resolve_many([orphan.id])

    assert resolved[orphan.id] is DEFAULT_LOCALE


async def test_un_compte_inconnu_rend_le_defaut_sans_lever(session):
    """Le fan-out des notifications est best-effort. Une langue introuvable ne doit pas
    empêcher une push de partir — elle doit la faire partir en français."""
    ghost = uuid4()

    resolved = await SqlLocaleResolver(session).resolve_many([ghost])

    assert resolved == {ghost: DEFAULT_LOCALE}


async def test_leglise_quittee_ne_parle_plus_pour_lui(session):
    """Il a quitté l'église anglophone pour une francophone. L'appartenance close ne compte
    pas — sinon un transfert laisserait la langue de l'ancienne église derrière lui."""
    left, joined = _church(language="en"), _church(language="fr")
    him = _account()
    session.add_all([
        left, joined, him,
        _belongs(him, left, since=_BEFORE, status=MembershipStatus.CLOSED, closed_at=_NOW),
        _belongs(him, joined, since=_NOW),
    ])
    await session.flush()

    resolved = await SqlLocaleResolver(session).resolve_many([him.id])

    assert resolved[him.id] is Locale.FR


async def test_entre_deux_appartenances_ouvertes_la_plus_recente(session):
    """Une annexe est un tenant à part entière, avec sa propre colonne `language` : on retient
    la dernière appartenance entrée en vigueur, c'est là qu'elle se tient aujourd'hui."""
    old, recent = _church(language="fr"), _church(language="en")
    her = _account()
    session.add_all([
        old, recent, her,
        _belongs(her, old, since=_BEFORE),
        _belongs(her, recent, since=_NOW),
    ])
    await session.flush()

    resolved = await SqlLocaleResolver(session).resolve_many([her.id])

    assert resolved[her.id] is Locale.EN


async def test_une_eglise_dans_une_langue_inconnue_tombe_au_defaut(session):
    """On ne remonte pas à l'appartenance précédente : c'est bien cette église-là qui est la
    sienne. Le défaut reste vrai ; la langue d'une église quittée serait faux."""
    old, now = _church(language="en"), _church(language="es")
    them = _account()
    session.add_all([
        old, now, them,
        _belongs(them, old, since=_BEFORE),
        _belongs(them, now, since=_NOW),
    ])
    await session.flush()

    resolved = await SqlLocaleResolver(session).resolve_many([them.id])

    assert resolved[them.id] is DEFAULT_LOCALE


async def test_le_fan_out_rend_une_entree_par_identifiant_demande(session):
    """Ce que le dispatch attend : aucun trou à combler, doublons absorbés, et de quoi
    regrouper les destinataires par langue avant de rendre le texte."""
    church = _church(language="fr")
    fr_member, en_member, unknown = _account(), _account(language="en"), uuid4()
    session.add_all([
        church, fr_member, en_member,
        _belongs(fr_member, church), _belongs(en_member, church),
    ])
    await session.flush()

    resolved = await SqlLocaleResolver(session).resolve_many(
        [fr_member.id, en_member.id, unknown, fr_member.id]
    )

    assert resolved == {
        fr_member.id: Locale.FR,
        en_member.id: Locale.EN,
        unknown: DEFAULT_LOCALE,
    }


async def test_sans_destinataire_aucune_requete(session):
    assert await SqlLocaleResolver(session).resolve_many([]) == {}


async def test_le_destinataire_unique_passe_par_la_meme_chaine(session):
    church = _church(language="en")
    her = _account()
    session.add_all([church, her, _belongs(her, church)])
    await session.flush()

    assert await SqlLocaleResolver(session).resolve(her.id) is Locale.EN


# --- La langue de l'église (pour ce qui s'écrit une fois et se lit à plusieurs) -------------


async def test_la_langue_de_leglise_se_lit_directement(session):
    """`resolve_tenant` ne passe pas par une personne : un digest de sermon est écrit une fois
    et lu par toute l'assemblée, il n'a pas de « destinataire » dont hériter."""
    church = _church(language="en")
    session.add(church)
    await session.flush()

    assert await SqlLocaleResolver(session).resolve_tenant(church.id) is Locale.EN


async def test_une_eglise_inconnue_ou_illisible_rend_le_defaut(session):
    church = _church(language="es")
    session.add(church)
    await session.flush()
    resolver = SqlLocaleResolver(session)

    assert await resolver.resolve_tenant(church.id) is DEFAULT_LOCALE
    assert await resolver.resolve_tenant(uuid4()) is DEFAULT_LOCALE
