"""Génération d'un `slug` d'église — identifiant lisible pour liens/QR (M0 §2.2).

Dérivé du nom, **suffixé** par un fragment de l'UUID pour garantir l'unicité sans
pré-lecture (deux « Beta » restent distincts). Éditable ensuite par l'Owner.
"""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """« Église Bêta » → « eglise-beta » (ASCII, minuscules, tirets)."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return _NON_SLUG.sub("-", ascii_text).strip("-")


def build_slug(name: str, tenant_id: UUID) -> str:
    """Slug unique et lisible : base dérivée du nom + suffixe court de l'UUID."""
    base = slugify(name) or "eglise"
    return f"{base}-{tenant_id.hex[:6]}"
