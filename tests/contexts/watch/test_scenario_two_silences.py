"""**Deux silences que le moteur confond** — Sondet, entouré ; Awa, seule.

Le scénario précédent montrait ce que le moteur ne voit pas du soin. Celui-ci montre ce qu'il ne
voit pas de la **solitude** — et les deux se rejoignent à la fin, de la pire des façons.

> Sondet manque trois rencontres de la cellule Bethel. Jean et Luc sont passés le voir : il est
> entouré, et son cas ne coûtera qu'un appel pour rien.
>
> Awa manque trois rencontres. Elle n'appartient à aucun groupe de suivi, personne n'est son
> référent, et personne ne passera. Son cas est le seul des deux qui compte vraiment.

Le moteur ouvre **deux cas identiques**. Puis le faux positif de Sondet remonte à la boucle froide
et finance une proposition qui, appliquée, aurait empêché le cas d'Awa de s'ouvrir.

---

Une précision sur le « taux de lien », parce qu'elle décide de ce qui est testable ici : un taux
par personne n'existe pas et ne doit pas exister — son complément est une carte d'isolement, et
son degré entrant un score de popularité. Ce que le moteur a le droit de savoir tient en deux
formes : un **booléen sur un cas déjà ouvert** (« ce cas a-t-il une route ? ») et un **compte
agrégé à l'église**, non nominatif. Le dernier test tient cette frontière.
"""

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contexts.attendance.application.return_detection import DetectReturn
from app.contexts.watch.application.fire_checks import FireDueChecks
from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpretation import InterpreterRegistry
from app.contexts.watch.application.interpreters.check_fired import CheckFiredV1
from app.contexts.watch.application.interpreters.presence_recorded import (
    ABSENCE_WATCH_KIND,
    PresenceRecordedV2,
)
from app.contexts.watch.application.owner_assignment import ResolveOwners
from app.contexts.watch.application.referent_resolution import ResolveSignalOwner
from app.contexts.watch.calibration.ports import AbsenceEvidence
from app.contexts.watch.calibration.simulator import Simulator
from app.contexts.watch.domain.effects import CasePriority, OpenCase
from app.contexts.watch.domain.facts import forbidden_reason
from app.contexts.watch.domain.parameters import DEFAULTS
from app.contexts.watch.domain.referent import Referent, ReferentOrigin
from app.contexts.watch.domain.registry import default_registry
from app.contexts.watch.domain.signal import SignalOutcome
from app.contexts.watch.infrastructure.neutralization_store import (
    AttendanceNeutralizationStore,
)
from tests.contexts.watch.fakes import (
    FakeAbsences,
    FakeChecks,
    FakeExclusions,
    FakeLedger,
    FakeSignals,
)

_NOW = datetime(2026, 8, 2, tzinfo=UTC)
_WEEK = timedelta(days=7)


# --- Le harnais ------------------------------------------------------------------------------


class _Params:
    def __init__(self, **overrides):
        self._values = {**DEFAULTS, **overrides}

    async def get_int(self, tenant_id, param):
        return self._values[param]


class _Rhythm:
    async def next_check_at(self, *, group_id, tenant_id, since):
        return since + _WEEK * 3 + timedelta(days=2)


class _Context:
    async def for_check(self, check):
        if check.kind != ABSENCE_WATCH_KIND:
            return {}
        return {"occurrences": 3, "threshold": 3, "group_label": "la cellule Bethel"}


class _Referents:
    """La cascade du référent, réduite à ce que l'histoire dit.

    Sondet a un responsable de cellule. Awa n'a rien : ni référent, ni groupe de suivi."""

    def __init__(self, *, referent_of):
        self._referent_of = referent_of

    async def execute(self, *, person_id, tenant_id, at):
        lead = self._referent_of.get(person_id)
        if lead is None:
            return None
        return Referent(person_id, lead, ReferentOrigin.GROUP_LEAD, at)

    async def primary_group(self, *, person_id, tenant_id):
        return None  # Awa n'appartient à aucun groupe qui porte la veille


class _People:
    """L'annuaire de l'église, réduit aux titres que la cascade interroge."""

    def __init__(self, *, pastor):
        self._pastor = pastor

    async def agenda_keeper(self, tenant_id):
        return None

    async def church_admin(self, tenant_id):
        return None

    async def pastor(self, tenant_id):
        return self._pastor

    async def tenant_owner(self, tenant_id):
        return self._pastor


class _Evidence:
    def __init__(self, rows):
        self._rows = rows

    async def absence_evidence(self, *, tenant_id, since):
        return list(self._rows)


def _engine(checks, *, signals):
    interpreters = InterpreterRegistry()
    interpreters.register(PresenceRecordedV2())
    interpreters.register(CheckFiredV1())
    return Intake(
        FakeLedger(),
        default_registry(),
        interpreters,
        AttendanceNeutralizationStore(FakeAbsences(), FakeExclusions()),
        signals,
        checks,
    )


async def _present(intake, *, tenant, member, group):
    await DetectReturn(intake, _Rhythm()).on_positive_presence(
        account_id=member, tenant_id=tenant, occurred_at=_NOW,
        gathering_id=uuid4(), recorded_at=_NOW, group_id=group,
    )


def _open_case(subject_id):
    return OpenCase(
        subject_id=subject_id,
        reason="Sans nouvelles — 3 rencontres de la cellule Bethel.",
        origin=CasePriority.ABSENCE,
        opened_at=_NOW,
    )


# --- Acte I : le moteur ouvre deux fois le même cas ------------------------------------------


async def test_the_engine_opens_two_cases_nothing_can_tell_apart():
    """Même groupe, même seuil, même échéance. Deux cas, et **pas un octet ne les sépare**.

    L'un coûtera un appel pour rien ; l'autre est la seule personne de l'église que personne
    n'attend. Sur l'écran du responsable, ce sont deux lignes jumelles — et comme leur origine et
    leur date d'ouverture sont identiques, **aucun tri ne fera jamais passer Awa devant**."""
    tenant, group = uuid4(), uuid4()
    sondet, awa = uuid4(), uuid4()
    checks, signals = FakeChecks(), FakeSignals()
    intake = _engine(checks, signals=signals)

    await _present(intake, tenant=tenant, member=sondet, group=group)
    await _present(intake, tenant=tenant, member=awa, group=group)
    due = checks.rows[0]["due_at"]
    await FireDueChecks(
        checks, intake, _Params(), _Context(), clock=lambda: due
    ).execute(tenant_id=tenant)

    cas_sondet, cas_awa = signals.rows
    assert {cas_sondet.subject_id, cas_awa.subject_id} == {sondet, awa}
    assert cas_sondet.reason == cas_awa.reason
    assert cas_sondet.origin is cas_awa.origin is CasePriority.ABSENCE
    assert cas_sondet.opened_at == cas_awa.opened_at  # toute clé de tri est une égalité


# --- Acte II : le moteur sait qu'Awa n'a personne, et il jette l'information ------------------


async def test_the_engine_computes_that_awa_has_no_one_and_then_drops_it():
    """La cascade **sait**. C'est l'étage suivant qui perd ce qu'elle a trouvé.

    `ResolveSignalOwner` renvoie pour Awa un destinataire *de repli* — le pasteur, faute de
    mieux — accompagné du motif : *« Cette personne n'appartient à aucun groupe de suivi. »* Sa
    propre docstring dit que ce motif est *« renvoyé pour être stocké avec le signal »*.

    Or `ResolveOwners` ne garde que l'identité, et `OpenCase` n'a **aucun champ** où ce motif
    pourrait aller. Le cas d'Awa arrive donc sur l'écran du pasteur exactement comme un cas
    correctement adressé à quelqu'un qui connaît la personne.

    Recevoir un cas parce qu'on est le bon et le recevoir parce que personne d'autre n'existe
    sont deux choses — et à partir d'ici, plus rien ne les distingue."""
    tenant, sondet, awa = uuid4(), uuid4(), uuid4()
    lead, pasteur = uuid4(), uuid4()
    owners = ResolveSignalOwner(
        _Referents(referent_of={sondet: lead}), _People(pastor=pasteur)
    )

    pour_sondet = await owners.execute(person_id=sondet, tenant_id=tenant, at=_NOW)
    pour_awa = await owners.execute(person_id=awa, tenant_id=tenant, at=_NOW)

    assert (pour_sondet.account_id, pour_sondet.is_escalated) == (lead, False)
    assert pour_awa.account_id == pasteur
    assert pour_awa.is_escalated is True
    assert pour_awa.escalation_reason == "Cette personne n'appartient à aucun groupe de suivi."

    kept, dropped = await ResolveOwners(owners, _People(pastor=pasteur)).execute(
        [_open_case(sondet), _open_case(awa)], tenant_id=tenant, at=_NOW
    )

    assert dropped == ()
    assert [effect.owner_account_id for effect in kept] == [lead, pasteur]
    # Et le motif n'a nulle part où aller : les deux ouvertures sont désormais jumelles.
    assert not any("escalation" in field.name for field in fields(OpenCase))


# --- Acte III : le soin invisible de Sondet finance ce qui coûtera Awa ------------------------


async def test_sondets_invisible_care_pays_for_the_proposal_that_would_lose_awa():
    """**Les deux scénarios se rejoignent ici, et c'est le cœur du chantier.**

    Le cas de Sondet se ferme sur « rien à signaler » — Jean et Luc étaient passés, mais le
    moteur n'en sait rien, alors il enregistre une erreur de détection. Le cas d'Awa se ferme sur
    une situation réelle qu'il a fallu porter.

    Le simulateur chiffre alors un seuil plus haut : *« 1 fermé sur "rien à signaler", mais 1 qui
    s'est confirmé. »* La phrase est honnête, et la question qu'elle pose au pasteur — *moins de
    bruit contre quelqu'un qu'on ne verra plus* — est posée sur une **prémisse fausse** : le
    « bruit » de Sondet n'était pas du bruit, c'était une visite que le journal n'a pas reçue.

    Un pasteur qui accepte cette proposition échange une visite qu'il ne voit pas contre une
    personne qu'il ne verra plus. **Quand le geste entrera au journal**, `spared_noise` tombera à
    zéro et la proposition n'aura plus rien à offrir en échange d'Awa."""
    evidence = _Evidence(
        [
            AbsenceEvidence(  # Sondet : entouré, et compté comme une fausse alerte
                occurrences=3, threshold=3,
                outcome=SignalOutcome.NOTHING_TO_REPORT.value,
            ),
            AbsenceEvidence(  # Awa : seule, et confirmée
                occurrences=3, threshold=3, outcome=SignalOutcome.FOLLOWED.value,
            ),
        ]
    )

    result = await Simulator(evidence).execute(
        tenant_id=uuid4(), candidate=4, since=_NOW
    )

    assert (result.opened_now, result.opened_then) == (2, 0)
    assert (result.spared_noise, result.missed_real) == (1, 1)
    assert "mais 1 qui se sont confirmés" in result.sentence


# --- Acte IV : la frontière du « taux de lien » ------------------------------------------------


def test_the_grid_catches_two_ways_of_naming_an_isolation_score_and_not_the_third():
    """Un **taux de lien par personne** est la carte d'isolement, et elle est interdite.

    Le grillage du contrat de fait en attrape déjà deux formulations : celle qui dit l'inaction
    (« jamais visité ») et celle qui dit le score. Il n'attrape **pas** la troisième — un taux
    nommé comme un taux passe.

    Ce test ne réclame pas d'élargir le grillage : il constate ce qu'on a et ce qu'on n'a pas.
    La protection du lien devra être écrite, elle n'est pas offerte par ce qui existe."""
    assert forbidden_reason("never_visited") == "inaction"
    assert forbidden_reason("isolation_score") == "inféré"

    assert forbidden_reason("link_rate") is None  # le trou, nommé
