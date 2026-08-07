"""**Le scénario de Sondet** — le soin que le moteur ne sait pas voir.

Une seule histoire, jouée d'un bout à l'autre contre le moteur **tel qu'il est aujourd'hui** :

> Sondet vient à la cellule Bethel. Puis il tombe malade. Jean l'apprend — ils sont proches.
> Jean et Luc vont le saluer. Personne d'autre ne le sait ; la veille non plus. Pendant ce
> temps, le responsable est en voyage et personne ne le sait non plus.

Ce module ne teste pas une fonction : il **mesure une histoire**. C'est le harnais qui a manqué
pour répondre autrement qu'à l'argument à la question *« combien ça change ? »*.

---

Trois moitiés — le compte est faux, et c'est le signe que le fichier a servi :

- **Ce qui est juste** — le moteur fait exactement ce qu'on lui a demandé. Ces assertions sont là
  pour toujours.
- **Ce qui a basculé** — G-1 (la porte du geste) et G-1b (la lecture avant l'appel) ont retourné
  trois assertions le 05/08/2026. Elles gardent le récit de ce qu'elles disaient avant : un test
  qui ne dit plus d'où il vient est un test qu'on supprimera au prochain refactor.
- **Ce qui est encore faux** — le moteur fait ce qu'on lui a demandé, et le résultat est faux quand
  même, parce qu'une porte manque. Ces assertions **figent un défaut** pour qu'on puisse le
  renverser : chacune porte la phrase qui dit ce qu'elle deviendra.

Un défaut qu'aucun test ne tient est une conversation, et les conversations ne survivent pas à la
pression de livrer.
"""

import inspect
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.attendance.application.return_detection import DetectReturn
from app.contexts.watch.application.concern_watchdog import (
    EscalateStaleConcerns,
    WatchForUnopenedCases,
)
from app.contexts.watch.application.fire_checks import FireDueChecks
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.check_fired import CheckFiredV1
from app.contexts.watch.application.interpreters.gesture_done import GestureDoneV1
from app.contexts.watch.application.interpreters.presence_recorded import (
    ABSENCE_WATCH_KIND,
    PresenceRecordedV2,
)
from app.contexts.watch.application.interpreters.self_declaration import DeclarationKind
from app.contexts.watch.application.ports import GestureSeen
from app.contexts.watch.application.restitution import GetCaseContext
from app.contexts.watch.calibration.judge import IGNORED_AFTER_DAYS, OutcomeJudge
from app.contexts.watch.calibration.ports import AbsenceEvidence
from app.contexts.watch.calibration.simulator import Simulator
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import CasePriority, CoverageGap
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.gesture import GestureKind
from app.contexts.watch.domain.parameters import DEFAULTS, WatchParam
from app.contexts.watch.domain.registry import COMPANION, WATCH_UI, default_registry
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeChecks,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
    case_acts_for,
)

_NOW = datetime(2026, 8, 2, tzinfo=UTC)  # un dimanche, après la date d'effet de la V2
_WEEK = timedelta(days=7)


# --- Le harnais de l'histoire ---------------------------------------------------------------


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


class _Rhythm:
    """La cellule Bethel se réunit chaque semaine ; on regarde à la 3ᵉ manquée, plus la marge."""

    async def next_check_at(self, *, group_id, tenant_id, since):
        return since + _WEEK * 3 + timedelta(days=2)


class _Context:
    """Ce que la Présence répond au moment du tir : les rencontres réellement tenues."""

    def __init__(self, *, occurrences=3):
        self._occurrences = occurrences

    async def for_check(self, check):
        if check.kind != ABSENCE_WATCH_KIND:
            return {}
        return {
            "occurrences": self._occurrences,
            "threshold": 3,
            "group_label": "la cellule Bethel",
        }


class _Gaps:
    """Le magasin des défauts de couverture, avec sa déduplication."""

    def __init__(self):
        self.rows: list[CoverageGapRecord] = []

    async def record_once(self, record):
        already = any(
            r.tenant_id == record.tenant_id
            and r.gap is record.gap
            and r.subject_id == record.subject_id
            and r.resolved_at is None
            for r in self.rows
        )
        if already:
            return False
        self.rows.append(record)
        return True

    async def open_gaps(self, tenant_id):
        return [r for r in self.rows if r.tenant_id == tenant_id]


class _Evidence:
    """Ce que le journal garde d'un cas d'absence : les rencontres et le seuil du jour."""

    def __init__(self, rows):
        self._rows = rows

    async def absence_evidence(self, *, tenant_id, since):
        return list(self._rows)


class _NoAttempts:
    """Aucun contact tenté : ce que le responsable lit ici vient d'ailleurs."""

    async def recent_for(self, *, signal_id, limit=3):
        return []


class _LedgerGestures:
    """La lecture des gestes, sur le **vrai** journal du scénario — mêmes bornes que le SQL."""

    def __init__(self, ledger):
        self._ledger = ledger

    async def gestures_between(self, *, subject_id, tenant_id, since, until, limit=3):
        found = [
            GestureSeen(
                kind=f.payload["kind"],
                occurred_at=f.occurred_at,
                # L'auteur vit dans la preuve de consentement, comme dans le SQL.
                by_account_id=f.consent.given_by if f.consent else None,
            )
            for f in self._ledger.rows
            if f.kind is FactKind.GESTURE_DONE
            and f.subject_id == subject_id
            and f.tenant_id == tenant_id
            and since <= f.occurred_at < until
        ]
        found.sort(key=lambda g: g.occurred_at, reverse=True)
        return found[:limit]


class _Everyone:
    """L'annuaire, réduit à l'éligibilité — `absent` a quitté l'église."""

    def __init__(self, *, absent=None):
        self._absent = absent

    async def is_eligible(self, account_id, tenant_id):
        return account_id != self._absent


def _engine(checks, *, signals, ledger):
    interpreters = InterpreterRegistry()
    interpreters.register(PresenceRecordedV2())
    interpreters.register(CheckFiredV1())
    return Intake(
        ledger,
        default_registry(),
        interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals,
        checks,
    )


def _gesture_engine(church):
    """La même église, vue par la porte du geste — une seconde entrée sur les mêmes dépôts."""
    interpreters = InterpreterRegistry()
    interpreters.register(GestureDoneV1())
    return Intake(
        church.ledger,
        default_registry(),
        interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        church.signals,
        church.checks,
    )


async def _present(intake, *, tenant, member, group, at):
    await DetectReturn(intake, _Rhythm()).on_positive_presence(
        account_id=member, tenant_id=tenant, occurred_at=at,
        gathering_id=uuid4(), recorded_at=at, group_id=group,
    )


async def _fire(checks, intake, *, tenant, at, occurrences=3):
    return await FireDueChecks(
        checks, intake, _Params(), _Context(occurrences=occurrences), clock=lambda: at
    ).execute(tenant_id=tenant)


class _Church:
    """L'église du scénario, réduite à ce que l'histoire touche."""

    def __init__(self):
        self.tenant, self.group = uuid4(), uuid4()
        self.sondet, self.jean, self.luc = uuid4(), uuid4(), uuid4()
        self.responsable = uuid4()
        self.ledger, self.signals, self.checks = FakeLedger(), FakeSignals(), FakeChecks()
        self.intake = _engine(self.checks, signals=self.signals, ledger=self.ledger)


async def _visited_then_opened():
    """Jean passe pendant l'absence, puis l'échéance tombe. La scène de Sondet, en trois lignes."""
    church = _Church()
    intake = _gesture_engine(church)
    await _present(
        church.intake,
        tenant=church.tenant, member=church.sondet, group=church.group, at=_NOW,
    )
    due = church.checks.rows[0]["due_at"]
    await intake.submit(_visit_fact(church, at=_NOW + _WEEK))
    await _fire(church.checks, church.intake, tenant=church.tenant, at=due)
    (case,) = church.signals.rows
    case.owner_account_id = church.responsable
    return church, case, due


async def _context_of(church, case, due, *, people=None):
    return await GetCaseContext(
        church.signals,
        _NoAttempts(),
        _LedgerGestures(church.ledger),
        people or _Everyone(),
        clock=lambda: due,
    ).execute(
        signal_id=case.id, tenant_id=church.tenant, actor_account_id=church.responsable
    )


def _visit_fact(church, *, at):
    """La visite de Jean, telle que le compagnon l'émet."""
    return Fact(
        fact_id=uuid4(), tenant_id=church.tenant, occurred_at=at, recorded_at=at,
        source=COMPANION, kind=FactKind.GESTURE_DONE,
        subject_kind=SubjectKind.PERSON, subject_id=church.sondet,
        payload={"kind": GestureKind.VISIT.value},
        consent=ConsentProof(
            given_by=church.jean, scope=ConsentScope.SPEAK_FOR_ANOTHER, given_at=at
        ),
    )


async def _play_until_the_case_opens(church):
    """Les trois premiers actes, joués tels quels — ils servent à plusieurs tests."""
    await _present(
        church.intake,
        tenant=church.tenant, member=church.sondet, group=church.group, at=_NOW,
    )
    due = church.checks.rows[0]["due_at"]
    # Ici Sondet tombe malade. Jean l'apprend, Jean et Luc vont le voir. **Rien n'entre.**
    await _fire(church.checks, church.intake, tenant=church.tenant, at=due)
    return due


# --- Acte I : les portes qui n'existent pas -------------------------------------------------


def test_the_visit_finally_has_a_door_and_only_the_companion_holds_it():
    """**Basculé le 05/08/2026 — c'était l'assertion d'acceptation de G-1.**

    `GESTURE_DONE` portait son nom depuis l'écriture du contrat — *« visite, appel abouti, aide
    déclarée »* — et aucune source enregistrée ne pouvait l'émettre. Ce test disait ce vide ; il
    dit maintenant la porte.

    Elle s'ouvre sur le compagnon seulement : c'est le membre qui pose le geste. L'écran du
    responsable a déjà `CASE_ACTIONS` pour dire ce qu'il fait de son travail."""
    registry = default_registry()

    assert registry.accepts(COMPANION, FactKind.GESTURE_DONE)
    assert not registry.accepts(WATCH_UI, FactKind.GESTURE_DONE)


def test_nobody_can_say_he_is_travelling():
    """Le responsable part en voyage, et le moteur n'a **aucun mot** pour l'entendre.

    `SELF_DECLARATION` sait écouter « priez pour moi », « appelez-moi », « voilà mon rythme ».
    Pas « je m'absente ». Son silence sera donc lu comme le silence de n'importe qui."""
    for existing in ("prayer", "contact_request", "rhythm", "capsule_accepted"):
        assert DeclarationKind(existing)  # ces gestes-là ont une porte

    with pytest.raises(ValueError):
        DeclarationKind("away")


# --- Acte II : ce qui est juste, et qui le restera ------------------------------------------


async def test_a_presence_arms_the_watch_and_the_deadline_opens_sondets_case():
    """Sondet était là ; trois rencontres plus tard, plus personne ne l'a vu. Le cas s'ouvre.

    C'est le moteur qui fonctionne exactement comme promis : aucun fait n'a jamais dit un
    silence, c'est une **échéance posée sur une parole** qui est tombée."""
    church = _Church()

    due = await _play_until_the_case_opens(church)

    assert due == _NOW + _WEEK * 3 + timedelta(days=2)
    (case,) = church.signals.rows
    assert case.subject_id == church.sondet
    assert case.origin is CasePriority.ABSENCE
    assert case.reason == "Sans nouvelles — 3 rencontres de la cellule Bethel."


async def test_the_ledger_holds_the_presence_and_nothing_of_the_two_men_who_went():
    """**Le test central de tout ce chantier.**

    Deux hommes ont pris soin de Sondet. Le journal, lui, ne contient que la présence de Sondet
    et le tir de l'échéance. Ni Jean ni Luc n'y apparaissent — non pas parce qu'ils ont omis de
    le dire, mais parce qu'il n'y a **rien à quoi le dire**.

    Le soin le plus réel de l'histoire est le seul que le moteur ne peut pas recevoir."""
    church = _Church()

    await _play_until_the_case_opens(church)

    kinds = [fact.kind for fact in church.ledger.rows]
    assert kinds == [FactKind.PRESENCE_RECORDED, FactKind.CHECK_FIRED]
    assert not any(
        fact.subject_id in (church.jean, church.luc) for fact in church.ledger.rows
    )


# --- Acte III : ce qui est faux, et qu'on fige pour pouvoir le renverser ---------------------


async def test_the_care_of_the_church_is_recorded_as_a_detection_error():
    """Le responsable appelle Sondet. *« Merci, Jean et Luc sont passés dimanche. »* Il ferme
    sur « rien à signaler » — la seule issue honnête dont il dispose.

    Et la vérité terrain enregistre un **faux positif** sur l'origine `ABSENCE` : pour le moteur,
    la détection s'est trompée. Elle ne s'était pas trompée : elle était en retard sur deux
    hommes qui y étaient déjà allés.

    **Quand le geste entrera au journal**, ce cas ne s'ouvrira pas — ou s'ouvrira en sachant
    qu'un humain avait vu avant lui. Cette assertion devra s'inverser."""
    church = _Church()
    due = await _play_until_the_case_opens(church)
    (case,) = church.signals.rows
    acts = case_acts_for(church.signals, clock=lambda: due + timedelta(days=1))
    await acts.seen(
        case=case, tenant_id=church.tenant, actor_account_id=church.responsable
    )
    await acts.closed(
        case=case, tenant_id=church.tenant, actor_account_id=church.responsable,
        outcome=SignalOutcome.NOTHING_TO_REPORT,
    )

    truth = await OutcomeJudge(
        church.signals, _Params(), clock=lambda: due + timedelta(days=2)
    ).execute(tenant_id=church.tenant)

    verdict = truth.verdict_for(CasePriority.ABSENCE)
    assert (verdict.closed, verdict.confirmed, verdict.false_positives) == (1, 0, 1)
    assert verdict.precision == 0.0  # le soin de l'église, compté comme une erreur
    # Et l'autre moitié de l'inversion : deux hommes ont vu avant le moteur, il n'en sait rien.
    assert truth.missed_detections == 0


async def test_the_cold_loop_then_offers_to_watch_less_and_it_looks_free():
    """La suite mécanique du test précédent, et la vraie gravité de l'affaire.

    Le simulateur lit ce faux positif et chiffre : à un seuil plus haut, ce cas ne se serait pas
    ouvert, et **aucun cas confirmé n'aurait été manqué**. La proposition qui remonte au pasteur
    est donc *« moins de bruit, sans coût »* — alors que le coût était déjà payé par Jean et Luc,
    hors du système.

    Autrement dit : **plus une église se soigne elle-même, plus le moteur conclut qu'il regarde
    trop.** Il désapprend dans les communautés qui vont bien.

    **Quand le geste entrera au journal**, `spared_noise` deviendra `missed_real` : la même
    ligne, lue comme « tu étais trop lent » au lieu de « tu criais »."""
    church = _Church()
    evidence = _Evidence(
        [
            AbsenceEvidence(
                occurrences=3,
                threshold=3,
                outcome=SignalOutcome.NOTHING_TO_REPORT.value,
            )
        ]
    )

    result = await Simulator(evidence).execute(
        tenant_id=church.tenant, candidate=4, since=_NOW
    )

    assert (result.opened_now, result.opened_then) == (1, 0)
    assert (result.spared_noise, result.missed_real) == (1, 0)
    assert "aucun cas confirmé" in result.sentence  # la proposition a l'air gratuite


async def test_with_the_door_open_the_same_week_stops_being_a_detection_error():
    """**Ce que G-1 livre, mesuré contre le test précédent.**

    Même semaine, même cas, même responsable — sauf que Jean déclare sa visite pendant que le cas
    est vivant. Le responsable lit alors *« Quelqu'un de l'église lui a rendu visite le … »* avant
    de décrocher, et il ferme sur *« on sait, quelqu'un s'en occupe déjà »* : une issue qui existait
    depuis le premier jour et que rien ne lui permettait de choisir en connaissance de cause.

    La précision de l'origine `ABSENCE` passe de **0.0 à 1.0** sur le même événement humain. Rien
    n'a changé dans l'église ; le moteur a simplement cessé de compter son soin comme une erreur.
    """
    church = _Church()
    due = await _play_until_the_case_opens(church)
    intake = _gesture_engine(church)

    await intake.submit(_visit_fact(church, at=due + timedelta(days=1)))

    (case,) = church.signals.rows
    assert case.gestures_count == 1
    assert any("rendu visite" in note for note in case.annotations)

    acts = case_acts_for(church.signals, clock=lambda: due + timedelta(days=2))
    await acts.closed(
        case=case, tenant_id=church.tenant, actor_account_id=church.responsable,
        outcome=SignalOutcome.KNOWN_AND_FOLLOWED,
    )
    truth = await OutcomeJudge(
        church.signals, _Params(), clock=lambda: due + timedelta(days=3)
    ).execute(tenant_id=church.tenant)

    verdict = truth.verdict_for(CasePriority.ABSENCE)
    assert (verdict.closed, verdict.confirmed, verdict.false_positives) == (1, 1, 0)
    assert verdict.precision == 1.0


async def test_a_visit_paid_before_the_case_opens_never_touches_the_decision():
    """**La scène de Sondet elle-même** — et la moitié de la réponse qui ne doit pas bouger.

    Jean passe *pendant* l'absence, donc avant que l'échéance ne tombe. À cet instant il n'y a
    aucun cas à enrichir, et l'interpreter ne doit surtout rien ouvrir : déclarer une visite ne
    peut pas ficher quelqu'un.

    Et quand l'échéance tombe, le cas s'ouvre **quand même**. C'est la règle, pas une lacune : une
    visite n'est pas une présence, et laisser la parole d'un tiers atténuer une détection lui
    donnerait le pouvoir de faire taire un cas. Le journal garde le geste ; la décision l'ignore.
    """
    church = _Church()
    intake = _gesture_engine(church)
    await _present(
        church.intake,
        tenant=church.tenant, member=church.sondet, group=church.group, at=_NOW,
    )
    due = church.checks.rows[0]["due_at"]

    await intake.submit(_visit_fact(church, at=_NOW + _WEEK))
    assert church.signals.rows == []  # une visite n'ouvre rien, et c'est la règle

    await _fire(church.checks, church.intake, tenant=church.tenant, at=due)

    (case,) = church.signals.rows
    assert case.annotations == []  # la décision n'a rien appris, et ne doit rien apprendre
    assert FactKind.GESTURE_DONE in [f.kind for f in church.ledger.rows]  # le journal, lui, sait


async def test_but_the_leader_reads_the_visit_before_he_picks_up_the_phone():
    """**Basculé le 05/08/2026 — l'assertion d'acceptation de G-1b.**

    Le cas s'ouvre toujours. Il ne s'ouvre plus **muet** : juste avant de composer le numéro, le
    responsable lit *« Quelqu'un de l'église lui a rendu visite le 9 août. »*, datée, avec sa
    source dépliable.

    La réparation est entièrement en lecture — aucun effet, aucune projection nouvelle, aucune
    migration, et le chemin déterministe n'est pas touché. C'est ce que la règle imposait : le
    geste informe, il ne décide pas."""
    church, case, due = await _visited_then_opened()

    context = await _context_of(church, case, due)

    (gesture,) = [s for s in context.segments if s.kind == "gesture"]
    assert gesture.text.startswith("Quelqu'un de l'église lui a rendu visite le 9 août.")
    assert gesture.source == "watch_facts.gesture_done"


async def test_the_leader_is_told_he_can_ask_jean_rather_than_disturb_sondet():
    """**G-4 — le lien fraternel, et toute la règle tient dans la phrase qu'il produit.**

    Le bloc ne dit pas au responsable ce que Jean sait de Sondet. Il lui dit qu'il **peut le lui
    demander**, et lui donne l'identifiant de Jean pour le joindre.

    *Le lien porte une question, jamais une information.* L'information remonte **par** l'humain,
    jamais autour de lui — et Sondet ne reçoit pas un appel de plus pour dire ce que Jean sait
    déjà. C'est aussi pourquoi l'annotation stockée sur le cas, elle, reste anonyme : elle voyage
    et elle persiste, là où ce bloc-ci est calculé pour un seul lecteur, sur un seul cas."""
    church, case, due = await _visited_then_opened()

    context = await _context_of(church, case, due)

    (gesture,) = [s for s in context.segments if s.kind == "gesture"]
    assert gesture.text.endswith("Vous pouvez lui demander de ses nouvelles.")
    assert gesture.account_id == church.jean
    # Et la projection, elle, ne nomme toujours personne.
    assert str(church.jean) not in " ".join(case.annotations)


async def test_nobody_is_offered_as_a_link_once_they_have_left_the_church():
    """Proposer d'appeler quelqu'un qui n'est plus là est pire que ne rien proposer.

    Le **geste reste affiché** — il a eu lieu, et il explique toujours le silence. C'est le lien
    qui disparaît : la phrase perd son invitation et l'identifiant tombe."""
    church, case, due = await _visited_then_opened()

    context = await _context_of(church, case, due, people=_Everyone(absent=church.jean))

    (gesture,) = [s for s in context.segments if s.kind == "gesture"]
    assert gesture.account_id is None
    assert "demander" not in gesture.text


def test_there_is_no_way_to_enumerate_who_is_linked_to_whom():
    """**Le garde qui empêche le sociogramme**, tenu structurellement et pas par une intention.

    Une carte des affinités dans une église fuite les clans, les histoires et les conflits — c'est
    le jour où le produit meurt. La protection n'est donc pas « on n'écrira pas cet écran » : c'est
    qu'aucune lecture de lien ne peut porter sur plus d'une personne à la fois.

    **Deux bornes sont admises, et l'asymétrie est le fond du sujet.**

    - `subject_id` — *ce qu'on a fait pour cette personne*. Sert au responsable, sur un cas ouvert.
    - `actor_account_id` — *ce que cette personne a fait*. Ses propres actes lui appartiennent,
      c'est la règle positive de la transparence, et c'est ce qui fait tenir le react fraternel.

    La borne qui **n'existe pas** est la troisième : *« qui a cité Jean »*, le degré entrant. Elle
    serait un score de popularité, son complément serait la carte d'isolement, et elle apprendrait
    à Jean qu'Anna l'a nommé — alors que le lien déclaré ne prévient jamais celui qu'il désigne.
    Le jour où une méthode l'accepte, ce test tombe."""
    from app.contexts.watch.application.ports import DeclaredLinkReader, GestureReader

    bornes = {"subject_id", "actor_account_id"}
    for port in (GestureReader, DeclaredLinkReader):
        lectures = [
            name
            for name in dir(port)
            if not name.startswith("_") and callable(getattr(port, name))
        ]
        assert lectures, f"{port.__name__} a perdu ses lectures — le garde ne garde plus rien"
        for name in lectures:
            params = set(inspect.signature(getattr(port, name)).parameters)
            assert params & bornes, (
                f"« {port.__name__}.{name} » lit du lien sans borner à une personne : "
                "c'est la première brique d'un graphe énumérable."
            )
            assert "linked_account_id" not in params, (
                f"« {port.__name__}.{name} » cherche par la personne **nommée** : c'est le "
                "degré entrant, donc un score de popularité et une carte d'isolement."
            )


async def test_and_the_engine_finally_learns_it_was_late_instead_of_wrong():
    """**Basculé le 05/08/2026 — la boucle du geste se referme ici.**

    La scène entière, jouée jusqu'au verdict. Jean passe voir Sondet pendant l'absence ; le cas
    s'ouvre quand même trois semaines plus tard ; le responsable lit la visite, appelle, et
    constate qu'il y avait bien quelque chose — il ferme sur une issue confirmée.

    Le juge lit alors *« un humain a vu avant le moteur »* : **`missed_detections` passe à 1**, et
    le verdict est « seuil trop lent » au lieu de « seuil trop sensible ».

    C'est l'inversion complète du signal d'apprentissage décrite au début de ce fichier. Le même
    événement humain — deux frères qui vont saluer un malade — était lu comme la preuve que le
    moteur criait trop ; il est lu maintenant comme la preuve qu'il était en retard."""
    church = _Church()
    intake = _gesture_engine(church)
    await _present(
        church.intake,
        tenant=church.tenant, member=church.sondet, group=church.group, at=_NOW,
    )
    due = church.checks.rows[0]["due_at"]
    await intake.submit(_visit_fact(church, at=_NOW + _WEEK))
    await _fire(church.checks, church.intake, tenant=church.tenant, at=due)
    (case,) = church.signals.rows

    acts = case_acts_for(church.signals, clock=lambda: due + timedelta(days=1))
    await acts.closed(
        case=case, tenant_id=church.tenant, actor_account_id=church.responsable,
        outcome=SignalOutcome.FOLLOWED,
    )
    # La doublure lit les gestes là où le SQL les lit : au journal.
    church.signals.gestures = [
        (f.subject_id, f.occurred_at)
        for f in church.ledger.rows
        if f.kind is FactKind.GESTURE_DONE
    ]

    truth = await OutcomeJudge(
        church.signals, _Params(), clock=lambda: due + timedelta(days=2)
    ).execute(tenant_id=church.tenant)

    assert truth.missed_detections == 1
    assert truth.verdict_for(CasePriority.ABSENCE).false_positives == 0


async def test_a_leader_nobody_knows_is_away_is_still_told_he_is_probably_overloaded():
    """**Le cas qui reste faux — et il n'est plus celui qu'on croyait.**

    Depuis G-3, un responsable qui a **déclaré** son voyage n'est plus soupçonné : `LEADER_AWAY`
    porte sa charge et appelle une relève. Ce test décrit ce qu'il en reste — celui dont *personne
    ne sait* qu'il est parti, parce qu'il n'a rien déclaré.

    Pour lui, le moteur n'a toujours que le mot « débordé », et il a toujours tort. Il n'y a pas de
    réparation technique à ça : le silence de quelqu'un qui n'a rien dit ne se devine pas, et le
    deviner serait exactement la surveillance que le produit s'interdit. Ce qui reste possible,
    c'est de rendre la déclaration facile — c'est un problème d'écran, pas de moteur."""
    church, gaps = _Church(), _Gaps()
    for _ in range(DEFAULTS[WatchParam.UNOPENED_VOLUME_FLOOR]):
        church.signals.rows.append(
            Signal(
                id=uuid4(), tenant_id=church.tenant, subject_id=uuid4(),
                origin=CasePriority.ABSENCE, reason="Sans nouvelles.",
                opened_at=_NOW - timedelta(days=IGNORED_AFTER_DAYS + 1),
                status=SignalStatus.ASSIGNED, owner_account_id=church.responsable,
                first_seen_at=None,  # jamais ouvert : il est dans un avion
            )
        )

    flagged = await WatchForUnopenedCases(
        church.signals, gaps, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=church.tenant)

    assert flagged == [church.responsable]
    (gap,) = gaps.rows
    assert gap.gap is CoverageGap.CASES_NOT_OPENED
    assert "A probablement besoin d'aide." in gap.reason


async def test_the_one_door_jean_has_leads_to_a_dead_end_when_nobody_knows_sondet():
    """Et si Jean utilisait la seule porte qu'on lui offre — *« je m'inquiète pour Sondet »* ?

    Si personne n'est le référent de Sondet, le cas n'a pas de propriétaire. Et l'escalade passe
    son chemin : sans propriétaire, il n'y a pas d'engagement à ne pas tenir. Le raisonnement est
    juste ; l'effet est que **la personne que personne ne connaît produit le cas qui remonte le
    moins**.

    Le contraste est dans le test : le même cas, avec un référent, remonte au pasteur.

    **Quand les liens existeront**, l'orphelin cessera d'être un cul-de-sac : le cas gagnera un
    nom à qui poser la question — sans que personne hérite d'une charge qu'il n'a pas acceptée."""
    church, gaps = _Church(), _Gaps()
    vieux = _NOW - timedelta(days=DEFAULTS[WatchParam.CONCERN_ESCALATION_DAYS] + 1)
    for owner in (None, church.responsable):
        church.signals.rows.append(
            Signal(
                id=uuid4(), tenant_id=church.tenant, subject_id=uuid4(),
                origin=CasePriority.CONCERN, reason="Quelqu'un pense à elle.",
                opened_at=vieux,
                status=SignalStatus.OPEN if owner is None else SignalStatus.ASSIGNED,
                owner_account_id=owner,
            )
        )

    escalated = await EscalateStaleConcerns(
        church.signals, gaps, _Params(), clock=lambda: _NOW
    ).execute(tenant_id=church.tenant)

    assert escalated == [church.responsable]  # celui qu'on connaît remonte
    assert len(gaps.rows) == 1  # l'orphelin, lui, ne remonte nulle part
