"""Port + validation du stockage média (images d'annonces).

Le backend ne fait que **ranger un fichier et rendre son URL** (M8 lit `media_urls`). Le port
est abstrait : `LocalMediaStore` (dev) ou `S3MediaStore` (prod). L'upload passe par le **body brut**
(bytes + `Content-Type`), sans multipart — le validateur borne type et taille.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app._shared.domain.errors import DomainError

# content-type → extension de fichier (les seuls types autorisés par défaut).
EXTENSION_OF: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    # SVG : jamais **uploadé** (hors `allowed_types`) ; produit par le générateur de
    # carte missionnaire (M9-1), rangé via `MediaStore.put`. D'où sa présence ici seule.
    "image/svg+xml": "svg",
}


class MediaTooLargeError(DomainError):
    code = "MEDIA_TOO_LARGE"
    http_status = 413


class MediaTypeNotAllowedError(DomainError):
    code = "MEDIA_TYPE_NOT_ALLOWED"
    http_status = 415


class MediaStore(ABC):
    @abstractmethod
    async def put(self, content: bytes, *, content_type: str) -> str:
        """Range le fichier et renvoie son **URL publique**."""
        ...


def validate_upload(
    content_type: str, size: int, *, max_bytes: int, allowed_types: list[str]
) -> None:
    if content_type not in allowed_types:
        raise MediaTypeNotAllowedError(
            "Type de fichier non autorisé (images seulement).",
            details={"content_type": content_type, "allowed": allowed_types},
        )
    if size == 0:
        raise MediaTooLargeError("Fichier vide.", details={"size": size})
    if size > max_bytes:
        raise MediaTooLargeError(
            "Fichier trop volumineux.", details={"size": size, "max_bytes": max_bytes}
        )
