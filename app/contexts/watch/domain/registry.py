"""Le registre des sources — ajouter n'est pas modifier.

Une source nouvelle s'enregistre avec ce qu'elle émet, la preuve de consentement qu'elle
fournit, et sa version. L'engine **refuse tout fait d'une source non enregistrée**. C'est ce qui
permet de greffer sans jamais rouvrir le noyau : on ajoute une entrée au registre et un
interpreter, rien d'autre ne bouge.

Le registre porte aussi le **filtre** : un kind de forme interdite (inaction, financier, inféré)
est rejeté à l'enregistrement. La tentation d'ajouter `MEMBER_INACTIVE_ON_APP` échoue au
démarrage de l'application, pas à la revue de code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contexts.watch.domain.errors import (
    ForbiddenFactKindError,
    SourceNotRegisteredError,
)
from app.contexts.watch.domain.facts import (
    FactKind,
    SourceId,
    forbidden_reason,
)


@dataclass(frozen=True)
class RegisteredSource:
    """Un greffon autorisé à parler à l'engine."""

    id: SourceId
    kinds: frozenset[FactKind]
    version: int = 1
    required_payload_keys: frozenset[str] = frozenset()


class SourceRegistry:
    """Le portier. Rien d'autre dans l'engine ne décide qui a le droit d'émettre."""

    def __init__(self) -> None:
        self._sources: dict[SourceId, RegisteredSource] = {}

    def register(self, source: RegisteredSource) -> RegisteredSource:
        for kind in source.kinds:
            family = forbidden_reason(kind.value)
            if family is not None:
                raise ForbiddenFactKindError(
                    "Ce type de fait relève d'une famille interdite par le produit.",
                    details={"kind": kind.value, "family": family, "source": source.id},
                )
        self._sources[source.id] = source
        return source

    def get(self, source_id: SourceId) -> RegisteredSource:
        source = self._sources.get(source_id)
        if source is None:
            raise SourceNotRegisteredError(
                "Source inconnue de l'engine.", details={"source": source_id}
            )
        return source

    def accepts(self, source_id: SourceId, kind: FactKind) -> bool:
        source = self._sources.get(source_id)
        return source is not None and kind in source.kinds

    @property
    def sources(self) -> tuple[RegisteredSource, ...]:
        return tuple(self._sources.values())


# --- Les sources de lancement ---------------------------------------------------------------

ANNOUNCEMENTS: SourceId = "announcements"
ATTENDANCE: SourceId = "attendance"
WATCH_SCHEDULER: SourceId = "watch_scheduler"  # le worker de l'engine, qui fait entrer le temps


def default_registry() -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(
        RegisteredSource(
            id=ANNOUNCEMENTS,
            kinds=frozenset({FactKind.LIFE_EVENT_ANNOUNCED}),
            required_payload_keys=frozenset({"announcement_id", "role"}),
        )
    )
    registry.register(
        RegisteredSource(
            id=ATTENDANCE,
            kinds=frozenset({FactKind.PRESENCE_RECORDED, FactKind.QUALIFICATION_SET}),
        )
    )
    registry.register(
        RegisteredSource(
            id=WATCH_SCHEDULER,
            kinds=frozenset({FactKind.CHECK_FIRED}),
            required_payload_keys=frozenset({"check_id"}),
        )
    )
    return registry
