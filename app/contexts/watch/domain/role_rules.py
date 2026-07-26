"""**Table de décision** d'un événement de vie → effet de veille. Le rôle décide, pas le type.

Ce module vit dans le moteur, pas dans les Annonces : c'est la règle métier de l'étage 02, et
une source doit parler le vocabulaire de l'engine, jamais l'inverse. Les Annonces gardent ce qui
leur appartient — quels rôles un type d'annonce propose, et l'accord du sujet avant publication.

Module **pur** : aucune I/O, aucune horloge, aucun accès en écriture. C'est là que se testent les
invariants du dispositif, sans base de données.

Les durées sont des **paramètres à calibrer par église** (backtest terrain), pas des constantes
de la nature. Elles vivent ici en attendant la table `(tenant, param, value, effective_from)`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum


class SubjectRole(StrEnum):
    """Le rôle qu'une personne tient dans un événement de vie.

    Une même annonce porte plusieurs rôles opposés : un décès, c'est un `DECEASED` (qui sort de
    la veille) **et** des `BEREAVED` (qu'on entoure)."""

    DECEASED = "deceased"  # le défunt
    BEREAVED = "bereaved"  # l'endeuillé — reste attendu, mais on l'entoure
    SICK = "sick"  # le malade (donnée intime : accord du sujet exigé en amont)
    NEW_PARENT = "new_parent"  # le parent d'un nouveau-né
    NEWLYWED = "newlywed"  # le marié
    TRAVELER = "traveler"  # le voyageur (durée déclarée)
    HONOREE = "honoree"  # celui qu'on célèbre — aucun effet


class WatchEffect(StrEnum):
    """Ce qu'un rôle fait à la veille d'une personne.

    - `EXIT` — retrait **définitif** : plus jamais de signal, quelle que soit la source. Absorbant.
    - `NEUTRALIZATION` — on l'attend plus tard : son silence cesse d'être un silence.
    - `EPISODE` — un cas de soin ouvert : elle reste attendue, mais quelqu'un doit aller vers elle.
    - `NONE` — l'événement ne touche pas la veille."""

    EXIT = "exit"
    NEUTRALIZATION = "neutralization"
    EPISODE = "episode"
    NONE = "none"


class WatchScope(StrEnum):
    """Jusqu'où l'on mobilise autour d'un épisode — **borne de pudeur**, pas de diffusion.

    Une maladie ne dépasse pas la cellule ; un deuil peut atteindre les groupes ; un mariage,
    toute l'église. Distinct de la portée de l'annonce (qui la voit dans le fil)."""

    CELL_ONLY = "cell_only"
    CELL_AND_GROUPS = "cell_and_groups"
    CHURCH = "church"


R, E = SubjectRole, WatchEffect

DECLARED = None  # durée non fixée par la règle : c'est le publicateur qui l'annonce


@dataclass(frozen=True)
class RoleRule:
    """Ce qu'un rôle fait à la veille."""

    effects: tuple[WatchEffect, ...]
    scope: WatchScope = WatchScope.CELL_ONLY
    neutralization_days: int | None = None  # None + NEUTRALIZATION dans `effects` = durée déclarée
    episode_days: int | None = None
    requires_consent: bool = False  # le sujet doit accepter d'être nommé (donnée intime)
    revisable: bool = False  # la durée peut être revue à la hausse en cours de route


ROLE_RULES: dict[SubjectRole, RoleRule] = {
    # Le cas le plus critique du dispositif : sans lui, le moteur signalerait l'absence d'un
    # défunt six semaines plus tard. Terminal et prioritaire — aucun autre effet n'est évalué.
    R.DECEASED: RoleRule(effects=(E.EXIT,), scope=WatchScope.CHURCH),
    # Le deuil **n'excuse pas** l'absence : il ouvre un soin. L'endeuillé reste attendu ; s'il
    # disparaît, c'est un vrai signal. Volontairement sans neutralisation.
    R.BEREAVED: RoleRule(
        effects=(E.EPISODE,), scope=WatchScope.CELL_AND_GROUPS, episode_days=40
    ),
    R.SICK: RoleRule(
        effects=(E.EPISODE, E.NEUTRALIZATION),
        scope=WatchScope.CELL_ONLY,  # la maladie ne sort pas de la cellule
        neutralization_days=30,
        episode_days=30,
        requires_consent=True,  # on ne dit pas la maladie de quelqu'un sans son accord
        revisable=True,
    ),
    R.NEW_PARENT: RoleRule(
        effects=(E.EPISODE, E.NEUTRALIZATION),
        scope=WatchScope.CELL_AND_GROUPS,
        neutralization_days=56,
        episode_days=21,
    ),
    R.NEWLYWED: RoleRule(
        effects=(E.NEUTRALIZATION,), scope=WatchScope.CHURCH, neutralization_days=24
    ),
    R.TRAVELER: RoleRule(
        effects=(E.NEUTRALIZATION,),
        scope=WatchScope.CELL_ONLY,
        neutralization_days=DECLARED,  # « je pars jusqu'au… » : c'est l'annonce qui le dit
    ),
    # On célèbre, on ne surveille pas.
    R.HONOREE: RoleRule(effects=(E.NONE,), scope=WatchScope.CHURCH),
}


def rule_for(role: SubjectRole) -> RoleRule:
    return ROLE_RULES[role]


def resolve_effects(
    role: SubjectRole, override: tuple[WatchEffect, ...] | None = None
) -> tuple[WatchEffect, ...]:
    """Les effets retenus — défaut du rôle, ou surcharge du publicateur.

    La surcharge ne peut que **retrancher** : on décoche un effet proposé, on n'en invente pas
    (sinon le publicateur pourrait neutraliser la veille de n'importe qui via n'importe quel
    rôle). `EXIT` absorbe : dès qu'il est là, il est seul.
    """
    rule = rule_for(role)
    chosen = rule.effects if override is None else tuple(override)

    if WatchEffect.EXIT in chosen and WatchEffect.EXIT in rule.effects:
        return (WatchEffect.EXIT,)

    kept = tuple(e for e in rule.effects if e in chosen)
    return kept or (WatchEffect.NONE,)


def neutralization_window(
    role: SubjectRole, event_date: datetime, *, declared_days: int | None = None
) -> tuple[datetime, datetime] | None:
    """Fenêtre `(début, retour attendu)` d'une neutralisation, ou None si le rôle n'en pose pas.

    **Datée par l'événement**, jamais par la publication : un voyage parti le 12 et annoncé le 20
    a déjà consommé huit jours. La durée déclarée l'emporte toujours sur celle de la règle.
    """
    rule = rule_for(role)
    if WatchEffect.NEUTRALIZATION not in rule.effects:
        return None
    days = declared_days if declared_days is not None else rule.neutralization_days
    if days is None:
        return None  # durée déclarée exigée par la règle et absente — l'appelant tranche
    return event_date, event_date + timedelta(days=days)


def episode_window(role: SubjectRole, event_date: datetime) -> tuple[datetime, datetime] | None:
    """Fenêtre `(ouverture, expiration)` d'un épisode, ou None si le rôle n'en ouvre pas."""
    rule = rule_for(role)
    if WatchEffect.EPISODE not in rule.effects or rule.episode_days is None:
        return None
    return event_date, event_date + timedelta(days=rule.episode_days)


def with_durations(
    role: SubjectRole, *, neutralization_days: int | None = None, episode_days: int | None = None
) -> RoleRule:
    """Règle calibrée pour une église donnée — point d'entrée du paramétrage par tenant."""
    rule = rule_for(role)
    return replace(
        rule,
        neutralization_days=(
            neutralization_days if neutralization_days is not None else rule.neutralization_days
        ),
        episode_days=episode_days if episode_days is not None else rule.episode_days,
    )
