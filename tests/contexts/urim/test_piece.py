"""Publier une pièce — **et ne jamais la publier deux fois**.

D70 a renversé le tronc de « prêcher » : l'audio retravaillé est le produit. Une pièce est
ce que le pasteur a écouté puis découpé, et c'est le seul objet de cette branche qui
traverse — la matière brute, elle, ne monte plus (D71).

Trois choses gouvernent ce fichier, et aucune ne se verrait casser :

- **republier est sans effet**, l'identifiant venant de l'appareil ;
- **les octets se rangent avant la ligne**, sinon le fil promet un son absent ;
- **rien n'expire**, contrairement à la capture dont la pièce est tirée.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.contexts.auth.interface.dependencies import get_current_actor
from app.contexts.urim.capture.piece import (
    AudioRefuseError,
    Piece,
    PieceInvalideError,
)
from app.contexts.urim.capture.piece_service import PieceService
from app.contexts.urim.interface.dependencies import get_piece_service
from app.main import create_app

LUNDI = datetime(2026, 8, 31, 21, 0, tzinfo=UTC)
VENDREDI = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)
EGLISE = uuid4()
PASTEUR = uuid4()
CULTE = uuid4()

#: Un WAV minimal — l'en-tête suffit : le contrôle de signature lit `RIFF` et `WAVE`.
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + bytes(36)


class _Acteur:
    account_id = PASTEUR


class _Pieces:
    """Un dépôt en mémoire, fidèle sur le seul point qui compte : `add` ne lève pas."""

    def __init__(self) -> None:
        self.rangees: dict[UUID, Piece] = {}
        self.appels_add = 0

    async def add(self, piece: Piece) -> Piece:
        self.appels_add += 1
        # Le contrat du port : sur un doublon, c'est la **première** ligne qui fait foi.
        if piece.id in self.rangees:
            return self.rangees[piece.id]
        self.rangees[piece.id] = piece
        return piece

    async def get(self, piece_id: UUID) -> Piece | None:
        return self.rangees.get(piece_id)

    async def pour_eglise(self, church_id: UUID, *, limite: int = 50):
        siennes = [p for p in self.rangees.values() if p.church_id == church_id]
        siennes.sort(key=lambda p: p.published_at, reverse=True)
        return tuple(siennes[:limite])


class _Media:
    def __init__(self, casse: bool = False) -> None:
        self.ecrits: list[bytes] = []
        self.casse = casse

    async def ranger(self, octets: bytes, *, content_type: str) -> str:
        if self.casse:
            raise OSError("stockage indisponible")
        self.ecrits.append(octets)
        return f"https://media.example/{len(self.ecrits)}.wav"


class _AccesOuvert:
    def __init__(self) -> None:
        self.demandes: list[tuple[UUID, UUID]] = []

    async def ensure_may_prepare(self, *, account_id, church_id):
        self.demandes.append((account_id, church_id))


def _service(*, pieces=None, media=None, acces=None) -> PieceService:
    return PieceService(
        pieces=pieces or _Pieces(),
        media=media or _Media(),
        access=acces or _AccesOuvert(),
        clock=lambda: VENDREDI,
    )


async def _publier(service, piece_id, *, titre="La prière", octets=WAV, **kw):
    return await service.publier(
        actor_account_id=PASTEUR,
        piece_id=piece_id,
        capture_id=CULTE,
        church_id=EGLISE,
        title=titre,
        start_ms=kw.pop("start_ms", 3_720_000),
        end_ms=kw.pop("end_ms", 5_400_000),
        cut_at=LUNDI,
        octets=octets,
        **kw,
    )


class TestPublier:
    async def test_la_piece_traverse_avec_ce_qui_la_decrit(self):
        pieces, media = _Pieces(), _Media()
        piece = await _publier(_service(pieces=pieces, media=media), uuid4())

        assert piece.title == "La prière"
        assert piece.capture_id == CULTE
        assert piece.author_id == PASTEUR
        assert piece.media_url.startswith("https://media.example/")
        assert media.ecrits == [WAV]

    async def test_les_deux_dates_disent_des_choses_differentes(self):
        # Il coupe le lundi soir, hors ligne ; il publie le vendredi. Confondre les deux
        # ferait mentir la chronologie que l'assemblée lit.
        piece = await _publier(_service(), uuid4())

        assert piece.cut_at == LUNDI
        assert piece.published_at == VENDREDI

    async def test_la_duree_se_calcule_sur_les_bornes(self):
        piece = await _publier(_service(), uuid4())

        assert piece.duree_ms == 5_400_000 - 3_720_000

    async def test_l_acces_est_verifie_avant_tout(self):
        acces = _AccesOuvert()
        await _publier(_service(acces=acces), uuid4())

        assert acces.demandes == [(PASTEUR, EGLISE)]


class TestRepublier:
    async def test_republier_rend_la_piece_deja_rangee(self):
        # 🔴 **Le cas ordinaire, pas l'incident.** L'identifiant vient de l'appareil (D64) :
        # un pasteur qui appuie deux fois dans un tunnel, ou dont la réponse s'est perdue,
        # renvoie la même pièce. Lever lui ferait croire à un échec — et son assemblée
        # finirait par recevoir la même prière trois fois.
        pieces = _Pieces()
        service = _service(pieces=pieces)
        piece_id = uuid4()

        premiere = await _publier(service, piece_id)
        seconde = await _publier(service, piece_id, titre="Un autre nom")

        assert seconde == premiere
        assert len(pieces.rangees) == 1

    async def test_republier_ne_reecrit_pas_les_octets(self):
        # ⚠️ Quatre-vingt-six mégaoctets sur la connexion d'une église. L'idempotence se
        # vérifie **avant** de toucher au magasin, pas après.
        media = _Media()
        service = _service(pieces=_Pieces(), media=media)
        piece_id = uuid4()

        await _publier(service, piece_id)
        await _publier(service, piece_id)

        assert len(media.ecrits) == 1

    async def test_la_date_de_publication_ne_derive_pas(self):
        # C'est la première qui fait foi : l'assemblée lit une chronologie.
        pieces = _Pieces()
        service = _service(pieces=pieces)
        piece_id = uuid4()

        premiere = await _publier(service, piece_id)
        seconde = await _publier(service, piece_id)

        assert seconde.published_at == premiere.published_at


class TestCeQuiEstRefuse:
    async def test_un_titre_vide_est_refuse_avec_une_phrase(self):
        # La base le tient déjà (`piece_titre_non_vide`) ; le refus existe pour que le
        # pasteur lise pourquoi, au lieu d'une violation de contrainte remontée telle quelle.
        with pytest.raises(PieceInvalideError):
            await _publier(_service(), uuid4(), titre="   ")

    async def test_des_bornes_croisees_sont_refusees(self):
        with pytest.raises(PieceInvalideError):
            await _publier(_service(), uuid4(), start_ms=5_000, end_ms=5_000)

    async def test_un_fichier_qui_n_est_pas_du_wav_est_refuse(self):
        # DOREA-024 — ce que le fichier **est**, pas ce qu'il prétend être. Un PNG rangé
        # sous une extension audio serait servi comme tel à une assemblée.
        with pytest.raises(AudioRefuseError):
            await _publier(_service(), uuid4(), octets=b"\x89PNG\r\n\x1a\n" + bytes(40))

    async def test_un_corps_vide_est_refuse(self):
        with pytest.raises(AudioRefuseError):
            await _publier(_service(), uuid4(), octets=b"")

    async def test_rien_n_est_range_quand_le_contenu_est_refuse(self):
        # 🔴 La ligne ne doit pas exister si les octets n'ont pas été acceptés : une pièce
        # visible dans le fil qui ne se joue pas est pire qu'une pièce absente.
        pieces, media = _Pieces(), _Media()

        with pytest.raises(AudioRefuseError):
            await _publier(
                _service(pieces=pieces, media=media), uuid4(), octets=b"pas du wav"
            )

        assert pieces.rangees == {}
        assert media.ecrits == []


class TestLOrdreDesEcritures:
    async def test_un_magasin_qui_casse_ne_range_aucune_ligne(self):
        # 🔴 **La garde la plus coûteuse à rater.** Une ligne dont le `media_url` pointe
        # vers un objet absent est une pièce que l'assemblée voit dans son fil et ne peut
        # pas jouer — pire qu'une pièce manquante, parce qu'elle promet.
        pieces = _Pieces()

        with pytest.raises(OSError):
            await _publier(_service(pieces=pieces, media=_Media(casse=True)), uuid4())

        assert pieces.rangees == {}


class TestLeFilDeLAssemblee:
    async def test_la_plus_recente_vient_en_tete(self):
        pieces = _Pieces()
        service = _service(pieces=pieces)

        await _publier(service, uuid4(), titre="Prédication")
        # Une seconde publication, plus tard.
        service_tardif = PieceService(
            pieces=pieces,
            media=_Media(),
            access=_AccesOuvert(),
            clock=lambda: datetime(2026, 9, 5, 18, 0, tzinfo=UTC),
        )
        await _publier(service_tardif, uuid4(), titre="Prière")

        fil = await service.pour_eglise(actor_account_id=PASTEUR, church_id=EGLISE)

        assert [p.title for p in fil] == ["Prière", "Prédication"]

    async def test_le_fil_d_une_autre_assemblee_ne_s_y_mele_pas(self):
        pieces = _Pieces()
        service = _service(pieces=pieces)

        await _publier(service, uuid4())

        fil = await service.pour_eglise(actor_account_id=PASTEUR, church_id=uuid4())

        assert fil == ()


@pytest.fixture
async def client_et_pieces() -> AsyncGenerator[tuple[AsyncClient, _Pieces]]:
    pieces = _Pieces()
    service = _service(pieces=pieces)

    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: _Acteur()
    app.dependency_overrides[get_piece_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, pieces

    app.dependency_overrides.clear()


class TestLaRoute:
    async def test_le_corps_brut_arrive_au_service(self, client_et_pieces):
        # ⚠️ **Pas de multipart, et c'est délibéré** : le corps brut avec des paramètres en
        # requête est la forme que la route des fragments emploie déjà. Ajouter
        # `python-multipart` pour porter un titre de deux mots aurait été une dépendance
        # contre une chaîne de caractères.
        client, pieces = client_et_pieces
        piece_id = uuid4()

        reponse = await client.post(
            f"/api/mobile/urim/pieces/{piece_id}",
            content=WAV,
            headers={"Content-Type": "audio/wav"},
            params={
                "capture_id": str(CULTE),
                "church_id": str(EGLISE),
                "title": "La prière du matin",
                "start_ms": 0,
                "end_ms": 1_800_000,
                "cut_at": LUNDI.isoformat(),
            },
        )

        assert reponse.status_code == 201, reponse.text
        assert pieces.rangees[piece_id].title == "La prière du matin"

    async def test_l_accuse_porte_l_url_et_la_duree(self, client_et_pieces):
        client, _ = client_et_pieces

        corps = (
            await client.post(
                f"/api/mobile/urim/pieces/{uuid4()}",
                content=WAV,
                params={
                    "capture_id": str(CULTE),
                    "church_id": str(EGLISE),
                    "title": "Prédication",
                    "start_ms": 0,
                    "end_ms": 3_600_000,
                    "cut_at": LUNDI.isoformat(),
                },
            )
        ).json()

        assert corps["media_url"].startswith("https://media.example/")
        assert corps["duration_ms"] == 3_600_000
        assert corps["title"] == "Prédication"

    async def test_un_titre_accentue_traverse_intact(self, client_et_pieces):
        # Le titre passe en paramètre de requête : s'il s'abîmait, le pasteur retrouverait
        # « La priere » là où il avait écrit « La prière ».
        client, pieces = client_et_pieces
        piece_id = uuid4()

        await client.post(
            f"/api/mobile/urim/pieces/{piece_id}",
            content=WAV,
            params={
                "capture_id": str(CULTE),
                "church_id": str(EGLISE),
                "title": "Prière pour les malades — Église d'Abidjan",
                "start_ms": 0,
                "end_ms": 1000,
                "cut_at": LUNDI.isoformat(),
            },
        )

        assert (
            pieces.rangees[piece_id].title
            == "Prière pour les malades — Église d'Abidjan"
        )

    async def test_le_fil_se_lit(self, client_et_pieces):
        client, _ = client_et_pieces

        await client.post(
            f"/api/mobile/urim/pieces/{uuid4()}",
            content=WAV,
            params={
                "capture_id": str(CULTE),
                "church_id": str(EGLISE),
                "title": "Prière",
                "start_ms": 0,
                "end_ms": 1000,
                "cut_at": LUNDI.isoformat(),
            },
        )

        corps = (
            await client.get(
                "/api/mobile/urim/pieces", params={"church_id": str(EGLISE)}
            )
        ).json()

        assert [p["title"] for p in corps] == ["Prière"]
