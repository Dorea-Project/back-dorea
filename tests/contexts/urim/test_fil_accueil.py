"""Le fil d'accueil — **ou en est chaque preparation, sans rejouer le moteur**.

Rejouer est le mode normal de lecture d'UNE preparation. Le faire pour vingt
lignes a l'ouverture de l'application ferait tourner vingt pipelines : ces tests
gardent la frontiere qui l'interdit, et le vocabulaire qui la traverse.

La regle qu'ils tiennent, et qui se perdrait au premier « ce serait mieux avec
la phrase » : **aucune phrase d'Urim ne sort d'ici**. Le `say` et le `why`
viennent du rejeu ; le fil dit ou l'on en est, l'ecran de la preparation dit ce
qu'Urim a dit.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.contexts.auth.interface.dependencies import get_current_actor
from app.contexts.urim.application.ports import PreparationRecord
from app.contexts.urim.interface.dependencies import (
    get_corpus_index,
    get_study_service,
)
from app.contexts.urim.interface.schemas import StudySummaryView
from app.main import create_app

AUTEUR = UUID("20aff920-5f30-530b-848a-b5483d9ce5d7")
UNITE = UUID("33333333-4444-5555-6666-777777777777")


class _Acteur:
    account_id = AUTEUR


class _Unite:
    id = UNITE
    label = "Hébreux 13:1-6"


class _Index:
    pericopes = (_Unite(),)


class _Service:
    """Une doublure qui note **ce qu'on lui demande**, et ne rejoue rien."""

    def __init__(self, records: list[PreparationRecord]) -> None:
        self._records = records
        self.appels: list[dict] = []

    async def list_mine(self, **kw) -> list[PreparationRecord]:
        self.appels.append(kw)
        return self._records


def _record(**kw) -> PreparationRecord:
    defauts = dict(
        id=uuid4(),
        church_id=None,
        author_id=AUTEUR,
        raw_input="l'amour fraternel n'existe plus dans l'église",
        status="ouverte",
    )
    return PreparationRecord(**{**defauts, **kw})


@pytest.fixture
async def client_et_service(request) -> AsyncGenerator[tuple[AsyncClient, _Service]]:
    records = getattr(request, "param", None) or [_record()]
    service = _Service(records)

    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: _Acteur()
    app.dependency_overrides[get_study_service] = lambda: service
    app.dependency_overrides[get_corpus_index] = lambda: _Index()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, service

    app.dependency_overrides.clear()


async def test_le_fil_rend_une_ligne_par_preparation(client_et_service):
    client, _ = client_et_service

    reponse = await client.get("/api/mobile/urim/studies")

    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


async def test_aucune_phrase_d_urim_ne_sort_du_fil(client_et_service):
    """La garde principale : servir `say`/`why` ici obligerait a rejouer."""
    client, _ = client_et_service

    ligne = (await client.get("/api/mobile/urim/studies")).json()[0]

    for interdit in ("say", "why", "ask", "rationale", "trace", "options", "blocks"):
        assert interdit not in ligne, f"« {interdit} » suppose un rejeu"


async def test_le_vocabulaire_du_moteur_traverse_intact(client_et_service):
    """`await_decision` **est** « rend la main ».

    Le traduire ici en un etat maison — « en attente », « a toi » — fabriquerait
    un second vocabulaire a tenir a jour a chaque etage nouveau.
    """
    client, _ = client_et_service

    ligne = (await client.get("/api/mobile/urim/studies")).json()
    assert "last_outcome" in ligne[0]

    vue = StudySummaryView.from_record(
        _record(last_outcome="await_decision", last_stage_code="weigh_conviction")
    )
    assert vue.last_outcome == "await_decision"
    assert vue.last_stage_code == "weigh_conviction"


async def test_une_preparation_sans_tour_rendu_ne_ment_pas(client_et_service):
    """Ouverte a l'instant, le moteur n'a encore rien dit : `null`, pas un etat."""
    client, _ = client_et_service

    ligne = (await client.get("/api/mobile/urim/studies")).json()[0]

    assert ligne["last_outcome"] is None
    assert ligne["last_turn_at"] is None
    # Le titre reste ce que le pasteur a ecrit : c'est tout ce qu'on a.
    assert ligne["raw_input"].startswith("l'amour fraternel")


async def test_l_unite_bornee_donne_son_etiquette(client_et_service):
    """Le fil nomme l'unite quand elle est bornee — sans faire tourner le moteur."""
    client, service = client_et_service
    service._records = [_record(pericope_id=UNITE)]

    ligne = (await client.get("/api/mobile/urim/studies")).json()[0]

    assert ligne["pericope_label"] == "Hébreux 13:1-6"


async def test_une_unite_inconnue_de_l_index_ne_casse_pas_la_ligne(client_et_service):
    """Un corpus qui change ne doit pas faire disparaitre une preparation."""
    client, service = client_et_service
    service._records = [_record(pericope_id=uuid4())]

    ligne = (await client.get("/api/mobile/urim/studies")).json()[0]

    assert ligne["pericope_label"] is None


async def test_la_date_du_culte_et_le_theme_voyagent(client_et_service):
    client, service = client_et_service
    service._records = [
        _record(
            theme="La communion comme pratique",
            service_date=date(2026, 8, 17),
            last_outcome="continue",
            last_turn_at=datetime(2026, 8, 16, 21, 14, tzinfo=UTC),
        )
    ]

    ligne = (await client.get("/api/mobile/urim/studies")).json()[0]

    assert ligne["theme"] == "La communion comme pratique"
    assert ligne["service_date"] == "2026-08-17"
    assert ligne["last_turn_at"].startswith("2026-08-16T21:14")


async def test_le_fil_est_celui_de_l_acteur(client_et_service):
    """Cle sur l'auteur, jamais sur l'eglise : l'antichambre et l'assemblee
    remplissent le meme fil, c'est un seul homme qui prepare."""
    client, service = client_et_service

    await client.get("/api/mobile/urim/studies")

    assert service.appels[0]["actor_account_id"] == AUTEUR
