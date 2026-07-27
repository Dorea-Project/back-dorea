"""Le `Referent` — *une personne, quelqu'un qui la connaît*.

Ce module matérialise un invariant relationnel **sans créer un champ à maintenir**. Aucun
`current_referent_id` n'est stocké sur la personne, aucun `is_primary` sur l'appartenance : le
référent est **résolu à la lecture**. Un champ que personne n'a intérêt à tenir à jour pourrit
en trois mois — et on se retrouve avec des gens à zéro ou deux primaires, c'est-à-dire
l'indétermination qu'on voulait supprimer.

Ce qui est persisté : les **overrides explicites** (une décision humaine) et l'**historique
observé** (pour dater les trous). Rien d'autre.

**Le référent n'est pas le propriétaire d'un signal.** Le premier est un lien durable et **peut
être nul** — « personne ne connaît cette personne » est une donnée, la plus utile du module. Le
second est une assignation opérationnelle et **ne l'est jamais**. Si l'escalade remplissait le
référent, la couverture vaudrait mécaniquement 100 % et la métrique la plus vendable du produit
ne mesurerait plus rien. Un pasteur référent de 200 personnes n'est le référent de personne.

**Le rang des types de groupe est une donnée, pas une constante.** Il vit en table
(`group_type_policy`) : ce module ne connaît le nom d'aucun type. Enrichir `GroupType` devient
une insertion de ligne, pas une modification de code — et le résolveur ne peut pas casser
quand l'énumération bouge.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ReferentOrigin(StrEnum):
    """D'où vient le lien. L'ordre de déclaration **est** l'ordre de la cascade."""

    MANUAL = "manual"  # désignation humaine explicite — gagne toujours
    GROUP_LEAD = "group_lead"  # responsable du groupe primaire — pointeur CALCULÉ
    INVITER = "inviter"  # celui qui a invité — visiteurs et sympathisants
    WELCOME_TEAM = "welcome_team"  # filet pour les visiteurs sans inviteur


# Les origines que l'on **stocke** : les autres sont dérivées, donc jamais écrites.
STORED_ORIGINS: frozenset[ReferentOrigin] = frozenset(
    {ReferentOrigin.MANUAL, ReferentOrigin.INVITER, ReferentOrigin.WELCOME_TEAM}
)

# L'ordre dans lequel la cascade essaie. `GROUP_LEAD` s'intercale en 2 sans être stocké.
CASCADE: tuple[ReferentOrigin, ...] = (
    ReferentOrigin.MANUAL,
    ReferentOrigin.GROUP_LEAD,
    ReferentOrigin.INVITER,
    ReferentOrigin.WELCOME_TEAM,
)


class ReferentChangeCause(StrEnum):
    """Pourquoi le lien a bougé — ce qui rend un trou lisible et priorisable."""

    MANUAL_SET = "manual_set"
    MANUAL_ENDED = "manual_ended"
    JOINED_GROUP = "joined_group"
    LEFT_GROUP = "left_group"
    LEADER_CHANGED = "leader_changed"
    ACCOUNT_REVOKED = "account_revoked"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class GroupTypePolicy:
    """La politique de veille d'un **type** de groupe. En table, jamais en dur.

    `bears_veille` dit si ce type peut fonder un lien de veille. Un type qui ne porte pas de
    politique d'alerte (une commission, une association) ne peut pas fonder un référent : la
    personne dont c'est la seule appartenance est structurellement un trou de couverture, et
    c'est **juste** — il faut alors la désigner à la main.

    `primacy_rank` ordonne par **durabilité du lien**, pas par intensité. Une classe
    d'intégration s'achève en quelques mois ; un ministère dure. Quelqu'un qui est dans les deux
    verra son référent basculer tout seul quand la classe se termine — gratuitement, puisque
    `GROUP_LEAD` est un pointeur calculé."""

    group_type: str
    bears_veille: bool
    primacy_rank: int


@dataclass(frozen=True)
class MembershipCandidate:
    """Une appartenance active, telle que la résolution a besoin de la voir."""

    group_id: UUID
    group_type: str
    joined_at: datetime


@dataclass(frozen=True)
class Referent:
    """Le lien résolu. `since` date la relation, pas le calcul."""

    person_id: UUID
    referent_person_id: UUID
    origin: ReferentOrigin
    since: datetime


class ReferentOverride:
    """Une désignation **explicite**, stockée seulement parce qu'elle existe."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        person_id: UUID,
        referent_person_id: UUID,
        origin: ReferentOrigin,
        started_at: datetime,
        started_by_account_id: UUID,
        ended_at: datetime | None = None,
        ended_reason: str | None = None,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.person_id = person_id
        self.referent_person_id = referent_person_id
        self.origin = origin
        self.started_at = started_at
        self.started_by_account_id = started_by_account_id
        self.ended_at = ended_at
        self.ended_reason = ended_reason

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    def end(self, *, at: datetime, reason: str) -> None:
        if self.ended_at is None:
            self.ended_at = at
            self.ended_reason = reason


class PrimaryGroupOverride:
    """« C'est ce groupe-là qui compte pour elle » — stocké seulement s'il existe."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        person_id: UUID,
        group_id: UUID,
        started_at: datetime,
        started_by_account_id: UUID,
        ended_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.person_id = person_id
        self.group_id = group_id
        self.started_at = started_at
        self.started_by_account_id = started_by_account_id
        self.ended_at = ended_at

    @property
    def is_active(self) -> bool:
        return self.ended_at is None


class ReferentHistoryEntry:
    """Append-only. `referent_person_id = NULL` marque le **début d'un trou**.

    Un trou de trois jours (le responsable vient de partir) et un trou de huit mois ne portent
    pas la même information. Sans datation, « sans référent » n'est pas actionnable ; avec elle,
    « sans référent depuis quatre mois » l'est."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        person_id: UUID,
        referent_person_id: UUID | None,
        origin: ReferentOrigin | None,
        observed_at: datetime,
        cause: ReferentChangeCause,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.person_id = person_id
        self.referent_person_id = referent_person_id
        self.origin = origin
        self.observed_at = observed_at
        self.cause = cause

    @property
    def is_gap(self) -> bool:
        return self.referent_person_id is None


# --- Fonctions pures ---------------------------------------------------------------------------


def pick_primary_group(
    candidates: Sequence[MembershipCandidate],
    policies: dict[str, GroupTypePolicy],
    *,
    override_group_id: UUID | None = None,
) -> MembershipCandidate | None:
    """Le groupe qui fonde le lien de veille. **Aucun nom de type n'apparaît ici.**

    Un override manuel gagne, à condition que l'appartenance soit encore active. Sinon on trie
    par rang de type, puis par ancienneté d'appartenance, puis par identifiant.

    Ce troisième critère n'est pas cosmétique : sans lui, deux exécutions peuvent diverger sur
    une égalité, et le déterminisme du moteur — donc la rejouabilité du ledger — tombe.
    """
    if override_group_id is not None:
        chosen = next((c for c in candidates if c.group_id == override_group_id), None)
        if chosen is not None:
            return chosen  # l'override ne vaut que si l'appartenance tient encore

    eligible = [
        c
        for c in candidates
        if c.group_type in policies and policies[c.group_type].bears_veille
    ]
    if not eligible:
        return None

    return min(
        eligible,
        key=lambda c: (policies[c.group_type].primacy_rank, c.joined_at, str(c.group_id)),
    )


def gap_duration(
    entry: ReferentHistoryEntry | None,
    at: datetime,
    *,
    member_since: datetime | None = None,
):
    """Depuis combien de temps cette personne n'est sous le regard de personne.

    Un historique vide ne veut pas dire « pas de trou » : il veut dire **« personne ne l'a
    jamais connue »**. Ce sont les plus exposées du fichier, et sans repli elles n'auraient
    aucune clé de tri sur l'écran de couverture — donc elles resteraient en bas de la liste
    indéfiniment. On retombe alors sur la date d'adhésion : le trou court depuis son arrivée.
    """
    if entry is not None:
        return at - entry.observed_at if entry.is_gap else None
    if member_since is None:
        return None
    return at - member_since
