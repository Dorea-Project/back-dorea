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
    ActorRequiredError,
    ForbiddenFactKindError,
    SourceNotRegisteredError,
)
from app.contexts.watch.domain.facts import (
    ACTOR_KEY,
    ACTOR_REQUIRED,
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
            # Un fait qui peut retirer quelqu'un de la veille doit dire **qui** l'a posé. Le
            # contrôle est ici, au démarrage : une source qui l'oublierait ferait du défunt
            # l'auteur déclaré de sa propre exclusion, et on le découvrirait dans un audit.
            if kind in ACTOR_REQUIRED and ACTOR_KEY not in source.required_payload_keys:
                raise ActorRequiredError(
                    "Ce type de fait peut retirer quelqu'un de la veille : la source doit "
                    "exiger l'acteur du geste.",
                    details={"kind": kind.value, "source": source.id, "missing": ACTOR_KEY},
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
APPOINTMENTS: SourceId = "appointments"
MISSION: SourceId = "mission"
# Les deux surfaces d'où part un signalement par un tiers. Deux sources, **un seul** kind : le
# responsable depuis son écran de veille, le membre depuis son compagnon. Les distinguer sert à
# lire l'adoption de chaque canal, jamais à traiter les faits différemment.
WATCH_UI: SourceId = "watch_ui"
COMPANION: SourceId = "companion"
WATCH_SCHEDULER: SourceId = "watch_scheduler"  # le worker de l'engine, qui fait entrer le temps


def default_registry() -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(
        RegisteredSource(
            id=ANNOUNCEMENTS,
            kinds=frozenset({FactKind.LIFE_EVENT_ANNOUNCED}),
            # `actor_account_id` est obligatoire parce qu'un décès annoncé **retire** la personne
            # de la veille : l'auteur de l'annonce est l'auteur du geste, et il ne peut pas être
            # la personne retirée.
            required_payload_keys=frozenset({"announcement_id", "role", "actor_account_id"}),
        )
    )
    registry.register(
        RegisteredSource(
            id=ATTENDANCE,
            kinds=frozenset({FactKind.PRESENCE_RECORDED, FactKind.QUALIFICATION_SET}),
        )
    )
    # Le rendez-vous n'ajoute **aucun** type de fait : `APPOINTMENT_REQUESTED` existait déjà,
    # et son état voyage dans le payload. C'est la preuve que le contrat tient — le greffon le
    # plus lourd du produit se pose sans rouvrir le registre.
    registry.register(
        RegisteredSource(
            id=APPOINTMENTS,
            kinds=frozenset({FactKind.APPOINTMENT_REQUESTED}),
            required_payload_keys=frozenset({"appointment_id", "state"}),
        )
    )
    # La mission n'émet **que** l'acceptation — jamais les réactions à une capsule. Une
    # réaction anonyme est une graine, pas une entrée en veille : elle n'a pas à être fichée.
    registry.register(
        RegisteredSource(
            id=MISSION,
            kinds=frozenset({FactKind.SELF_DECLARATION}),
            required_payload_keys=frozenset({"kind"}),
        )
    )
    # Le signalement par un tiers n'exige **aucune** clé de payload : la nuance est optionnelle,
    # et le propriétaire peut légitimement être nul quand personne ne connaît la personne. Ce
    # vide est la spécification, pas un oubli — il n'y a rien à écrire sur quelqu'un.
    for surface in (WATCH_UI, COMPANION):
        registry.register(
            RegisteredSource(id=surface, kinds=frozenset({FactKind.THIRD_PARTY_CONCERN}))
        )
    registry.register(
        RegisteredSource(
            id=WATCH_SCHEDULER,
            kinds=frozenset({FactKind.CHECK_FIRED}),
            required_payload_keys=frozenset({"check_id"}),
        )
    )
    return registry
