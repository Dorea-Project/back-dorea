"""L'anniversaire — *Dorea rappelle aux humains d'aimer ; il n'aime jamais à leur place.*

Une date déclarée, affichée au bon moment, au cercle que le membre a choisi, pour provoquer un
geste **humain**. L'essentiel du travail de ces deux services est de refuser : refuser d'afficher
l'année, refuser d'afficher ce qui est masqué, refuser qu'un tiers pose la date de quelqu'un.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.contexts.iam.application.birthdays import BirthdaysToday, SetMyBirthday
from app.contexts.iam.domain.birthday import (
    DEFAULT_SCOPE,
    Birthday,
    BirthdayScope,
    InvalidBirthdayError,
)
from app.contexts.watch.domain.facts import FactKind

_TODAY = datetime(2026, 6, 12, 9, 0, tzinfo=UTC)  # un 12 juin


class _Accounts:
    def __init__(self):
        self.saved: dict = {}

    async def set_birthday(self, *, account_id, day, month, year, scope):
        self.saved = {
            "account_id": account_id, "day": day, "month": month, "year": year, "scope": scope
        }


class _Directory:
    """Les gens des groupes du viewer, et qui veille sur qui.

    `lookups` compte les résolutions de référent : chacune coûte une douzaine de requêtes en
    vrai, et l'encart ne doit pas en lancer une par membre de mes groupes."""

    def __init__(self, rows, referents=None):
        self._rows = rows
        self._referents = referents or {}
        self.lookups = 0

    async def candidates(self, *, viewer_account_id, tenant_id):
        return self._rows

    async def referent_of(self, account_id, tenant_id):
        self.lookups += 1
        return self._referents.get(account_id)


def _row(account_id, *, day, month, scope=BirthdayScope.GROUPS, first="Awa"):
    return (account_id, first, "Diallo", day, month, scope.value)


def _query(rows, referents=None, *, at=_TODAY):
    return BirthdaysToday(_Directory(rows, referents), clock=lambda: at)


# --- Ce que le membre pose ---------------------------------------------------------------


async def test_the_member_posts_his_own_date_and_nobody_elses():
    """La saisie appartient au membre : le service ne prend aucun identifiant de sujet."""
    accounts, awa = _Accounts(), uuid4()

    await SetMyBirthday(accounts).execute(actor_account_id=awa, day=12, month=6)

    assert accounts.saved["account_id"] == awa
    assert accounts.saved["scope"] == DEFAULT_SCOPE.value


async def test_a_date_that_does_not_exist_is_refused():
    with pytest.raises(InvalidBirthdayError):
        await SetMyBirthday(_Accounts()).execute(
            actor_account_id=uuid4(), day=31, month=2
        )


def test_the_29th_of_february_is_a_real_birthday():
    """On n'a jamais refusé à quelqu'un sa propre date de naissance."""
    assert Birthday(day=29, month=2).day == 29


# --- Ce qui s'affiche, et ce qui ne s'affiche jamais -------------------------------------


async def test_the_year_appears_in_no_dto_at_all():
    """L'âge de quelqu'un n'est pas une donnée d'église. Le DTO n'a **pas de champ** pour le dire.

    C'est la même mécanique que partout ailleurs : ce qui ne doit pas sortir n'a pas de forme."""
    from app.contexts.iam.application.birthdays import BirthdayOfTheDay

    fields = set(BirthdayOfTheDay.__dataclass_fields__)
    assert not any("year" in f or "age" in f for f in fields)

    awa = uuid4()
    (shown,) = await _query([_row(awa, day=12, month=6)]).execute(
        viewer_account_id=uuid4(), tenant_id=uuid4()
    )
    assert not hasattr(shown, "birth_year")


async def test_hidden_shows_nothing_to_anybody():
    """`HIDDEN` est absolu — y compris pour le pasteur et pour son référent.

    Même mécanique que `DO_NOT_CONTACT` : le réglage du membre absorbe, et aucune bonne intention
    ne le lève."""
    fatou, pastor = uuid4(), uuid4()
    rows = [_row(fatou, day=12, month=6, scope=BirthdayScope.HIDDEN, first="Fatou")]

    shown = await _query(rows, {fatou: pastor}).execute(
        viewer_account_id=pastor, tenant_id=uuid4()
    )

    assert shown == []


async def test_referent_only_shows_to_the_referent_and_to_nobody_else():
    fatou, referent, other = uuid4(), uuid4(), uuid4()
    rows = [_row(fatou, day=12, month=6, scope=BirthdayScope.REFERENT_ONLY)]
    referents = {fatou: referent}

    seen_by_referent = await _query(rows, referents).execute(
        viewer_account_id=referent, tenant_id=uuid4()
    )
    seen_by_group = await _query(rows, referents).execute(
        viewer_account_id=other, tenant_id=uuid4()
    )

    assert len(seen_by_referent) == 1
    assert seen_by_group == []


async def test_an_unset_date_is_the_same_as_hidden():
    """Ne rien renseigner **est** une réponse : le champ reste optionnel."""
    shown = await _query([_row(uuid4(), day=None, month=None)]).execute(
        viewer_account_id=uuid4(), tenant_id=uuid4()
    )
    assert shown == []


# --- Le bon moment -----------------------------------------------------------------------


async def test_the_group_sees_it_on_the_day():
    awa = uuid4()
    (shown,) = await _query([_row(awa, day=12, month=6)]).execute(
        viewer_account_id=uuid4(), tenant_id=uuid4()
    )
    assert shown.account_id == awa and shown.is_today is True


async def test_only_the_referent_is_told_the_day_before():
    """Prévenir la veille aide celui qui prépare un geste ; à tout le groupe, c'est un rappel de
    plus."""
    awa, referent, other = uuid4(), uuid4(), uuid4()
    rows = [_row(awa, day=13, month=6)]  # demain
    referents = {awa: referent}

    (ahead,) = await _query(rows, referents).execute(
        viewer_account_id=referent, tenant_id=uuid4()
    )
    assert ahead.is_today is False
    assert await _query(rows, referents).execute(
        viewer_account_id=other, tenant_id=uuid4()
    ) == []


async def test_the_29th_of_february_is_celebrated_on_the_28th_in_ordinary_years():
    """Le détail qui vexe s'il manque : sinon on n'a un anniversaire qu'une année sur quatre."""
    awa = uuid4()
    rows = [_row(awa, day=29, month=2)]

    ordinary = await _query(rows, at=datetime(2027, 2, 28, tzinfo=UTC)).execute(
        viewer_account_id=uuid4(), tenant_id=uuid4()
    )
    leap = await _query(rows, at=datetime(2028, 2, 28, tzinfo=UTC)).execute(
        viewer_account_id=uuid4(), tenant_id=uuid4()
    )

    assert len(ordinary) == 1  # 2027 n'est pas bissextile : on le fête le 28
    assert leap == []  # 2028 l'est : ce sera le 29


async def test_nobody_wishes_himself_a_happy_birthday():
    awa = uuid4()
    shown = await _query([_row(awa, day=12, month=6)]).execute(
        viewer_account_id=awa, tenant_id=uuid4()
    )
    assert shown == []


async def test_nobodys_referent_is_resolved_for_a_birthday_in_november():
    """**On écarte sur la date avant d'interroger quoi que ce soit.**

    Résoudre un référent coûte une douzaine de requêtes ; le faire pour chaque membre de mes
    groupes reviendrait à en lancer des centaines pour n'afficher, la plupart des jours, personne.
    """
    directory = _Directory([_row(uuid4(), day=3, month=11) for _ in range(40)])

    shown = await BirthdaysToday(directory, clock=lambda: _TODAY).execute(
        viewer_account_id=uuid4(), tenant_id=uuid4()
    )

    assert shown == []
    assert directory.lookups == 0


async def test_the_referent_is_resolved_only_for_the_few_that_could_show():
    """Un seul candidat du jour parmi trente : une seule résolution."""
    awa = uuid4()
    rows = [_row(uuid4(), day=3, month=11) for _ in range(30)]
    rows.append(_row(awa, day=12, month=6, scope=BirthdayScope.REFERENT_ONLY))
    directory = _Directory(rows, {awa: uuid4()})

    await BirthdaysToday(directory, clock=lambda: _TODAY).execute(
        viewer_account_id=uuid4(), tenant_id=uuid4()
    )

    assert directory.lookups == 1


# --- Ce que l'anniversaire n'est pas -----------------------------------------------------


def test_no_birthday_fact_exists_in_the_engine():
    """Aucun fait au ledger, aucun cas, aucune entrée dans le plafond.

    Un anniversaire n'est pas un signal de veille : c'est une attention. Le type qui en ferait un
    signal n'existe pas — même patron que les familles interdites de `FactKind`."""
    assert not any("birth" in kind.value for kind in FactKind)


def test_the_visibility_is_a_closed_list():
    """Trois valeurs, et pas de quatrième « sauf si » à inventer un jour."""
    assert {s.value for s in BirthdayScope} == {"groups", "referent_only", "hidden"}


def test_the_day_before_is_computed_not_stored():
    """Aucune échéance, aucun worker : l'encart se calcule à la lecture."""
    assert Birthday(day=1, month=1).falls_on(date(2026, 1, 1)) is True
    assert Birthday(day=1, month=1).falls_on(date(2026, 1, 2)) is False
