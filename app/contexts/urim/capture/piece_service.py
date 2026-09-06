"""Publier une pièce — **le seul objet de « prêcher » qui traverse**.

D70 a renversé le tronc : l'audio retravaillé est le produit. Ce service tient le geste par
lequel une pièce quitte le téléphone du pasteur pour atteindre son assemblée.

## Ce qui traverse, et ce qui ne traverse pas

⛔ **La matière brute ne monte plus** (D71). Les cent quatre-vingts fragments d'un culte
restent sur l'appareil et y meurent au septième jour. Ce qui part, c'est ce que le pasteur
a **écouté puis découpé** — et ce geste est le consentement.

Conséquence directe : la pièce est **le premier objet de ce culte que le serveur voit**. Sa
capture d'origine n'existe très probablement pas en base, et rien ici ne la cherche.

## Les deux ordres qui comptent

**On range les octets avant d'écrire la ligne.** Une ligne dont le `media_url` pointe vers
un objet absent est une pièce que l'assemblée voit dans son fil et ne peut pas jouer —
pire qu'une pièce manquante, parce qu'elle promet.

**On écrit la ligne une seule fois, quoi qu'il arrive.** L'identifiant vient de l'appareil
(D64) ; republier rend la pièce déjà rangée au lieu d'en créer une seconde.

⚠️ **Le prix de cet ordre est un objet orphelin possible** : si l'écriture de la ligne
échoue après le rangement des octets, ceux-ci restent dans le magasin sans que rien ne les
désigne. C'est le bon sens du compromis — un fichier perdu coûte du stockage, une ligne
menteuse coûte la confiance.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.contexts.urim.application.ports import PreacherAuthorization
from app.contexts.urim.capture.piece import (
    AudioRefuseError,
    Piece,
    PieceAudioStore,
    PieceRepository,
)

#: Le seul format qu'une pièce prend aujourd'hui — le même PCM que la capture, avec son
#: en-tête WAV devant. ⚠️ **Rien n'est ré-encodé** : c'est assumé, et ça se paie en poids.
TYPE_AUDIO = "audio/wav"

#: Une heure et demie de PCM 16 kHz mono pèse cent soixante-treize mégaoctets. La borne est
#: donc large — mais elle existe, parce qu'une route sans borne est une route qu'on peut
#: remplir. Deux cent cinquante mégaoctets laissent passer un culte entier publié d'un bloc.
POIDS_MAXIMUM = 250 * 1024 * 1024


def _verifier_audio(octets: bytes, content_type: str) -> None:
    """Ce que le fichier **est**, pas ce qu'il prétend être.

    🔴 **La signature compte autant que le type déclaré.** Le `Content-Type` vient du client :
    il dit ce qu'il veut. Un PNG rangé sous une extension audio serait servi tel quel à une
    assemblée, et ne se jouerait jamais — un fil qui promet un son absent.

    Le WAV est un conteneur RIFF : `RIFF` en tête, `WAVE` en position 8. Deux comparaisons,
    et elles suffisent à écarter tout ce qui n'est pas ce format."""
    if content_type != TYPE_AUDIO:
        raise AudioRefuseError(
            "Une pièce se publie en WAV — le format que l'appareil produit.",
            details={"content_type": content_type, "attendu": TYPE_AUDIO},
        )
    if not octets:
        raise AudioRefuseError("Cette pièce est vide : il n'y a rien à publier.")
    if len(octets) > POIDS_MAXIMUM:
        raise AudioRefuseError(
            "Cette pièce dépasse ce qu'une publication accepte.",
            details={"octets": len(octets), "maximum": POIDS_MAXIMUM},
        )
    if not (octets.startswith(b"RIFF") and octets[8:12] == b"WAVE"):
        raise AudioRefuseError(
            "Ce fichier n'est pas l'audio qu'il annonce, et il ne se jouerait pas."
        )


class PieceService:
    """Le geste de publier, et rien d'autre."""

    def __init__(
        self,
        *,
        pieces: PieceRepository,
        media: PieceAudioStore,
        access: PreacherAuthorization,
        clock: Callable[[], datetime],
    ) -> None:
        self._pieces = pieces
        self._media = media
        self._access = access
        self._clock = clock

    async def publier(
        self,
        *,
        actor_account_id: UUID,
        piece_id: UUID,
        capture_id: UUID,
        church_id: UUID,
        title: str,
        start_ms: int,
        end_ms: int,
        cut_at: datetime,
        octets: bytes,
        content_type: str = TYPE_AUDIO,
    ) -> Piece:
        """Publie la pièce. Rend celle qui fait foi — la neuve, ou celle déjà rangée.

        🔴 **L'idempotence est vérifiée avant de toucher au magasin.** Republier ne doit pas
        écrire une seconde copie de quatre-vingt-six mégaoctets pour la jeter ensuite : le
        pasteur est sur une connexion d'église, et l'octet coûte.
        """
        await self._access.ensure_may_prepare(
            account_id=actor_account_id, church_id=church_id
        )

        deja = await self._pieces.get(piece_id)
        if deja is not None:
            return deja

        _verifier_audio(octets, content_type)

        url = await self._media.ranger(octets, content_type=content_type)

        return await self._pieces.add(
            Piece.publier(
                id=piece_id,
                capture_id=capture_id,
                church_id=church_id,
                author_id=actor_account_id,
                title=title,
                start_ms=start_ms,
                end_ms=end_ms,
                media_url=url,
                cut_at=cut_at,
                at=self._clock(),
            )
        )

    async def pour_eglise(
        self, *, actor_account_id: UUID, church_id: UUID, limite: int = 50
    ) -> tuple[Piece, ...]:
        """Le fil d'une assemblée — ce qu'elle a reçu, du plus récent au plus ancien."""
        await self._access.ensure_may_prepare(
            account_id=actor_account_id, church_id=church_id
        )
        return await self._pieces.pour_eglise(church_id, limite=limite)
