"""Le magasin des pièces publiées — **l'adaptateur, et le seul endroit qui traverse**.

Urim n'importe rien hors de lui-même : c'est le verrou d'architecture du contexte, et
`adapters/` en est l'exception assumée. Le port `PieceAudioStore` vit dans `capture/piece.py`
et ne connaît que deux choses — des octets, et l'URL qu'on rend. Voici ce qui le branche.

## Pourquoi le `MediaStore` et pas le magasin des fragments

Les deux savent ranger des octets. L'un **purge à sept jours** — c'est sa raison d'être, la
matière brute d'un culte ne survit pas à la promesse de suppression. L'autre garde ce qu'on
lui confie : c'est là que vivent les images d'annonces, et c'est là que doit vivre une
prédication publiée.

🔴 **Une pièce est ce que le pasteur a écouté puis choisi.** Le découpage est le
consentement ; un objet consenti n'a pas de date de péremption. Le ranger dans le magasin
qui purge le ferait disparaître au septième jour, avec le reste — et l'assemblée verrait un
fil dont les entrées cessent de se jouer une à une.
"""

from __future__ import annotations

from app.contexts.media.application.media_store import MediaStore


class MediaPieceAudioStore:
    """Range les octets d'une pièce dans le magasin durable du dépôt."""

    def __init__(self, media: MediaStore) -> None:
        self._media = media

    async def ranger(self, octets: bytes, *, content_type: str) -> str:
        return await self._media.put(octets, content_type=content_type)
