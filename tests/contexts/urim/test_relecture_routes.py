"""La surface du relecteur — **l'écran par lequel la dette diminue, ou ne diminue pas**.

`test_relecture.py` éprouve le service : ce qu'il refuse, ce qu'il périme, ce qu'il compte. Ici
on ne garde que ce qui appartient à la frontière, et qui ne se voit nulle part ailleurs.

## Pourquoi cette frontière mérite ses propres tests

Tout l'outillage de relecture existait et fonctionnait — cinq détecteurs, une file ordonnée, un
registre de verdicts, une commande pour trancher — et le compteur affichait **0 unité relue sur
4 561**. Ce n'était pas un défaut d'outillage : le relecteur est un théologien, et
`--ref "Apocalypse 5:5-14" --portee D4` ne sera jamais tapé par la personne dont on a besoin.
Ces routes sont le seul endroit où ce constat se répare, et une surface qu'aucun test
n'emprunte est une surface dont on découvrira l'inconfort trop tard.

## Ce qu'on mesure

- **le nom du signataire ne vient pas du corps** — c'est le trou par lequel un verdict a été
  posé au nom du propriétaire du dépôt ;
- **écrire exige un signataire, lire non** : le jeton dit *« la Plateforme »*, l'en-tête dit
  *« qui »* ;
- **le dossier montre la signature du modèle**, parce que rien de généré ne doit se confondre
  avec une relecture ;
- **le compteur passe entier**, y compris la date du balayage : une file dont on ne sait pas
  l'âge ment.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.contexts.urim.application.relecture import (
    Compteur,
    Dossier,
    LigneCuration,
    Relecteur,
    Signalement,
    UniteSignalee,
    VerdictPose,
    Verset,
)
from app.contexts.urim.interface.dependencies import exiger_relecteur, get_relecture
from app.core.config import get_settings
from app.main import create_app

BASE = "/api/backoffice/platform/urim/relecture"
UNITE = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_NOW = datetime(2026, 8, 13, tzinfo=UTC)
RELECTEUR = Relecteur(identifiant="kouassi", nom="Kouassi Jean")

_EMPREINTE = "f" * 32


def _unite() -> UniteSignalee:
    return UniteSignalee(
        id=UNITE, reference="Apocalypse 5:5-14", libelle="Le Lion et l'Agneau",
        signature="ia-mistral", empreinte_courante=_EMPREINTE,
        signalements=[Signalement(
            detecteur="D4", libelle="D4 aberration", gravite=2,
            detail="8 loci portants sur 10", corps="", empreinte_balayage=_EMPREINTE,
        )],
        verdicts=[],
    )


class _Relecture:
    """Une doublure qui rend une unité et **retient ce qu'on lui fait signer**."""

    def __init__(self) -> None:
        self.poses: list[tuple[str, str]] = []

    async def file(self, *, limite=20, decalage=0):
        return [_unite()]

    async def dossier(self, pericope_id):
        return Dossier(
            unite=_unite(),
            versets=[Verset(chapitre=5, verset=5, texte="Ne pleure point ; voici, le lion…")],
            lignes=[
                LigneCuration(
                    couche="pesée", axe="christologie", force="dominant",
                    corps="le Lion est l'Agneau immolé", source="lecture suivie",
                    signee_par="ia-mistral",
                ),
                LigneCuration(
                    couche="mise en garde", axe="christologie", force=None,
                    corps="le passage ne décrit pas le mécanisme de l'expiation",
                    source="Beale", signee_par="Kouassi Jean",
                ),
            ],
        )

    async def poser(self, pericope_id, *, portee, verdict, note, relecteur):
        self.poses.append((portee, relecteur.nom))
        return VerdictPose(
            portee=portee, verdict=verdict, note=note, relu_par=relecteur.nom,
            relu_le=_NOW, empreinte_jugee=_EMPREINTE,
        )

    async def retirer(self, pericope_id, portee):
        return "Richmond"

    async def compteur(self):
        return Compteur(
            unites=4561, unites_signalees=140, unites_relues=0,
            signalements=312, signalements_tranches=0,
            lignes=45557, lignes_humaines=0, derniere_analyse=_NOW,
        )


@pytest.fixture
def relecture() -> _Relecture:
    return _Relecture()


def _jeton() -> dict[str, str]:
    return {"X-Service-Token": get_settings().backoffice_service_token}


@pytest.fixture
async def client(relecture: _Relecture) -> AsyncGenerator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_relecture] = lambda: relecture
    app.dependency_overrides[exiger_relecteur] = lambda: RELECTEUR
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ouvert:
        yield ouvert
    app.dependency_overrides.clear()


# ================================================================ le nom n'est pas une entrée


async def test_le_nom_du_signataire_ne_vient_pas_du_corps(client, relecture):
    """🔴 **Le trou éprouvé, refermé.**

    Le corps porte « Richmond » — délibérément. La surface ne le refuse pas : elle l'ignore,
    parce que le nom vient du registre. Un refus laisserait croire que le champ compte encore,
    et un champ qui compte à moitié est un champ qui comptera de nouveau."""
    reponse = await client.post(
        f"{BASE}/unites/{UNITE}/verdict",
        json={"portee": "D4", "verdict": "accepte", "reviewed_by": "Richmond"},
        headers=_jeton(),
    )

    assert reponse.status_code == 201
    assert reponse.json()["relu_par"] == "Kouassi Jean"
    assert relecture.poses == [("D4", "Kouassi Jean")]


async def test_signer_exige_un_relecteur_descendre_la_file_non(relecture):
    """Deux gardes qui ne disent pas la même chose. Lire la file n'affirme rien ; signer
    fabrique ce qu'un pasteur lira comme relu."""
    app = create_app()
    app.dependency_overrides[get_relecture] = lambda: relecture
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ouvert:
        signature = await ouvert.post(
            f"{BASE}/unites/{UNITE}/verdict",
            json={"portee": "D4", "verdict": "accepte"}, headers=_jeton(),
        )
        lecture = await ouvert.get(f"{BASE}/file", headers=_jeton())

    assert signature.status_code == 401
    assert signature.json()["error"]["code"] == "URI_REVIEWER_UNKNOWN"
    assert lecture.status_code == 200


@pytest.mark.parametrize(
    ("methode", "chemin", "corps"),
    [
        ("get", "/file", None),
        ("get", "/compteur", None),
        ("get", f"/unites/{UNITE}", None),
        ("post", f"/unites/{UNITE}/verdict", {"portee": "D4", "verdict": "accepte"}),
        ("delete", f"/unites/{UNITE}/verdict/D4", None),
    ],
)
async def test_sans_jeton_plateforme_rien_ne_passe(client, methode, chemin, corps):
    """Le corpus est global : relire change ce que **toutes** les églises liront. Le garde est
    structurel, et il vaut aussi sur les routes qui ne font que lire — la file dit l'état
    d'avancement d'un produit, pas une donnée publique."""
    reponse = await client.request(methode.upper(), f"{BASE}{chemin}", json=corps)

    assert reponse.status_code in (401, 403), f"{methode.upper()} {chemin} laisse passer"


# ============================================================ ce que le relecteur a sous les yeux


async def test_le_dossier_sert_le_passage_avant_la_curation(client):
    """Juger une pesée sans lire le passage qu'elle pèse n'est pas une relecture, c'est une
    signature. Et la signature du modèle s'affiche sur chaque ligne."""
    corps = (await client.get(f"{BASE}/unites/{UNITE}", headers=_jeton())).json()

    assert corps["versets"][0]["texte"].startswith("Ne pleure point")
    assert corps["lignes_generees"] == 1
    assert [ligne["generee"] for ligne in corps["lignes"]] == [True, False]
    assert corps["unite"]["signature"] == "ia-mistral"


async def test_la_file_dit_ce_qu_on_reproche_et_a_quel_point(client):
    """L'ordre est la gravité que les détecteurs ont posée, rien d'autre : **ils signalent, ils
    ne jugent pas**."""
    (entree,) = (await client.get(f"{BASE}/file", headers=_jeton())).json()

    assert entree["reference"] == "Apocalypse 5:5-14"
    assert entree["poids"] == 2
    assert entree["signalements"][0]["detecteur"] == "D4"
    assert entree["relue_en_entier"] is False


async def test_le_compteur_dit_le_retard_sans_le_maquiller(client):
    """« 0 unité relue en entier par un humain » est la première ligne du rapport, et la seule
    mesure qui dise de combien la promesse est en retard sur le fait. La surface l'alimente ;
    elle ne la contourne pas."""
    corps = (await client.get(f"{BASE}/compteur", headers=_jeton())).json()

    assert (corps["unites"], corps["unites_relues"]) == (4561, 0)
    assert (corps["lignes"], corps["lignes_humaines"]) == (45557, 0)
    assert corps["part_relue"] == 0.0
    #: ⚠️ Sans elle, une file calculée il y a trois mois se lirait comme l'état du jour.
    assert corps["derniere_analyse"] is not None


async def test_retirer_un_verdict_dit_qui_l_avait_signe(client):
    """Un retrait silencieux effacerait la seule chose qu'on voudra savoir ensuite : au nom de
    qui le verdict avait été posé."""
    reponse = await client.delete(f"{BASE}/unites/{UNITE}/verdict/D4", headers=_jeton())

    assert reponse.status_code == 200
    assert reponse.json()["etait_signe_par"] == "Richmond"


async def test_un_verdict_hors_liste_est_refuse_a_la_frontiere(client):
    """Les trois verdicts sont clos en base (`review_verdict_clos`) ; la frontière rend le refus
    lisible avant que la contrainte ne le rende brutal."""
    reponse = await client.post(
        f"{BASE}/unites/{uuid4()}/verdict",
        json={"portee": "D4", "verdict": "excellent"}, headers=_jeton(),
    )

    assert reponse.status_code == 422
