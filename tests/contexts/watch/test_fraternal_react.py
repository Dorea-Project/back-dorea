"""**Le react fraternel** — *« tu es passé voir Anna il y a un mois. Un mot ? »*

Le dernier lot du chantier, et celui dont la forme a été dictée par ce qu'il ne devait **pas**
pouvoir faire.

La version évidente — chercher de qui Jean est un proche — cassait deux règles d'un coup : le
graphe devenait énumérable, et Jean apprenait qu'Anna l'avait nommé. La version corrigée — filtrer
sur le silence d'Anna — en cassait une troisième, plus discrète : la présence d'Anna dans la liste
de Jean *serait* l'information, donc un cas de veille fuité à un membre.

Ce qui reste ne se calcule que sur **les propres actes de Jean**. C'est ce que ces tests vérifient,
et surtout ce qu'ils vérifient qu'on ne peut pas apprendre.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.fraternal_react import SuggestFraternalReacts
from app.contexts.watch.application.ports import GestureTowards
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from app.contexts.watch.infrastructure.persistence.ledger import fold_my_gestures
from tests.contexts.watch.fakes import FakeSignals

_NOW = datetime(2026, 8, 5, tzinfo=UTC)
_AFTER = timedelta(days=DEFAULTS[WatchParam.REACT_AFTER_DAYS])


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


class _MyGestures:
    """Les gestes que j'ai posés — mêmes bornes que le SQL, même pli."""

    def __init__(self, rows):
        self._rows = rows  # (actor, subject, at)

    async def gestures_by(self, *, actor_account_id, tenant_id, before, limit=5):
        return fold_my_gestures(
            (
                (subject, {"kind": "visit"}, at, actor)
                for actor, subject, at in sorted(
                    self._rows, key=lambda r: r[2], reverse=True
                )
                if at <= before
            ),
            actor_account_id=actor_account_id,
            limit=limit,
        )

    async def gestures_between(self, *, subject_id, tenant_id, since, until, limit=3):
        return []


class _Exclusions:
    def __init__(self, excluded=()):
        self._excluded = set(excluded)

    async def excluded_subject_ids(self, tenant_id):
        return self._excluded


class _People:
    def __init__(self, *, ineligible=None):
        self._ineligible = ineligible

    async def is_eligible(self, account_id, tenant_id):
        return account_id != self._ineligible


def _query(gestures, signals=None, *, excluded=(), people=None, **params):
    return SuggestFraternalReacts(
        gestures,
        signals or FakeSignals(),
        _Exclusions(excluded),
        people or _People(),
        _Params(**params),
        clock=lambda: _NOW,
    )


# --- Ce qu'il propose ---------------------------------------------------------------------


async def test_it_suggests_writing_again_to_someone_you_visited_a_month_ago():
    """La proposition part du geste de **Jean**, et la date rendue est la sienne.

    C'est la seule date qu'on ait le droit de lui donner. Rendre « Anna n'a pas donné de nouvelles
    depuis 5 semaines » serait lui apprendre quelque chose sur elle — et ce quelque chose est
    précisément ce qu'un cas de veille contient."""
    tenant, jean, anna = uuid4(), uuid4(), uuid4()
    passe_le = _NOW - _AFTER - timedelta(days=9)

    (react,) = await _query(_MyGestures([(jean, anna, passe_le)])).execute(
        actor_account_id=jean, tenant_id=tenant
    )

    assert react.account_id == anna
    assert react.last_gesture_at == passe_le


async def test_a_visit_still_fresh_proposes_nothing():
    """Trois semaines, pas trois jours : on ne rappelle pas à quelqu'un ce qu'il vient de faire."""
    tenant, jean, anna = uuid4(), uuid4(), uuid4()

    assert (
        await _query(
            _MyGestures([(jean, anna, _NOW - timedelta(days=2))])
        ).execute(actor_account_id=jean, tenant_id=tenant)
        == []
    )


async def test_three_visits_to_the_same_person_make_one_invitation_dated_from_the_last():
    """Une personne, une fois — et datée du **dernier** passage.

    Sinon on rappellerait à Jean une visite qu'il a déjà répétée, ce qui est la meilleure façon de
    lui apprendre à ne plus lire l'écran."""
    tenant, jean, anna = uuid4(), uuid4(), uuid4()
    dernier = _NOW - _AFTER - timedelta(days=1)
    rows = [
        (jean, anna, dernier - timedelta(days=40)),
        (jean, anna, dernier - timedelta(days=20)),
        (jean, anna, dernier),
    ]

    (react,) = await _query(_MyGestures(rows)).execute(
        actor_account_id=jean, tenant_id=tenant
    )

    assert react.last_gesture_at == dernier


async def test_two_invitations_at_most_because_a_dozen_names_is_a_task_list():
    """Une invitation qu'on ne peut pas honorer devient une dette — et le produit s'interdit d'en
    fabriquer."""
    tenant, jean = uuid4(), uuid4()
    vieux = _NOW - _AFTER - timedelta(days=5)
    rows = [(jean, uuid4(), vieux - timedelta(days=n)) for n in range(10)]

    reacts = await _query(_MyGestures(rows)).execute(
        actor_account_id=jean, tenant_id=tenant
    )

    assert len(reacts) == DEFAULTS[WatchParam.REACT_SUGGESTIONS_CAP]


# --- Ce qu'il refuse de proposer, et sans jamais dire pourquoi -------------------------------


async def test_someone_who_asked_us_to_stop_simply_disappears_from_the_list():
    """**Aucune des trois sorties n'est expliquée à Jean.**

    Une demande d'arrêt, un décès, un départ : la proposition disparaît, et rien ne dit laquelle
    des trois — sinon la disparition elle-même deviendrait une information sur la personne."""
    tenant, jean, anna = uuid4(), uuid4(), uuid4()
    signals = FakeSignals()
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=anna, origin=CasePriority.ABSENCE,
        reason="…", opened_at=_NOW - timedelta(days=60), status=SignalStatus.ASSIGNED,
        owner_account_id=uuid4(),
    )
    case.close(
        outcome=SignalOutcome.DO_NOT_CONTACT, at=_NOW, closed_by_account_id=uuid4()
    )
    signals.rows.append(case)

    reacts = await _query(
        _MyGestures([(jean, anna, _NOW - _AFTER - timedelta(days=3))]), signals
    ).execute(actor_account_id=jean, tenant_id=tenant)

    assert reacts == []


async def test_someone_retired_from_the_watch_is_never_proposed():
    tenant, jean, anna = uuid4(), uuid4(), uuid4()

    reacts = await _query(
        _MyGestures([(jean, anna, _NOW - _AFTER - timedelta(days=3))]),
        excluded={anna},
    ).execute(actor_account_id=jean, tenant_id=tenant)

    assert reacts == []


async def test_someone_who_left_the_church_is_never_proposed():
    tenant, jean, anna = uuid4(), uuid4(), uuid4()

    reacts = await _query(
        _MyGestures([(jean, anna, _NOW - _AFTER - timedelta(days=3))]),
        people=_People(ineligible=anna),
    ).execute(actor_account_id=jean, tenant_id=tenant)

    assert reacts == []


# --- Ce qu'il n'apprend à personne ----------------------------------------------------------


async def test_luc_never_learns_who_jean_went_to_see():
    """La borne est l'acteur, et elle tient : Luc ne reçoit que **ses** gestes.

    C'est ce qui interdit de reconstituer le graphe en interrogeant la route avec deux comptes —
    chacun ne voit que ce qu'il a fait lui-même."""
    tenant, jean, luc, anna, sondet = (uuid4() for _ in range(5))
    vieux = _NOW - _AFTER - timedelta(days=4)
    gestures = _MyGestures([(jean, anna, vieux), (luc, sondet, vieux)])

    pour_luc = await _query(gestures).execute(actor_account_id=luc, tenant_id=tenant)

    assert [r.account_id for r in pour_luc] == [sondet]


def test_the_response_carries_no_measure_of_the_other_persons_silence():
    """**Le test qui garde la frontière** : la vue n'a que deux champs, et les deux sont à Jean.

    Ajouter un jour « depuis combien de temps on ne l'a pas vue » rendrait la liste utile — et
    ferait d'elle, du même coup, la liste des gens qui vont mal, remise à un membre."""
    from dataclasses import fields

    from app.contexts.watch.application.fraternal_react import FraternalReact

    assert {f.name for f in fields(FraternalReact)} == {
        "account_id",
        "last_gesture_at",
    }


def test_the_fold_only_keeps_what_i_signed_myself():
    """Le pli isolé : un geste signé par quelqu'un d'autre n'entre jamais dans ma liste."""
    jean, luc, anna = uuid4(), uuid4(), uuid4()

    plie = fold_my_gestures(
        [
            (anna, {"kind": "visit"}, _NOW, luc),
            (anna, {"kind": "call"}, _NOW - timedelta(days=1), jean),
        ],
        actor_account_id=jean,
        limit=5,
    )

    assert [g.subject_id for g in plie] == [anna]
    assert isinstance(plie[0], GestureTowards)
    assert plie[0].kind == "call"  # celui de Jean, pas celui de Luc
