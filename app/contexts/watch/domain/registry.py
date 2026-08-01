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
    CASE_ACTS,
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
# Les Groupes : ils ne disent qu'une chose, l'entrée de quelqu'un dans un groupe. C'est ce qui
# permet de regarder celui qui n'est jamais venu — sinon seule une présence arme le regard.
GROUPS: SourceId = "groups"
# La surface du responsable quand elle rapporte **ses propres gestes** sur un cas. Distincte
# de `WATCH_UI` (d'où part une inquiétude sur autrui) : ce n'est pas la même chose de dire
# quelque chose de quelqu'un et de dire ce que l'on a fait.
CASE_ACTIONS: SourceId = "case_actions"


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
    # Le compagnon dit **aussi** ce que la personne dépose d'elle-même : le signe de vie. Il
    # s'ajoute à `COMPANION` et pas à `WATCH_UI`, et l'asymétrie est le fond du sujet — une
    # reconnaissance ne se dépose qu'à la première personne. Un responsable qui pourrait déposer
    # « elle va bien » à la place de quelqu'un ferait taire un cas avec sa propre impression.
    registry.register(
        RegisteredSource(
            id=COMPANION,
            kinds=frozenset(
                {FactKind.THIRD_PARTY_CONCERN, FactKind.GRATITUDE_DEPOSITED}
            ),
        )
    )
    # L'écran du responsable dit aussi ce qu'il **fait** : il a ouvert le cas, il l'a fermé avec
    # une issue. Ces gestes n'étaient écrits que sur la projection — donc perdus au premier rejeu,
    # avec les deux métriques du pilote. Les clés qu'ils exigent tiennent au type de fait
    # (`KIND_REQUIRED_KEYS`) et non à la surface : un geste anonyme n'est pas un geste.
    registry.register(
        RegisteredSource(id=CASE_ACTIONS, kinds=frozenset(CASE_ACTS))
    )
    # L'entrée dans un groupe : `group_id` est obligatoire, puisque c'est le rythme de ce
    # groupe-là qui dira quand regarder. Sans lui, le fait n'aurait rien à armer.
    registry.register(
        RegisteredSource(
            id=GROUPS,
            kinds=frozenset({FactKind.JOINED_GROUP}),
            required_payload_keys=frozenset({"group_id"}),
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
