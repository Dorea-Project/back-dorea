"""Lecture bornée du corps de requête — protège contre le DoS mémoire (upload non borné).

`request.body()` bufferise tout le flux en RAM sans limite : sur un monolithe partagé, un seul
appelant peut saturer la mémoire et faire tomber toutes les églises. Ce helper rejette d'abord sur
`Content-Length`, puis lit en streaming avec un plafond dur (couvre le cas chunked sans en-tête).
"""

from __future__ import annotations

from fastapi import Request

from app._shared.domain.errors import PayloadTooLargeError


async def read_body_capped(request: Request, *, max_bytes: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise PayloadTooLargeError(
            "Fichier trop volumineux.", details={"max_bytes": max_bytes}
        )
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                "Fichier trop volumineux.", details={"max_bytes": max_bytes}
            )
        chunks.append(chunk)
    return b"".join(chunks)
