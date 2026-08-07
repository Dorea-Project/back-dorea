"""**Le lien déclaré** — *« voici par qui vous pouvez me rejoindre »*.

Le lien par geste arrive trop tard, et jamais pour celui qui en a le plus besoin : il n'apparaît
que quand quelqu'un s'est déjà approché. Pour la personne dont personne ne s'approche, le journal
reste vide exactement là où il fallait un nom.

Celui-ci attaque par l'autre bout, et il est le **fort** des deux — parce qu'il porte un accord.
En nommant Jean, Sondet ne donne pas un renseignement : il dit *« vous pouvez passer par lui »*.

Ces tests tiennent les cinq gardes du lot, et la plus importante n'est pas technique : le retrait
sans motif existe pour le lien conjugal, celui qu'on a le plus de raisons de retirer.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.declare_link import MAX_LINKS, DeclareLink
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.self_declaration import (
    DeclarationKind,
    SelfDeclarationV1,
)
from app.contexts.watch.application.ports import DeclaredLink
from app.contexts.watch.application.restitution import GetCaseContext
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.errors import (
    IneligibleReferentError,
    SelfReferentError,
    TooManyLinksError,
)
from app.contexts.watch.domain.facts import FactKind
from app.contexts.watch.domain.registry import default_registry
from app.contexts.watch.domain.signal import Signal, SignalStatus
from app.contexts.watch.domain.transparency import is_listable_to_subject
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from app.contexts.watch.infrastructure.persistence.ledger import fold_declared_links
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 8, 5, tzinfo=UTC)


class _Links:
    """La lecture des liens, **par le même pli que le SQL** — deux versions auraient divergé."""

    def __init__(self, ledger):
        self._ledger = ledger

    async def declared_links(self, *, subject_id, tenant_id):
        return fold_declared_links(
            (dict(f.payload), f.occurred_at)
            for f in sorted(self._ledger.rows, key=lambda f: f.seq or 0)
            if f.kind is FactKind.SELF_DECLARATION
            and f.subject_id == subject_id
            and f.tenant_id == tenant_id
        )


class _People:
    def __init__(self, *, ineligible=None):
        self._ineligible = ineligible

    async def is_eligible(self, account_id, tenant_id):
        return account_id != self._ineligible


class _NoAttempts:
    async def recent_for(self, *, signal_id, limit=3):
        return []


def _command(ledger, signals, *, people=None):
    interpreters = InterpreterRegistry()
    interpreters.register(SelfDeclarationV1())
    intake = Intake(
        ledger, default_registry(), interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()), signals,
    )
    return DeclareLink(
        intake, _Links(ledger), people or _People(), clock=lambda: _NOW
    )


# --- Ce qu'il fait ------------------------------------------------------------------------


async def test_naming_a_close_one_opens_no_case_and_writes_no_projection():
    """Nommer un proche est un **réglage**, pas un appel à l'aide.

    Comme le rythme qu'on choisit pour soi, il ne produit aucun effet : ni cas, ni échéance, ni
    annotation. Le fait reste au journal, et le seul endroit où il ressort est le bloc que le
    responsable relit avant d'appeler — un saut, un cas, un lecteur."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()

    ack = await _command(ledger, signals).execute(
        actor_account_id=sondet, linked_account_id=jean, tenant_id=tenant
    )

    assert signals.rows == []
    assert ack.remaining == MAX_LINKS - 1
    (fact,) = ledger.rows
    assert fact.subject_id == sondet  # sa parole sur elle-même
    assert fact.payload["kind"] == DeclarationKind.LINK_DECLARED.value


async def test_the_named_person_never_appears_as_a_subject_of_any_fact():
    """**Aucun fait n'est jamais posé *sur* Jean.**

    Il n'est qu'une valeur du payload — c'est ce qui fait qu'il n'est pas prévenu, qu'il n'a rien
    à consentir, et qu'aucun compteur ne peut se former sur lui. Le degré entrant n'existe pas."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()

    await _command(ledger, signals).execute(
        actor_account_id=sondet, linked_account_id=jean, tenant_id=tenant
    )

    assert all(f.subject_id != jean for f in ledger.rows)


async def test_the_subject_can_list_what_she_declared_herself():
    """La frontière de transparence tombe toute seule : c'est **son propre acte**.

    Le lien par geste, lui, décrit l'engagement du tiers et reste hors de sa vue. Les deux liens
    n'ont donc pas le même régime, et c'est cohérent — pas une exception de plus."""
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()
    await _command(ledger, signals).execute(
        actor_account_id=sondet, linked_account_id=jean, tenant_id=tenant
    )

    assert is_listable_to_subject(ledger.rows[0])


# --- Les gardes ---------------------------------------------------------------------------


async def test_nobody_is_a_path_towards_themselves():
    tenant, sondet = uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()

    with pytest.raises(SelfReferentError):
        await _command(ledger, signals).execute(
            actor_account_id=sondet, linked_account_id=sondet, tenant_id=tenant
        )


async def test_someone_who_left_the_church_cannot_be_named():
    tenant, sondet, parti = uuid4(), uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()

    with pytest.raises(IneligibleReferentError):
        await _command(ledger, signals, people=_People(ineligible=parti)).execute(
            actor_account_id=sondet, linked_account_id=parti, tenant_id=tenant
        )


async def test_a_fourth_name_is_refused_because_a_list_of_friends_calls_for_a_screen():
    """Trois chemins, c'est du routage. Quatre, c'est un carnet d'adresses affectif — et un objet
    social finit toujours par appeler un écran qui le montre."""
    tenant, sondet = uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()
    command = _command(ledger, signals)
    for _ in range(MAX_LINKS):
        await command.execute(
            actor_account_id=sondet, linked_account_id=uuid4(), tenant_id=tenant
        )

    with pytest.raises(TooManyLinksError):
        await command.execute(
            actor_account_id=sondet, linked_account_id=uuid4(), tenant_id=tenant
        )


async def test_naming_the_same_person_twice_does_not_consume_a_second_place():
    tenant, sondet, jean = uuid4(), uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()
    command = _command(ledger, signals)
    await command.execute(
        actor_account_id=sondet, linked_account_id=jean, tenant_id=tenant
    )

    ack = await command.execute(
        actor_account_id=sondet, linked_account_id=jean, tenant_id=tenant
    )

    assert ack.remaining == MAX_LINKS - 1


# --- Le retrait, et pourquoi il compte le plus ---------------------------------------------


async def test_removing_a_link_needs_no_reason_and_frees_the_place():
    """**La clause qui tient l'éthique du lot.**

    Le lien conjugal est celui qu'on a le plus de raisons de retirer : un foyer violent, une
    séparation en cours. Si le conjoint est la route par laquelle l'église prend de vos nouvelles,
    la personne qui aurait besoin d'être rejointe *hors* du foyer n'a plus de sortie.

    Le retrait n'écrit aucun motif, et le journal ne se corrige pas : on ajoute un fait qui dit
    autre chose, et le pli à la lecture n'en tient plus compte."""
    tenant, sondet, conjoint = uuid4(), uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()
    command = _command(ledger, signals)
    await command.execute(
        actor_account_id=sondet, linked_account_id=conjoint, tenant_id=tenant
    )

    ack = await command.remove(
        actor_account_id=sondet, linked_account_id=conjoint, tenant_id=tenant
    )

    assert ack.remaining == MAX_LINKS
    assert len(ledger.rows) == 2  # append-only : le premier fait est toujours là
    assert await _Links(ledger).declared_links(
        subject_id=sondet, tenant_id=tenant
    ) == []


# --- Ce que le responsable en lit ----------------------------------------------------------


async def test_the_leader_reads_the_declared_link_before_the_gesture():
    """**L'ordre est la spécification.** Ce qu'elle a consenti d'avance passe avant ce qu'on a
    déduit d'un acte : en nommant Jean, elle a dit qu'on pouvait passer par lui ; personne n'a
    rien demandé à celui qui est passé.

    Et la phrase porte une **question**, pas une information : on ne dit pas au responsable ce que
    Jean sait — on lui dit qu'il peut le lui demander."""
    tenant, sondet, jean, responsable = uuid4(), uuid4(), uuid4(), uuid4()
    ledger, signals = FakeLedger(), FakeSignals()
    await _command(ledger, signals).execute(
        actor_account_id=sondet, linked_account_id=jean, tenant_id=tenant
    )
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=sondet, origin=CasePriority.ABSENCE,
        reason="Sans nouvelles.", opened_at=_NOW - timedelta(days=2),
        status=SignalStatus.ASSIGNED, owner_account_id=responsable,
    )
    signals.rows.append(case)

    context = await GetCaseContext(
        signals, _NoAttempts(), None, _People(), _Links(ledger), clock=lambda: _NOW
    ).execute(signal_id=case.id, tenant_id=tenant, actor_account_id=responsable)

    (link,) = [s for s in context.segments if s.kind == "declared_link"]
    assert link.account_id == jean
    assert link.text.endswith("Vous pouvez lui demander de ses nouvelles.")
    assert link.source == "watch_facts.self_declaration"


def test_the_fold_keeps_the_last_word_per_person():
    """Le pli, isolé : dernière déclaration gagnante, et un retrait ne ressuscite pas."""
    jean, luc = uuid4(), uuid4()
    plie = fold_declared_links(
        [
            ({"kind": "link_declared", "linked_account_id": str(jean)}, _NOW),
            ({"kind": "link_declared", "linked_account_id": str(luc)}, _NOW),
            (
                {
                    "kind": "link_declared",
                    "linked_account_id": str(jean),
                    "active": "false",
                },
                _NOW + timedelta(days=1),
            ),
            ({"kind": "rhythm", "every_days": "7"}, _NOW),  # ignoré : autre geste
        ]
    )

    assert [link.linked_account_id for link in plie] == [luc]
    assert isinstance(plie[0], DeclaredLink)
