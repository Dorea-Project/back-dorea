"""La restitution — *« Dorea me connaît mieux que mon cahier ».*

Avant d'appeler, Jean relit six mois de lien en quatre lignes au lieu de faire défiler onze entrées
dans le bus. Ce que ces tests vérifient, ce n'est pas la mise en forme : c'est que **chaque phrase
est un champ**, qu'aucune n'est une conclusion, et qu'un cas sans histoire n'affiche rien.

La découverte en spécifiant : tout ce que le résumé contenait était **déjà structuré** en base. Des
gabarits fermés suffisent — zéro token d'IA, coût nul, et rien qui puisse déformer ce que quelqu'un
a écrit.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.watch.application.restitution import GetCaseContext
from app.contexts.watch.domain.contact import (
    ContactAttempt,
    ContactChannel,
    ContactResult,
)
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.errors import NotYourCaseError
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from tests.contexts.watch.fakes import FakeContactAttempts, FakeSignals

_NOW = datetime(2026, 6, 18, tzinfo=UTC)


def _case(signals, *, tenant, subject, owner, **kwargs):
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=subject, origin=CasePriority.ABSENCE,
        reason="Sans nouvelles — 3 rencontres de la cellule Bethel.",
        opened_at=_NOW - timedelta(days=6), status=SignalStatus.ASSIGNED,
        owner_account_id=owner, **kwargs,
    )
    signals.rows.append(case)
    return case


def _attempt(attempts, *, tenant, case, by, at, result=ContactResult.REACHED, note=None):
    attempt = ContactAttempt(
        id=uuid4(), tenant_id=tenant, signal_id=case.id, by_account_id=by,
        channel=ContactChannel.CALL, attempted_at=at, result=result,
        answered_at=at, commitment=note,
    )
    attempts.rows.append(attempt)
    return attempt


def _context(signals, attempts):
    return GetCaseContext(signals, attempts, clock=lambda: _NOW)


# --- Chaque phrase est un champ ----------------------------------------------------------


async def test_every_segment_is_traceable_to_a_field():
    """La traçabilité est **gratuite** ici, puisque chaque phrase *est* un champ.

    C'est ce qui permet au responsable de vérifier au lieu de croire — et ce qu'un résumé produit
    par une machine ne pourrait pas offrir sans travail supplémentaire."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(
        signals, tenant=tenant, subject=subject, owner=jean,
        previous_outcome=SignalOutcome.FOLLOWED,
        previous_closed_at=_NOW - timedelta(days=90),
        occurrence_number=2,
    )
    signals.memory.append(
        (tenant, subject, "return_confirmed", _NOW - timedelta(days=120), "…", None)
    )
    _attempt(
        attempts, tenant=tenant, case=case, by=jean, at=_NOW - timedelta(days=4),
        note="Je la rappelle jeudi.",
    )

    dto = await _context(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    assert all(s.source for s in dto.segments)
    kinds = [s.kind for s in dto.segments]
    assert kinds[0] == "link"  # « vous l'accompagnez depuis février »
    assert "episode" in kinds and "present" in kinds
    assert "last_contact" in kinds and "commitment" in kinds


async def test_it_says_since_when_you_accompany_her():
    """La phrase que le responsable ne peut pas reconstruire de tête."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)
    signals.memory.append(
        (tenant, subject, "return_confirmed", datetime(2026, 2, 3, tzinfo=UTC), "…", None)
    )

    dto = await _context(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    (link,) = [s for s in dto.segments if s.kind == "link"]
    assert link.text == "Vous l'accompagnez depuis février."


async def test_it_quotes_the_commitment_it_never_rewrites_it():
    """Citer n'est pas résumer : aucun risque de déformer ce qu'on s'était engagé à faire."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)
    _attempt(
        attempts, tenant=tenant, case=case, by=jean, at=_NOW - timedelta(days=4),
        note="Je passe déposer le colis samedi.",
    )

    dto = await _context(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    (commitment,) = [s for s in dto.segments if s.kind == "commitment"]
    assert "Je passe déposer le colis samedi." in commitment.text


async def test_the_previous_outcome_is_read_in_plain_words():
    """« Cas précédent clos le 20 mars — repris contact, situation suivie. C'est la 2ᵉ fois. »

    Ce qui évite d'ouvrir un appel par « je vois que tu n'es pas venue » à quelqu'un à qui on a
    déjà parlé il y a trois mois."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(
        signals, tenant=tenant, subject=subject, owner=jean,
        previous_outcome=SignalOutcome.FOLLOWED,
        previous_closed_at=datetime(2026, 3, 20, tzinfo=UTC),
        occurrence_number=2,
    )

    dto = await _context(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    (episode,) = [s for s in dto.segments if s.kind == "episode"]
    assert "20 mars" in episode.text
    assert "repris contact, situation suivie" in episode.text
    assert "2ᵉ fois" in episode.text


# --- Ce que le bloc ne fait pas ----------------------------------------------------------


async def test_a_case_without_a_story_shows_nothing():
    """Pas de bloc vide, pas de « aucune information » : un encart qui ne dit rien apprend au
    lecteur à ne plus le lire.

    Seule la raison du jour reste — et c'est déjà affiché ailleurs sur l'écran."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)

    dto = await _context(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    assert [s.kind for s in dto.segments] == ["present"]  # rien à raconter d'autre


async def test_a_pending_attempt_says_nothing_yet():
    """Une tentative partie dont personne n'est revenu dire l'issue n'a rien à raconter."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)
    _attempt(
        attempts, tenant=tenant, case=case, by=jean, at=_NOW - timedelta(hours=2),
        result=ContactResult.PENDING,
    )

    dto = await _context(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    assert not [s for s in dto.segments if s.kind == "last_contact"]


async def test_the_block_is_served_to_the_owner_and_to_nobody_else():
    """Le même contrôle que le reste de l'écran du cas : rien de nouveau à sécuriser."""
    tenant, subject, jean, someone = uuid4(), uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(signals, tenant=tenant, subject=subject, owner=jean)

    with pytest.raises(NotYourCaseError):
        await _context(signals, attempts).execute(
            signal_id=case.id, tenant_id=tenant, actor_account_id=someone
        )


async def test_the_vocabulary_of_the_block_is_closed():
    """Cinq sortes de segments, et pas une sixième à inventer un jour.

    Le bloc rend des faits datés : d'où vient le lien, ce qui s'est passé avant, ce qui se passe
    aujourd'hui, le dernier contact, et ce qu'on avait promis. Aucune n'énonce un jugement — et
    ajouter une sorte qui en énoncerait un demanderait de la nommer ici, donc de la décider."""
    tenant, subject, jean = uuid4(), uuid4(), uuid4()
    signals, attempts = FakeSignals(), FakeContactAttempts()
    case = _case(
        signals, tenant=tenant, subject=subject, owner=jean,
        previous_outcome=SignalOutcome.FOLLOWED,
        previous_closed_at=_NOW - timedelta(days=60),
        occurrence_number=2,
    )
    case.annotations.append("A annulé le rendez-vous qu'il avait demandé.")
    signals.memory.append(
        (tenant, subject, "return_confirmed", _NOW - timedelta(days=90), "…", None)
    )
    _attempt(
        attempts, tenant=tenant, case=case, by=jean, at=_NOW - timedelta(days=2),
        note="Je la rappelle jeudi.",
    )

    dto = await _context(signals, attempts).execute(
        signal_id=case.id, tenant_id=tenant, actor_account_id=jean
    )

    assert {s.kind for s in dto.segments} <= {
        "link", "episode", "present", "last_contact", "commitment"
    }
    # Et le cas riche produit bien les cinq : le test ne passerait pas sur un bloc vide.
    assert {s.kind for s in dto.segments} == {
        "link", "episode", "present", "last_contact", "commitment"
    }
