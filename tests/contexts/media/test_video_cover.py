"""La durée d'une vidéo de couverture — **mesurée, jamais déclarée**.

Un client qui annonce « 30 s » peut se tromper, et surtout peut mentir. Une limite qui repose sur
une déclaration n'est pas une limite : c'est une convention, et les conventions cèdent devant le
premier qui a intérêt à passer outre — ici, celui qui veut poster un film de vingt minutes en
couverture d'un événement.

On lit donc l'en-tête du conteneur. Ces tests fabriquent de vrais MP4 minimaux — les boîtes
`ftyp`, `moov` et `mvhd` suffisent à porter une durée — pour vérifier qu'on la lit vraiment.
"""

import struct

import pytest

from app.contexts.media.application.media_store import (
    VIDEO_TYPES,
    MediaTypeNotAllowedError,
    VideoTooLongError,
    validate_upload,
    validate_video,
)
from app.contexts.media.application.video import mp4_duration_seconds


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload) + 8) + kind + payload


def _mvhd_v0(seconds: float, timescale: int = 600) -> bytes:
    """`mvhd` version 0 : version+flags, deux dates, l'échelle, puis la durée."""
    return _box(
        b"mvhd",
        bytes([0]) + b"\x00\x00\x00"  # version 0 + flags
        + struct.pack(">II", 0, 0)  # création, modification
        + struct.pack(">II", timescale, int(seconds * timescale)),
    )


def _mvhd_v1(seconds: float, timescale: int = 90000) -> bytes:
    """Version 1 : dates et durée sur 64 bits — celle des encodeurs récents."""
    return _box(
        b"mvhd",
        bytes([1]) + b"\x00\x00\x00"
        + struct.pack(">QQ", 0, 0)
        + struct.pack(">IQ", timescale, int(seconds * timescale)),
    )


def _mp4(mvhd: bytes) -> bytes:
    return _box(b"ftyp", b"isom" + b"\x00" * 8) + _box(b"moov", mvhd)


# --- Ce qu'on sait lire ------------------------------------------------------------------


@pytest.mark.parametrize("secondes", [0.5, 12.0, 29.9, 30.0, 45.0, 1200.0])
def test_the_duration_is_read_from_the_header(secondes):
    """Vingt lignes de lecture d'octets : on n'ouvre pas la vidéo, on lit sa fiche."""
    assert mp4_duration_seconds(_mp4(_mvhd_v0(secondes))) == pytest.approx(secondes, abs=0.01)


def test_the_sixty_four_bit_variant_is_read_too():
    """Sans elle, un encodeur récent passerait au travers — et « je ne sais pas » vaut refus,
    donc l'auteur verrait sa vidéo de dix secondes rejetée."""
    assert mp4_duration_seconds(_mp4(_mvhd_v1(20.0))) == pytest.approx(20.0, abs=0.01)


def test_what_is_not_an_mp4_has_no_duration():
    """`None` n'est pas « zéro » : c'est « je ne sais pas »."""
    assert mp4_duration_seconds(b"") is None
    assert mp4_duration_seconds(b"GIF89a" + b"\x00" * 200) is None
    assert mp4_duration_seconds(_box(b"ftyp", b"isom")) is None  # pas de `moov`


# --- Ce qui passe, ce qui est refusé -----------------------------------------------------


def test_thirty_seconds_pass_and_thirty_one_do_not():
    assert validate_video(_mp4(_mvhd_v0(30.0)), max_seconds=30) == pytest.approx(30.0, abs=0.01)

    with pytest.raises(VideoTooLongError) as refus:
        validate_video(_mp4(_mvhd_v0(31.0)), max_seconds=30)
    assert refus.value.details["seconds"] == pytest.approx(31.0, abs=0.1)


def test_a_duration_we_could_not_read_is_refused_like_a_long_one():
    """**Accepter ce qu'on n'a pas su mesurer viderait la limite de son sens.**

    Les deux refus partagent une erreur, et c'est volontaire : « je ne sais pas » se traite comme
    « trop longue »."""
    with pytest.raises(VideoTooLongError):
        validate_video(b"pas un mp4 du tout", max_seconds=30)


def test_only_a_format_we_can_measure_is_accepted():
    """WebM porte aussi sa durée, dans une structure nettement plus coûteuse à parcourir.
    L'accepter sans savoir la lire rouvrirait la porte qu'on vient de fermer."""
    assert VIDEO_TYPES == frozenset({"video/mp4"})

    with pytest.raises(MediaTypeNotAllowedError):
        validate_upload(
            "video/webm", 1024, max_bytes=10**7,
            allowed_types=["image/png", "video/mp4"],
        )


def test_a_long_video_is_refused_even_when_it_is_light():
    """**Un poids ne dit pas une durée.** Trente secondes pèsent deux mégaoctets ou deux cents
    selon l'encodeur — une limite en octets ne borne donc pas une durée, et c'est pour ça que la
    seconde vérification existe."""
    vingt_minutes = _mp4(_mvhd_v0(1200.0))

    validate_upload(  # le poids passe : quelques centaines d'octets
        "video/mp4", len(vingt_minutes), max_bytes=10**7, allowed_types=["video/mp4"]
    )

    with pytest.raises(VideoTooLongError):
        validate_video(vingt_minutes, max_seconds=30)
