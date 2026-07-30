"""La note du responsable — **sur son geste, jamais sur la personne**.

Décision du 30 juillet 2026. Jusqu'ici la veille n'avait aucun champ de texte libre, et c'était
délibéré : `RaiseConcern` dit noir sur blanc *« il n'y a pas de champ où l'écrire »*, ce qui règle
le problème du diagnostic par construction. Un « je la sens fragile » conservé fait une fiche.

Ce champ-ci ne rouvre pas cette porte, et la garantie n'est pas une consigne de rédaction : c'est
**où la colonne vit**. Elle est portée par la tentative de contact — un acte déjà daté et signé par
celui qui l'a posé. Il n'existe toujours aucun endroit où écrire quelque chose *sur* un membre.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.watch.application.contact_loop import AnswerContact, StartContact
from app.contexts.watch.domain.contact import ContactChannel, ContactResult
from app.contexts.watch.domain.effects import CasePriority
from app.contexts.watch.domain.signal import Signal, SignalStatus
from app.contexts.watch.infrastructure.persistence import models
from tests.contexts.watch.fakes import FakeContactAttempts, FakeSignals

_NOW = datetime(2026, 8, 3, tzinfo=UTC)

# Rien ne filtre ce qu'un responsable écrit — on ne censure pas quelqu'un qui prend soin. Ce qui
# tient la règle, c'est qu'un « elle semble fragile » n'a **aucun endroit où vivre** : le seul
# champ de texte est attaché à un geste, daté et signé par son auteur.


def _case(signals, *, tenant, owner):
    case = Signal(
        id=uuid4(), tenant_id=tenant, subject_id=uuid4(), origin=CasePriority.ABSENCE,
        reason="Sans nouvelles.", opened_at=_NOW - timedelta(days=7),
        status=SignalStatus.ASSIGNED, owner_account_id=owner,
    )
    signals.rows.append(case)
    return case


async def _attempt(attempts, signals, *, tenant, owner):
    case = _case(signals, tenant=tenant, owner=owner)
    started = await StartContact(
        attempts, signals, None, clock=lambda: _NOW, id_factory=uuid4
    ).execute(
        signal_id=case.id, tenant_id=tenant, by_account_id=owner,
        channel=ContactChannel.CALL, person_label="Awa",
    )
    return started.attempt_id


# --- Ce que la note est ------------------------------------------------------------------


async def test_the_note_records_what_i_will_do_next():
    tenant, lead = uuid4(), uuid4()
    attempts, signals = FakeContactAttempts(), FakeSignals()
    attempt_id = await _attempt(attempts, signals, tenant=tenant, owner=lead)

    resolved = await AnswerContact(attempts, signals, clock=lambda: _NOW).execute(
        attempt_id=attempt_id,
        result=ContactResult.REACHED,
        commitment="Je repasse jeudi avec le colis.",
    )

    assert resolved.commitment == "Je repasse jeudi avec le colis."
    # Elle est datée et signée par construction : ce sont les champs de la tentative.
    assert resolved.by_account_id == lead
    assert resolved.answered_at == _NOW


async def test_an_empty_note_is_no_note():
    """Un responsable qui n'écrit rien n'a rien manqué : la boucle n'est pas un formulaire."""
    tenant, lead = uuid4(), uuid4()
    attempts, signals = FakeContactAttempts(), FakeSignals()
    attempt_id = await _attempt(attempts, signals, tenant=tenant, owner=lead)

    resolved = await AnswerContact(attempts, signals, clock=lambda: _NOW).execute(
        attempt_id=attempt_id, result=ContactResult.REACHED, commitment="   "
    )

    assert resolved.commitment is None


async def test_the_note_is_written_once_like_the_outcome():
    """On ne réécrit pas une tentative résolue — ni son issue, ni ce qu'on avait promis.

    Une correction tardive brouillerait la métrique **et** transformerait la note en journal
    modifiable sur quelqu'un."""
    tenant, lead = uuid4(), uuid4()
    attempts, signals = FakeContactAttempts(), FakeSignals()
    attempt_id = await _attempt(attempts, signals, tenant=tenant, owner=lead)
    answer = AnswerContact(attempts, signals, clock=lambda: _NOW)

    await answer.execute(
        attempt_id=attempt_id, result=ContactResult.REACHED, commitment="Je rappelle jeudi."
    )
    again = await answer.execute(
        attempt_id=attempt_id, result=ContactResult.NOT_REACHED, commitment="Finalement non."
    )

    assert again.commitment == "Je rappelle jeudi."
    assert again.result is ContactResult.REACHED


# --- Ce que le typage rend impossible ----------------------------------------------------


def test_there_is_nowhere_to_write_something_about_a_member():
    """L'invariant central : **aucune colonne de texte libre attachée à une personne**.

    La note vit sur `watch_contact_attempts`, clé sur `signal_id` + `by_account_id` : elle décrit
    un geste posé par quelqu'un. Si un jour une colonne de note apparaît sur `watch_signals` ou sur
    un modèle porté par `subject_id`, c'est la fiche qui revient — et ce test tombe."""
    suspicious = ("note", "comment", "observation", "remark", "assessment", "diagnosis")
    person_keyed = (
        models.SignalModel,
        models.CareMemoryModel,
        models.CoverageGapModel,
        models.ReferentHistoryModel,
        models.ScheduledCheckModel,
    )

    for model in person_keyed:
        columns = set(model.__table__.columns.keys())
        assert not any(
            word in column for column in columns for word in suspicious
        ), f"{model.__tablename__} porte un champ de note libre sur une personne"

    # Et la note existe bien là où elle doit être : sur l'acte.
    assert "commitment" in models.ContactAttemptModel.__table__.columns
    assert "by_account_id" in models.ContactAttemptModel.__table__.columns


def test_the_word_used_by_the_field_names_the_gesture_not_the_person():
    """`commitment` — pas `note`, pas `observation`.

    Le nom d'un champ est la première documentation que lit celui qui l'utilisera dans deux ans.
    « Note » invite à écrire sur quelqu'un ; « engagement » dit ce qu'on attend."""
    columns = set(models.ContactAttemptModel.__table__.columns.keys())
    assert "commitment" in columns
    assert not columns & {"note", "observation", "assessment"}
