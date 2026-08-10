"""Les routes mobile d'Urim — **ce que le contrat HTTP promet au client Flutter**.

Le service est éprouvé ailleurs (`test_study_service.py`). Ici on ne mesure qu'une chose :
*ce qui sort du tuyau est-il ce que le mobile attend ?* Les défauts qu'on garde sont ceux
d'une frontière, et ils ne se voient jamais dans le service :

- **une ambiguïté revient en 200**, jamais en 4xx — c'est la raison d'être du champ `outcome`,
  et la transformer en erreur ferait disparaître exactement ce que le produit veut montrer ;
- **`origin` voyage avec chaque option**, sinon le client devine la provenance en lisant la
  forme du motif, ce qui marche jusqu'au jour où non ;
- **aucun champ n'est absent** : les listes sont vides, les scalaires `null`. Un client qui
  doit tester la présence d'une clé a déjà perdu ;
- **le code d'option est un aller-retour** : ce que la réponse propose, la décision l'accepte.
  C'est le contrat que le 422 au clic avait rompu, et il ne se vérifie qu'ici.

Le service est substitué par une doublure : ces tests gardent la **frontière**, pas le moteur.
Un test de route qui traverse tout le pipeline mesure trop de choses à la fois et n'indique
plus où la panne se trouve.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.contexts.auth.interface.dependencies import get_current_actor
from app.contexts.urim.application.ports import (
    ElementRecord,
    PreparationRecord,
    StudyDTO,
    VerseServed,
)
from app.contexts.urim.interface.dependencies import get_study_service
from app.main import create_app

EGLISE = UUID("9a522e8f-17e3-5e74-a661-0c57cb7b73d6")
AUTEUR = UUID("20aff920-5f30-530b-848a-b5483d9ce5d7")
ETUDE = UUID("11111111-2222-3333-4444-555555555555")


class _Acteur:
    account_id = AUTEUR


def _dto(**kw) -> StudyDTO:
    """La réponse d'un moteur qui **rend la main** — le cas ordinaire, pas l'exception."""
    record = PreparationRecord(
        id=ETUDE, church_id=EGLISE, author_id=AUTEUR,
        raw_input="je veux prêcher sur la fraternité",
    )
    defauts = dict(
        record=record,
        outcome="await_decision",
        rationale="Laquelle prêchez-vous ?",
        trace=(("route_entry", "Lu comme une intention."),),
        options=(
            ("axe:christologie", "Christologie", "Disponible.", "locus"),
            ("Hébreux 13:1-2", "Hébreux 13:1-2", "Traite ce sujet.", "sens"),
        ),
        verses=(VerseServed("Hébreux 13:1", "Persévérez dans l'amour fraternel."),),
        elements=(ElementRecord("introduction", 0, None),),
        entry_mode="conviction",
    )
    return StudyDTO(**{**defauts, **kw})


class _Service:
    """Une doublure qui **note ce qu'on lui demande** — c'est le contrat qu'on éprouve."""

    def __init__(self) -> None:
        self.decisions: list[tuple[str, str]] = []
        self.explorations: list[str] = []

    async def open(self, **kw) -> StudyDTO:
        return _dto()

    async def get(self, **kw) -> StudyDTO:
        return _dto()

    async def decide(self, *, stage_code: str, option_code: str, **kw) -> StudyDTO:
        self.decisions.append((stage_code, option_code))
        return _dto(outcome="continue", options=())

    async def set_elements(self, **kw) -> StudyDTO:
        return _dto()

    async def explorer(self, *, reference: str, **kw):
        self.explorations.append(reference)
        raise NotImplementedError


@pytest.fixture
def service() -> _Service:
    return _Service()


@pytest.fixture
async def client(service: _Service) -> AsyncGenerator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: _Acteur()
    app.dependency_overrides[get_study_service] = lambda: service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ouvert:
        yield ouvert
    app.dependency_overrides.clear()


def _url(suffixe: str = "") -> str:
    return f"/api/mobile/urim/tenants/{EGLISE}/studies{suffixe}"


# ============================================================ une ambiguïté revient en 200


async def test_une_ambiguite_est_une_issue_du_moteur_pas_une_erreur_http(client):
    """⚠️ **`await_decision` est un succès.**

    Une résolution qui hésite, un bornage contesté, un couple impossible ne sont pas des
    erreurs HTTP : ce sont des issues, rendues avec leurs options et leur motif. Les
    transformer en 4xx ferait disparaître ce que le produit existe pour montrer."""
    reponse = await client.post(_url(), json={"raw_input": "la fraternité"})

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["outcome"] == "await_decision"
    assert corps["options"], "une main rendue sans option est une impasse"


# ================================================================== la provenance des options


async def test_chaque_option_dit_d_ou_elle_vient(client):
    """🔴 « Jean 5:42 partage 1 des mots rares » et « Parabole du bon Samaritain » arrivaient
    dans la même liste avec la même apparence. L'une est trouvée sur des mots, l'autre sur le
    sens ; le client doit pouvoir les séparer sans deviner."""
    corps = (await client.post(_url(), json={"raw_input": "la fraternité"})).json()

    origines = {option["origin"] for option in corps["options"]}
    assert origines == {"locus", "sens"}
    assert all(option["code"] and option["label"] for option in corps["options"])


# =========================================================== le contrat du code d'option


async def test_le_code_propose_est_celui_que_la_decision_accepte(client, service):
    """🔴 **Le 422 au clic.**

    L'étage proposait « Hébreux 13:1-2 » et le service refusait ce code. La réponse était
    juste ; c'est l'aller-retour qui était rompu, et il ne se vérifie qu'ici — ni le moteur ni
    le service ne voient les deux bouts."""
    corps = (await client.post(_url(), json={"raw_input": "la fraternité"})).json()
    propose = next(o for o in corps["options"] if o["origin"] == "sens")

    reponse = await client.post(
        f"/api/mobile/urim/studies/{ETUDE}/decisions",
        json={"stage_code": "weigh_conviction", "option_code": propose["code"]},
    )

    assert reponse.status_code == 200
    assert service.decisions == [("weigh_conviction", propose["code"])]


# ================================================================ la forme, entière et stable


async def test_aucun_champ_n_est_absent_meme_quand_tout_est_vide(client):
    """Les listes sont vides, les scalaires `null` — jamais de clé manquante.

    Un client qui doit tester la présence d'une clé avant de la lire a déjà perdu : la forme
    de la réponse ne doit pas dépendre de ce que le moteur a trouvé."""
    corps = (await client.post(_url(), json={"raw_input": "la fraternité"})).json()

    attendus = {
        "id", "status", "entry_mode", "raw_input", "outcome", "rationale", "trace",
        "options", "resolved", "pericope_id", "pericope_label", "curation_reviewed_by",
        "bounds_overridden", "version_id", "axis_code", "plan_source", "subject_matter",
        "theme", "elements", "verses", "variants", "bearings", "caveats", "context",
        "couples", "resisting_elsewhere", "corpus_snapshot", "corpus_drifted",
    }
    assert attendus <= set(corps), f"manquants : {sorted(attendus - set(corps))}"
    assert corps["variants"] == [] and corps["bearings"] == []
    assert corps["resolved"] is None and corps["pericope_id"] is None


async def test_la_saisie_vide_est_refusee_a_la_frontiere(client):
    """Le seul 4xx légitime sur cette route : une saisie que le moteur n'aura jamais à lire."""
    reponse = await client.post(_url(), json={"raw_input": ""})

    assert reponse.status_code == 422


async def test_le_texte_servi_remonte_au_pasteur(client):
    """`serve_corpus` annonçait « texte servi » et la réponse ne portait qu'un identifiant de
    version. Le pasteur recevait une référence et un UUID à la place de son verset."""
    corps = (await client.post(_url(), json={"raw_input": "la fraternité"})).json()

    (verset,) = corps["verses"]
    assert verset["reference"] == "Hébreux 13:1"
    assert "amour fraternel" in verset["text"]
