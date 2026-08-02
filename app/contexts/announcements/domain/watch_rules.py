"""Ce que le **type d'annonce** propose — la part de la décision qui appartient aux Annonces.

La table de décision elle-même (rôle → effet, durées, portées) vit dans le moteur de veille,
`watch/domain/role_rules.py` : c'est la règle de l'étage 02, et une source parle le vocabulaire
de l'engine, jamais l'inverse. Ce module ne garde que ce qui relève du fil d'actualité :

- quels **types** peuvent porter un sujet, et lesquels n'en portent jamais ;
- quels **rôles** un type propose au publicateur.

Les symboles du moteur sont réexportés ici pour que les Annonces n'aient qu'un import à faire.
"""

from __future__ import annotations

from app.contexts.announcements.domain.enums import AnnouncementCategory
from app.contexts.watch.domain.role_rules import (
    ROLE_RULES,
    RoleRule,
    SubjectRole,
    WatchEffect,
    WatchScope,
    episode_window,
    neutralization_window,
    resolve_effects,
    rule_for,
)

__all__ = [
    "ROLES_FOR_CATEGORY",
    "ROLE_RULES",
    "SUBJECTLESS_CATEGORIES",
    "RoleRule",
    "SubjectRole",
    "WatchEffect",
    "WatchScope",
    "accepts_subjects",
    "episode_window",
    "neutralization_window",
    "resolve_effects",
    "roles_for",
    "rule_for",
]

C, R = AnnouncementCategory, SubjectRole


# Un type qui parle d'une **activité** (un culte, un appel à servir, une info) ne parle de
# personne : lui rattacher un sujet est refusé **à l'écriture**, pas par convention. C'est aussi
# ce qui interdit de dériver un effet de veille d'une donnée d'argent ou de participation.
SUBJECTLESS_CATEGORIES: frozenset[AnnouncementCategory] = frozenset(
    {C.SERVICE, C.MEETING, C.CALL, C.INFO, C.SERMON}
)


# Le type **propose**, il ne décide pas : ces listes bornent ce qu'un publicateur peut choisir.
ROLES_FOR_CATEGORY: dict[AnnouncementCategory, tuple[SubjectRole, ...]] = {
    C.DEATH: (R.DECEASED, R.BEREAVED),
    C.BIRTH: (R.NEW_PARENT,),
    C.WEDDING: (R.NEWLYWED,),
    C.BAPTISM: (R.HONOREE,),
    # « Les vingt ans de ministère du pasteur Kouassi » : on peut nommer celui qu'on fête. Le rôle
    # `HONOREE` n'a **aucun effet de veille** — on célèbre, on ne surveille pas — et c'est ce qui
    # rend l'ouverture sans risque : nommer quelqu'un dans une fête ne touche pas à sa veille.
    C.CELEBRATION: (R.HONOREE,),
    C.SICKNESS: (R.SICK,),
    C.TRAVEL: (R.TRAVELER,),
    C.PRAYER: (R.SICK, R.BEREAVED, R.TRAVELER),  # « portons X » — le rôle précise pourquoi
    C.TESTIMONY: (R.HONOREE,),
}


def accepts_subjects(category: AnnouncementCategory) -> bool:
    return category not in SUBJECTLESS_CATEGORIES


def roles_for(category: AnnouncementCategory) -> tuple[SubjectRole, ...]:
    """Les rôles que ce type propose (vide = ce type ne porte pas de sujet)."""
    return ROLES_FOR_CATEGORY.get(category, ())
