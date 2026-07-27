"""Les **défauts de couverture** — ce que le dispositif ne sait pas voir.

Un défaut de couverture n'est pas un cas. Il ne se résout pas par un contact mais par une
**désignation** : nommer un responsable, attribuer des référents, configurer l'église. Les
sorties valides sont *j'ai nommé quelqu'un*, jamais *j'ai appelé*.

Il vit à part des signaux parce qu'il peut porter sur une **église entière** — ce qu'aucun fait
ne sait dire, puisqu'un `Fact` a pour sujet une personne ou un groupe.

**Émis une fois.** Un défaut qui se répète chaque nuit devient du bruit, et le bruit se
désapprend en trois semaines.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app._shared.domain.entity import AggregateRoot
from app.contexts.watch.domain.effects import CoverageGap, CoverageScope


class CoverageGapRecord(AggregateRoot):
    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        scope: CoverageScope,
        gap: CoverageGap,
        reason: str,
        observed_at: datetime,
        subject_id: UUID | None = None,  # NULL quand le défaut porte sur l'église entière
        resolved_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.tenant_id = tenant_id
        self.scope = scope
        self.gap = gap
        self.reason = reason  # en clair, stockée — jamais reconstruite à l'affichage
        self.observed_at = observed_at
        self.subject_id = subject_id
        self.resolved_at = resolved_at

    @property
    def is_open(self) -> bool:
        return self.resolved_at is None

    def resolve(self, *, at: datetime) -> None:
        """Comblé — par une désignation, jamais par un contact."""
        if self.resolved_at is None:
            self.resolved_at = at
