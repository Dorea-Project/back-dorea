"""Entités et racines d'agrégat — briques d'identité du domaine."""

from __future__ import annotations

from uuid import UUID

from app._shared.domain.events import DomainEvent


class Entity:
    """Objet du domaine identifié par son `id`.

    L'égalité se fait par **identité** (type + id), jamais par valeur — deux
    entités aux mêmes attributs mais d'`id` différents restent distinctes.
    """

    id: UUID

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id))


class AggregateRoot(Entity):
    """Racine d'agrégat — seul point d'entrée transactionnel de son cluster.

    Elle garantit les invariants de l'agrégat et accumule d'éventuels
    événements de domaine. ⚠️ Il n'y a **pas de broker** (spec §14) : les
    événements sont *tirés* par la couche application si besoin, pas publiés.
    """

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    def record_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events
