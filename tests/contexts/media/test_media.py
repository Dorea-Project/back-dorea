"""Média : validation (type/taille), stockage local, choix du store par config."""

from pathlib import Path

import pytest

from app.contexts.media.application.media_store import (
    MediaTooLargeError,
    MediaTypeNotAllowedError,
    validate_upload,
)
from app.contexts.media.infrastructure.stores import LocalMediaStore, build_media_store
from app.core.config import Settings

_ALLOWED = ["image/png", "image/jpeg"]


# --- Validation ---


def test_validate_accepts_a_small_png():
    validate_upload("image/png", 1024, max_bytes=5_000_000, allowed_types=_ALLOWED)  # pas d'erreur


def test_validate_rejects_a_non_image():
    with pytest.raises(MediaTypeNotAllowedError):
        validate_upload("application/pdf", 1024, max_bytes=5_000_000, allowed_types=_ALLOWED)


def test_validate_rejects_too_large_and_empty():
    with pytest.raises(MediaTooLargeError):
        validate_upload("image/png", 6_000_000, max_bytes=5_000_000, allowed_types=_ALLOWED)
    with pytest.raises(MediaTooLargeError):
        validate_upload("image/png", 0, max_bytes=5_000_000, allowed_types=_ALLOWED)


# --- Stockage local ---


async def test_local_store_writes_the_file_and_returns_a_url(tmp_path):
    store = LocalMediaStore(directory=str(tmp_path), base_url="/media")
    url = await store.put(b"\x89PNG fake bytes", content_type="image/png")

    assert url.startswith("/media/") and url.endswith(".png")  # URL + extension du type
    key = url.rsplit("/", 1)[1]
    saved = Path(tmp_path) / key
    assert saved.exists() and saved.read_bytes() == b"\x89PNG fake bytes"


# --- Choix du store ---


def test_build_uses_local_when_s3_unconfigured(tmp_path):
    store = build_media_store(
        Settings(s3_endpoint_url=None, media_dir=str(tmp_path), media_base_url="/media")
    )
    assert isinstance(store, LocalMediaStore)


# --------------------------------------------------- DOREA-024 · le type annoncé vs les octets

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def test_un_fichier_qui_ment_sur_son_type_est_refuse():
    """Le `Content-Type` est **déclaré par le client** : il dit ce qu'il veut.

    Sans recoupement, un fichier arbitraire se rangeait sous une extension d'image — et se
    faisait ensuite servir comme telle."""
    with pytest.raises(MediaTypeNotAllowedError):
        validate_upload(
            "image/png",
            64,
            max_bytes=5_000_000,
            allowed_types=_ALLOWED,
            content=b"<?php echo 1; ?>" + b"\x00" * 32,
        )


def test_un_jpeg_annonce_png_est_refuse():
    """Même famille, mauvais format : la signature ne pardonne pas."""
    with pytest.raises(MediaTypeNotAllowedError):
        validate_upload(
            "image/png", 64, max_bytes=5_000_000, allowed_types=_ALLOWED, content=_JPEG
        )


def test_les_vrais_fichiers_passent():
    """Le jumeau légitime — un contrôle qui refuse le bon fichier est une régression."""
    validate_upload("image/png", 64, max_bytes=5_000_000, allowed_types=_ALLOWED, content=_PNG)
    validate_upload("image/jpeg", 64, max_bytes=5_000_000, allowed_types=_ALLOWED, content=_JPEG)
