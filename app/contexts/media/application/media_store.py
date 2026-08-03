"""Port + validation du stockage média (images d'annonces).

Le backend ne fait que **ranger un fichier et rendre son URL** (M8 lit `media_urls`). Le port
est abstrait : `LocalMediaStore` (dev) ou `S3MediaStore` (prod). L'upload passe par le **body brut**
(bytes + `Content-Type`), sans multipart — le validateur borne type et taille.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app._shared.domain.errors import DomainError
from app.contexts.media.application.video import mp4_duration_seconds

# content-type → extension de fichier (les seuls types autorisés par défaut).
EXTENSION_OF: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    # SVG : jamais **uploadé** (hors `allowed_types`) ; produit par le générateur de
    # carte missionnaire (M9-1), rangé via `MediaStore.put`. D'où sa présence ici seule.
    "image/svg+xml": "svg",
    # **MP4 seulement**, et c'est une décision : on n'accepte que les formats dont on sait lire
    # la durée dans l'en-tête (`video.mp4_duration_seconds`). Accepter un conteneur qu'on ne sait
    # pas mesurer rouvrirait la porte que la limite de trente secondes existe pour fermer.
    "video/mp4": "mp4",
}

VIDEO_TYPES: frozenset[str] = frozenset({"video/mp4"})


class MediaTooLargeError(DomainError):
    code = "MEDIA_TOO_LARGE"
    http_status = 413


class MediaTypeNotAllowedError(DomainError):
    code = "MEDIA_TYPE_NOT_ALLOWED"
    http_status = 415


class VideoTooLongError(DomainError):
    """Plus longue que la limite — ou d'une durée qu'on n'a pas su lire.

    Les deux refus partagent une erreur, et c'est volontaire : « je ne sais pas » se traite comme
    « trop longue ». Laisser passer ce qu'on n'a pas mesuré viderait la limite de son sens."""

    code = "MEDIA_VIDEO_TOO_LONG"
    http_status = 422


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


def validate_video(content: bytes, *, max_seconds: int) -> float:
    """Mesure la vidéo et la refuse au-delà de la limite. Renvoie sa durée en secondes.

    Appelée **après** `validate_upload` : le type et la taille sont déjà bornés, il reste la seule
    chose qu'un poids ne dit pas — trente secondes de vidéo pèsent deux mégaoctets ou deux cents
    selon l'encodeur, et une limite en octets ne borne donc pas une durée."""
    seconds = mp4_duration_seconds(content)
    if seconds is None:
        raise VideoTooLongError(
            "Impossible de lire la durée de cette vidéo. Envoyez un MP4.",
            details={"max_seconds": max_seconds},
        )
    if seconds > max_seconds:
        raise VideoTooLongError(
            f"Une vidéo de couverture ne dépasse pas {max_seconds} secondes.",
            details={"seconds": round(seconds, 1), "max_seconds": max_seconds},
        )
    return seconds
