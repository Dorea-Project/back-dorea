"""La surface Plateforme de la curation — **la frontière qui écrit de la doctrine**.

`test_curation.py` éprouve le service : ce qu'il refuse et pourquoi. Ici on garde ce que le
service ne peut pas voir, et qui est propre à cette frontière-là.

## Pourquoi celle-ci mérite ses propres tests

Aucune table `urim_corpus_*` ne porte de `church_id`. Curer ne change pas ce qu'une église
lit : ça change ce que **toutes** lisent, y compris celles qui n'ont jamais entendu parler du
relecteur. Le garde n'est donc pas prudentiel, il est structurel — et un garde structurel qui
ne serait vérifié nulle part est un garde qu'un jour on retire par mégarde.

Et c'est la seule surface qui écrive ce que le pasteur lira comme **relu**. Ce qui passe ici
devient de la doctrine affichée sous l'autorité de quelqu'un.

## Ce qu'on mesure

- **le jeton Plateforme** ferme chacune des sept routes, celles qui lisent comprises ;
- **l'en-tête du relecteur** ferme celles qui écrivent, et le nom qu'un corps de requête
  contiendrait encore ne signe rien — c'est le trou par lequel un verdict a été posé au nom du
  propriétaire du dépôt, et un trou refermé sans témoin se rouvre ;
- **un refus de curation revient en 422 avec son motif**, jamais en 500 — le message dit quoi
  faire, et un message vague transformerait un garde en obstacle, or un obstacle se contourne ;
- **la reprise de signature** (`PATCH`) répond, parce qu'elle est la sortie de `ia-mistral` et
  qu'une sortie non vérifiée est une porte condamnée.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.contexts.urim.application.curation import CoverageReport, PericopeSummary
from app.contexts.urim.application.relecture import Relecteur
from app.contexts.urim.domain.errors import CurationInvalideError
from app.contexts.urim.interface.dependencies import exiger_relecteur, get_curation
from app.core.config import get_settings
from app.main import create_app

UNITE = UUID("11111111-2222-3333-4444-555555555555")
BASE = "/api/backoffice/platform/urim"

#: Une unité complète, pour que le corps envoyé soit celui d'un vrai relecteur.
UNITE_VALIDE = {
    "book": "Ésaïe", "start_ch": 53, "start_v": 1, "end_ch": 53, "end_v": 12,
    "label": "Le Serviteur souffrant",
    "rationale": "L'unité tient du v. 1 au v. 12 — la vision et son interprétation.",
    "source_ref": "Découpage BHS usuel",
}


class _Curation:
    """Une doublure qui **accepte tout, ou refuse ce qu'on lui dit de refuser**.

    Le service décide *quoi* refuser — c'est `test_curation.py`. Ici on ne vérifie que le
    trajet du refus jusqu'au client."""

    def __init__(self, *, refus: str | None = None) -> None:
        self.refus = refus
        self.resignatures: list[tuple[UUID, str]] = []

    def _peut_ou_leve(self) -> None:
        if self.refus:
            raise CurationInvalideError(self.refus)

    async def create_pericope(self, draft):
        self._peut_ou_leve()
        return UNITE

    async def set_bearings(self, pericope_id, drafts, reviewed_by):
        self._peut_ou_leve()

    async def add_caveat(self, pericope_id, draft, reviewed_by):
        self._peut_ou_leve()
        return uuid4()

    async def add_context(self, pericope_id, draft, reviewed_by):
        self._peut_ou_leve()
        return uuid4()

    async def set_feasibility(self, pericope_id, drafts, reviewed_by):
        self._peut_ou_leve()

    async def resign_pericope(self, pericope_id, *, reviewed_by, label=None, rationale=None):
        self._peut_ou_leve()
        self.resignatures.append((pericope_id, reviewed_by))
        return True

    async def delete_pericope(self, pericope_id):
        return True

    async def list_pericopes(self, book=None):
        return [PericopeSummary(
            id=UNITE, book="Ésaïe", start_ch=53, start_v=1, end_ch=53, end_v=12,
            label="Le Serviteur souffrant", reviewed_by="ia-mistral",
            n_bearings=10, n_caveats=0, n_context=0, n_feasibility=18,
        )]

    async def coverage(self):
        return CoverageReport(
            verses_total=31170, verses_covered=31066, pericopes=4561,
            pericopes_completes=4553, par_locus={}, par_livre={},
        )


@pytest.fixture
def curation() -> _Curation:
    return _Curation()


def _jeton() -> dict[str, str]:
    return {"X-Service-Token": get_settings().backoffice_service_token}


#: Le relecteur que le registre rendrait. Il est **substitué** ici plutôt que saisi : c'est
#: exactement ce que la surface a cessé d'accepter dans un corps de requête.
RELECTEUR = Relecteur(identifiant="kouassi", nom="Kouassi Jean")


@pytest.fixture
async def client(curation: _Curation) -> AsyncGenerator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_curation] = lambda: curation
    app.dependency_overrides[exiger_relecteur] = lambda: RELECTEUR
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ouvert:
        yield ouvert
    app.dependency_overrides.clear()


# ==================================================== le jeton ferme la surface, entièrement


@pytest.mark.parametrize(
    ("methode", "chemin", "corps"),
    [
        ("get", "/coverage", None),
        ("get", "/pericopes", None),
        ("post", "/pericopes", UNITE_VALIDE),
        ("patch", f"/pericopes/{UNITE}", {"label": "Le Serviteur souffrant"}),
        ("delete", f"/pericopes/{UNITE}", None),
        ("put", f"/pericopes/{UNITE}/bearings", {"bearings": []}),
        ("post", f"/pericopes/{UNITE}/caveats", {}),
    ],
)
async def test_sans_jeton_plateforme_rien_ne_passe(client, methode, chemin, corps):
    """⚠️ **Le garde est structurel, pas prudentiel.**

    Aucune table `urim_corpus_*` ne porte de `church_id` : curer change ce que **toutes** les
    églises lisent. Les routes de lecture sont fermées elles aussi — la couverture dit l'état
    d'avancement d'un produit, pas une donnée publique.

    Vérifié sur les sept, et pas sur une : un garde posé route par route se perd à la
    huitième."""
    # `request` plutôt que `client.get(...)` : httpx refuse `json=` sur GET et DELETE, et on
    # veut la **même** invocation pour les sept — sinon le paramétrage ne prouve plus qu'elles
    # sont traitées pareil.
    reponse = await client.request(methode.upper(), f"{BASE}{chemin}", json=corps)

    assert reponse.status_code in (401, 403), f"{methode.upper()} {chemin} laisse passer"


# ============================================================ un refus arrive avec son motif


async def test_un_refus_de_curation_revient_en_422_avec_ce_qu_il_faut_faire(curation):
    """Le motif doit **traverser**. Un refus qui arrive en 500 fait croire à une panne, et un
    relecteur qui croit à une panne réessaie au lieu de corriger."""
    curation.refus = (
        "Signez d'un nom qui désigne quelqu'un. Ce champ dit au pasteur qui a pesé ce texte."
    )
    app = create_app()
    app.dependency_overrides[get_curation] = lambda: curation
    app.dependency_overrides[exiger_relecteur] = lambda: RELECTEUR
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ouvert:
        reponse = await ouvert.post(
            f"{BASE}/pericopes", json=UNITE_VALIDE, headers=_jeton()
        )

    assert reponse.status_code == 422
    corps = reponse.json()["error"]
    assert corps["code"] == "URI_CURATION_INVALID"
    assert "désigne quelqu'un" in corps["message"]


# ================================================ la sortie de `ia-mistral` est praticable


async def test_un_relecteur_peut_reprendre_une_unite_signee_par_le_modele(client, curation):
    """🔴 **La contrepartie de `ia-mistral`.**

    4 553 unités portent la signature du modèle. Sans cette route, un relecteur ne pourrait
    qu'effacer et retaper — en perdant au passage les pesées accrochées à l'unité. Une porte de
    sortie qu'aucun test n'emprunte est une porte condamnée."""
    reponse = await client.patch(
        f"{BASE}/pericopes/{UNITE}",
        json={"label": "Le Serviteur souffrant"},
        headers=_jeton(),
    )

    assert reponse.status_code == 204
    assert curation.resignatures == [(UNITE, "Kouassi Jean")]


async def test_le_nom_envoye_dans_le_corps_ne_signe_rien(client, curation):
    """🔴 **Le trou qu'on a éprouvé, refermé — et le témoin qui le prouve.**

    `verifier_verdict()` faisait déjà tout ce qu'un validateur peut faire sur une chaîne : il
    refuse le vide, `semis-demo`, `ia-mistral`. Il n'a jamais pu refuser le nom **de quelqu'un
    d'autre**, et un verdict d'essai a été posé au nom du propriétaire du dépôt.

    Le corps ci-dessous porte encore « Richmond » — c'est délibéré. La surface ne le refuse même
    pas : elle l'**ignore**, parce que le nom ne vient plus de là. Un refus laisserait croire que
    le champ compte encore."""
    reponse = await client.patch(
        f"{BASE}/pericopes/{UNITE}", json={"reviewed_by": "Richmond"}, headers=_jeton()
    )

    assert reponse.status_code == 204
    assert curation.resignatures == [(UNITE, "Kouassi Jean")]


async def test_ecrire_exige_un_relecteur_lire_non(curation):
    """Deux gardes, et ils ne disent pas la même chose : le jeton dit *« la Plateforme »*,
    l'en-tête dit *« qui »*. Lire l'état d'avancement ne demande pas de signataire ; écrire du
    corpus, si — c'est ce qui apparaîtra un jour sous les yeux d'un pasteur comme relu."""
    app = create_app()
    app.dependency_overrides[get_curation] = lambda: curation
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ouvert:
        ecriture = await ouvert.post(f"{BASE}/pericopes", json=UNITE_VALIDE, headers=_jeton())
        lecture = await ouvert.get(f"{BASE}/coverage", headers=_jeton())

    assert ecriture.status_code == 401
    assert ecriture.json()["error"]["code"] == "URI_REVIEWER_UNKNOWN"
    assert lecture.status_code == 200


# ===================================================================== la mesure, sans fard


async def test_la_couverture_dit_l_etat_reel(client):
    """C'est le seul chiffre qui empêche de se raconter que la curation avance."""
    reponse = await client.get(f"{BASE}/coverage", headers=_jeton())

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["verses_total"] == 31170
    assert 0.0 <= corps["part_couverte"] <= 1.0


async def test_une_unite_listee_dit_qui_l_a_signee(client):
    """Sans le signataire, un relecteur ne sait pas ce qui reste à relire — et `ia-mistral`
    se confondrait avec un nom."""
    corps = (await client.get(f"{BASE}/pericopes", headers=_jeton())).json()

    (unite,) = corps
    assert unite["reviewed_by"] == "ia-mistral"
