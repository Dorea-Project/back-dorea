"""La durée d'une vidéo — **mesurée**, jamais déclarée.

Un client qui annonce « 30 s » peut se tromper, et surtout peut mentir. Une limite qui repose sur
une déclaration n'est pas une limite : c'est une convention, et les conventions cèdent devant le
premier qui a intérêt à passer outre — ici, celui qui veut poster un film de vingt minutes en
couverture d'un événement.

**On lit l'en-tête du conteneur.** Un MP4 est une suite de « boîtes » `[taille][type][contenu]` ;
la boîte `mvhd`, dans `moov`, porte l'échelle de temps et la durée du film. Vingt lignes de
lecture d'octets, aucune dépendance, aucun décodage : on n'ouvre pas la vidéo, on lit sa fiche.

**Et on n'accepte que ce qu'on sait mesurer.** MP4 seulement. WebM porte aussi sa durée, dans une
structure EBML nettement plus coûteuse à parcourir ; l'accepter sans savoir la lire reviendrait à
rouvrir la porte qu'on vient de fermer. Un format qu'on ne sait pas mesurer est un format qu'on
refuse — quitte à en ajouter un le jour où on saura.
"""

from __future__ import annotations

import struct

# Les boîtes qui **contiennent** d'autres boîtes et qu'il faut donc ouvrir pour trouver `mvhd`.
_CONTAINERS = (b"moov",)
# Au-delà, ce n'est plus un en-tête : on arrête de chercher plutôt que de parcourir un film.
_MAX_HEADER_SCAN = 4 * 1024 * 1024


def mp4_duration_seconds(content: bytes) -> float | None:
    """La durée en secondes, ou `None` si l'en-tête ne la porte pas (ou n'est pas un MP4).

    `None` n'est pas « zéro » : c'est « je ne sais pas ». L'appelant refuse — accepter ce qu'on
    n'a pas su mesurer viderait la limite de son sens."""
    return _scan(content, 0, min(len(content), _MAX_HEADER_SCAN))


def _scan(content: bytes, start: int, end: int) -> float | None:
    offset = start
    while offset + 8 <= end:
        size = int.from_bytes(content[offset : offset + 4], "big")
        kind = content[offset + 4 : offset + 8]
        header = 8
        if size == 1:  # taille 64 bits, stockée juste après le type
            if offset + 16 > end:
                return None
            size = int.from_bytes(content[offset + 8 : offset + 16], "big")
            header = 16
        elif size == 0:  # « jusqu'à la fin du fichier »
            size = end - offset

        if size < header:
            return None  # boîte incohérente : on ne devine pas
        if kind == b"mvhd":
            return _read_mvhd(content[offset + header : offset + size])
        if kind in _CONTAINERS:
            found = _scan(content, offset + header, min(offset + size, end))
            if found is not None:
                return found
        offset += size
    return None


def _read_mvhd(payload: bytes) -> float | None:
    """`mvhd` : version, flags, dates, **échelle de temps**, **durée**.

    La durée est exprimée en unités d'échelle — 900 000 unités à 30 000/s font trente secondes.
    Deux dispositions selon la version, et la v1 est celle des longs formats (dates et durée sur
    64 bits) : la lire aussi évite qu'un encodeur récent passe au travers."""
    if len(payload) < 4:
        return None
    version = payload[0]
    try:
        if version == 1:
            timescale, duration = struct.unpack(">IQ", payload[20:32])
        else:
            timescale, duration = struct.unpack(">II", payload[12:20])
    except struct.error:
        return None
    if not timescale:
        return None
    return duration / timescale
