"""Adaptateurs de stockage média : local (dev) et S3/MinIO (prod), + factory.

`build_media_store(settings)` : S3/MinIO si `s3_endpoint_url` défini, sinon **local** (fichiers
servis en statique). Le local marche sans aucune dépendance ; l'import de `minio` est **paresseux**
(le module se charge sans la lib ; l'erreur ne survient qu'en activant S3 sans l'avoir installée).
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from uuid import uuid4

from app.contexts.media.application.media_store import EXTENSION_OF, MediaStore
from app.core.config import Settings


def _key_for(content_type: str) -> str:
    return f"{uuid4().hex}.{EXTENSION_OF.get(content_type, 'bin')}"


class LocalMediaStore(MediaStore):
    """Dev : écrit sous un répertoire, renvoie une URL servie en statique par l'app."""

    def __init__(self, *, directory: str, base_url: str) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._base = base_url.rstrip("/")

    async def put(self, content: bytes, *, content_type: str) -> str:
        key = _key_for(content_type)
        await asyncio.to_thread((self._dir / key).write_bytes, content)
        return f"{self._base}/{key}"


class S3MediaStore(MediaStore):
    """Prod : dépose l'objet dans un bucket S3/MinIO, renvoie l'URL publique."""

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str | None,
        secret_key: str | None,
        secure: bool,
        public_base_url: str,
    ) -> None:
        from minio import Minio  # import paresseux (dépendance optionnelle)

        self._client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )
        self._bucket = bucket
        self._base = public_base_url.rstrip("/")

    async def put(self, content: bytes, *, content_type: str) -> str:
        key = _key_for(content_type)
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            key,
            io.BytesIO(content),
            len(content),
            content_type,
        )
        return f"{self._base}/{key}"


def build_media_store(settings: Settings) -> MediaStore:
    if settings.s3_endpoint_url:
        return S3MediaStore(
            endpoint=settings.s3_endpoint_url,
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_secure,
            public_base_url=settings.s3_public_base_url,
        )
    return LocalMediaStore(directory=settings.media_dir, base_url=settings.media_base_url)
