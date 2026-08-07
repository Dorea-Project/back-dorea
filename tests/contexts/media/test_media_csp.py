"""DOREA-019 — un média servi en même origine ne doit pas pouvoir exécuter de script.

Le générateur de carte missionnaire (M9-1) produit des **SVG**, rangés par `MediaStore.put`
et servis par `StaticFiles` sous la même origine que l'application. Un SVG ouvert directement
dans un onglet s'exécute dans cette origine : c'est le vecteur d'un XSS stocké.

Le rendu échappe son texte aujourd'hui — donc rien n'est exploitable. Mais la sûreté ne peut
pas reposer sur le fait que chaque futur écrivain de SVG pense à échapper. La CSP, elle,
protège quoi qu'il arrive en aval.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as opened:
        yield opened


async def test_les_medias_portent_une_csp_qui_coupe_les_scripts(client: AsyncClient):
    """Peu importe que le fichier existe : l'en-tête doit être là sur le chemin média."""
    media_prefix = get_settings().media_base_url
    response = await client.get(f"{media_prefix}/inexistant.svg")

    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'none'" in csp, "un SVG pourrait charger et exécuter du script"
    assert "sandbox" in csp, "sans sandbox, le SVG reste dans l'origine de l'application"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"


async def test_l_api_n_est_pas_bridee_par_la_csp_des_medias(client: AsyncClient):
    """La CSP ne vise **que** le chemin média — une CSP `none` sur l'API casserait Swagger."""
    response = await client.get("/api/mobile/health")
    assert "Content-Security-Policy" not in response.headers


async def test_la_carte_missionnaire_echappe_son_texte():
    """La défense en profondeur ne dispense pas de la première ligne."""
    from app.contexts.mission.infrastructure.card_renderer import render_verse_card

    svg = render_verse_card(
        reference_label='<script>alert("ref")</script>',
        verse_text='</text><script>alert("verset")</script>',
    )
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
