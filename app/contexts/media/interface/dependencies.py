"""Injection du stockage média — un seul store par configuration (mémoïsé)."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.contexts.media.application.media_store import MediaStore
from app.contexts.media.infrastructure.stores import build_media_store
from app.core.config import get_settings


@lru_cache
def _store() -> MediaStore:
    # Local (dev) ou S3/MinIO (prod) selon la config ; construit une fois.
    return build_media_store(get_settings())


def get_media_store() -> MediaStore:
    return _store()


MediaStoreDep = Annotated[MediaStore, Depends(get_media_store)]
