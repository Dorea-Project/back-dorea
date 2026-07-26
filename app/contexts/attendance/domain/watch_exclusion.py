"""Agrégat `WatchExclusion` — le retrait **définitif** de la veille fraternelle.

Le cas le plus critique du dispositif : sans lui, le moteur signalerait l'absence d'un défunt six
semaines plus tard, et une famille recevrait « prenez de ses nouvelles ». Une annonce de décès
pose une exclusion ; plus aucun calcul de veille ne porte sur cette personne, quelle que soit la
source.

**Statut de veille, pas statut d'appartenance.** C'est délibéré : publier une annonce ne doit
jamais pouvoir fermer l'adhésion de quelqu'un (ce geste demande `CLOSE_MEMBERSHIP`, et l'Admin
le fera à son rythme). L'exclusion arrête la surveillance, elle ne touche pas à l'identité.

**Absorbante** : aucun algorithme ne la lève. Il n'y a pas de « dé-exclure » — poser une
exclusion à tort se corrige à la main, dans le contexte qui l'a créée.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.attendance.domain.enums import WatchExclusionReason


class WatchExclusion(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        account_id: UUID,
        tenant_id: UUID,
        reason: WatchExclusionReason,
        excluded_at: datetime,
        declared_by_account_id: UUID,
        source_ref: UUID | None = None,  # l'annonce d'origine (idempotence du rejeu)
        note: str | None = None,  # la raison **en clair**, stockée, jamais recalculée
    ) -> None:
        super().__init__()
        self.id = id
        self.account_id = account_id
        self.tenant_id = tenant_id
        self.reason = reason
        self.excluded_at = excluded_at
        self.declared_by_account_id = declared_by_account_id
        self.source_ref = source_ref
        self.note = note
