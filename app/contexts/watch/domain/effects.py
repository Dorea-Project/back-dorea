"""Les effets **proposés** — tout ce qu'un interpreter a le droit de dire.

Un interpreter lit un fait et une vue en lecture seule, puis renvoie des propositions. Il n'a
aucun accès en écriture, et ce module est la liste close de ce qu'il peut demander. Ajouter une
source demain, c'est écrire un interpreter qui produit ces mêmes formes — jamais en inventer une
nouvelle, jamais toucher à l'état.

C'est l'arbitrage (étage 03) qui décide lesquelles deviennent visibles, et la matérialisation
(étage 04) qui les écrit. Une proposition n'est pas une décision.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

# Un payload vide et **immuable** : un effet est gelé, sa valeur par défaut ne peut pas être un
# dict que quelqu'un modifierait par mégarde pour tous les autres.
_NO_PAYLOAD: Mapping[str, Any] = MappingProxyType({})


class EffectKind(StrEnum):
    OPEN_CASE = "open_case"
    ENRICH_CASE = "enrich_case"
    NEUTRALISE = "neutralise"
    EXTINGUISH = "extinguish"
    EXCLUDE_FOREVER = "exclude_forever"
    RECORD_MEMORY = "record_memory"
    MARK_CASE_SEEN = "mark_case_seen"
    RECORD_CONTACT_ATTEMPT = "record_contact_attempt"
    RESOLVE_CONTACT_ATTEMPT = "resolve_contact_attempt"
    RESOLVE_CASE = "resolve_case"
    SCHEDULE_CHECK = "schedule_check"
    CANCEL_SCHEDULED_CHECKS = "cancel_scheduled_checks"
    COVERAGE_SIGNAL = "coverage_signal"


class CasePriority(StrEnum):
    """La priorité vient de l'**origine du dire**, pas de la gravité supposée.

    Ce qu'une personne demande pour elle-même passe avant tout, et sort du plafond de débit :
    on ne fait pas attendre quelqu'un qui a levé la main."""

    DECLARED = "declared"  # la personne elle-même — hors plafond
    DEADLINE = "deadline"
    ANNOUNCEMENT = "announcement"
    # Un tiers a signalé une inquiétude. Distincte de `DECLARED` et c'est **le** point où le
    # document du signalement se contredit s'il est lu vite : son §4 dit « origine déclarée »,
    # son §6 dit que le plafond de débit s'y applique *contrairement* au déclaré du membre. Les
    # deux ne peuvent pas tenir sur la même valeur. Celle-ci porte la parole d'un tiers — une
    # vraie parole, donc plus haut qu'une absence calculée ; mais pas celle de l'intéressé, donc
    # soumise au plafond. Sans elle, un responsable débordé taperait dix fois en trente secondes
    # et sortirait dix cas prioritaires du plafond sans avoir appelé personne.
    CONCERN = "concern"
    ABSENCE = "absence"


class ExtinguishCause(StrEnum):
    EXPLAINED_BY_ANNOUNCEMENT = "explained_by_announcement"
    RETURNED = "returned"
    DECEASED = "deceased"
    # Trois tentatives non abouties sur un régime d'échéance. La personne reste en base ; elle
    # sort de la file, pas du fichier. Sans cette péremption, un module d'évangélisation qui
    # fonctionne noie son propre inviteur en trois semaines.
    UNREACHABLE = "unreachable"


# Il n'existe **pas** de cause « signe de vie ». Déposer une reconnaissance prouve qu'on est
# vivant et engagé — pas qu'on est revenu en cellule. Éteindre le cas là-dessus serait la même
# erreur que fermer un deuil parce que la personne est venue au culte : confondre une présence
# avec un état. Un signe de vie **enrichit** le cas et en abaisse la priorité (`EnrichCase`),
# pour que le responsable lise « absente depuis 4 semaines, a déposé un sujet de reconnaissance
# le 12 avril » et comprenne immédiatement de quoi il s'agit.


# Les seules causes qui autorisent une clôture de **cas** sans acte humain. Toute autre exige un
# `closed_by`. La justification commune : le cas n'était pas réel, ou son sujet est hors de
# portée — et on ne demande pas à un responsable de fermer à la main une erreur du système.
#
# `RETURNED` n'y est **pas**, et c'est le point délicat : un retour ferme la *neutralisation*
# (son silence avait une explication, elle a pris fin) mais **pas le cas**. On peut être présent
# et endeuillé. Fermer le soin parce que la personne est venue une fois, ce serait confondre
# « elle est là » avec « elle va bien » — exactement l'erreur que le module doit empêcher.
SYSTEM_CLOSURE_CAUSES: frozenset[ExtinguishCause] = frozenset(
    {
        ExtinguishCause.EXPLAINED_BY_ANNOUNCEMENT,
        ExtinguishCause.DECEASED,
        ExtinguishCause.UNREACHABLE,
    }
)


class CoverageGap(StrEnum):
    """Ce qui manque pour veiller — un défaut de dispositif, jamais un reproche à quelqu'un."""

    NO_REFERENT = "no_referent"  # personne ne connaît cette personne
    BLIND = "blind"  # aucune rencontre saisie : on ne sait rien
    # Ni admin, ni pasteur : l'église n'a **personne** à qui adresser un cas. Sans ce défaut,
    # elle détecterait tout et n'émettrait rien — et son écran vide dirait « tout va bien »
    # alors qu'il dit « aucun destinataire n'existe ». C'est le faux silence que le produit
    # existe pour empêcher, retourné contre lui-même.
    NO_RECIPIENT = "no_recipient"
    # Une demande attend, et aucun pasteur n'est disponible pour la reprendre. Au-delà de deux
    # relais, ce n'est plus un problème de délai : l'église n'a personne pour recevoir.
    NO_PASTORAL_RELAY = "no_pastoral_relay"
    # Une inquiétude signalée, aucun contact depuis. **Porte sur le responsable, pas sur le
    # membre** — et c'est la seule source du produit où l'escalade change de sujet. Escalader
    # vers le pasteur *à propos du membre* n'aurait aucun sens : il ne sait rien de lui, il sait
    # seulement que quelqu'un a ressenti quelque chose. Le problème n'est plus la personne,
    # c'est l'engagement non tenu — et l'action du pasteur est d'appeler le responsable.
    ENGAGEMENT_NOT_KEPT = "engagement_not_kept"
    # Signale beaucoup, contacte peu. Le tell est le **ratio**, jamais le volume : un seuil sur
    # le volume punirait exactement les meilleurs responsables — dix intuitions et dix contacts,
    # c'est l'excellence, et il ne faut surtout pas la freiner.
    LEADER_OVERLOADED = "leader_overloaded"


class OwnerKind(StrEnum):
    """À **quel titre** quelqu'un doit recevoir ce cas — une intention, jamais une identité.

    Un interpreter est pur : il ne peut interroger ni l'annuaire, ni les rôles. Mais il est le
    seul à savoir *pourquoi* un cas revient à telle place — une demande déclinée est une dette de
    l'agenda, pas du référent. Il renvoie donc le titre, et la couche applicative le résout avant
    l'arbitrage. Même patron que le motif d'escalade, déjà renvoyé pour être stocké.
    """

    REFERENT = "referent"  # le défaut : celui qui connaît cette personne
    AGENDA_KEEPER = "agenda_keeper"  # celui qui tient l'agenda du pasteur
    PASTOR = "pastor"  # celui à qui la main avait été tendue


class CoverageScope(StrEnum):
    """Sur quoi porte un défaut de couverture. Distinct du sujet d'un `Fact` : un défaut peut
    concerner l'église entière, ce qu'aucun fait ne sait dire."""

    PERSON = "person"
    GROUP = "group"
    TENANT = "tenant"


class ExclusionCause(StrEnum):
    DECEASED = "deceased"


@dataclass(frozen=True)
class _Effect:
    """Socle commun : sur qui, et **pourquoi en clair**.

    La raison est écrite ici, une fois, et voyagera telle quelle jusqu'à l'affichage. On ne la
    recalcule jamais : un motif reconstruit six semaines plus tard ne dit plus la même chose."""

    subject_id: UUID
    reason: str


@dataclass(frozen=True)
class OpenCase(_Effect):
    origin: CasePriority
    opened_at: datetime
    expires_at: datetime | None = None
    role: str | None = None
    # À qui ce cas revient, **résolu à l'émission** et non recalculé. NULL ici n'est pas une
    # donnée : c'est une question encore ouverte, que l'étage 02bis referme avant l'arbitrage.
    # Un cas sans destinataire est un cas que personne ne traite — et, pire, un cas que
    # n'importe quel responsable de la portée pourrait s'attribuer, donc lire.
    owner_account_id: UUID | None = None
    # À défaut d'identité, le **titre** auquel le destinataire doit être cherché. C'est tout ce
    # qu'un interpreter pur peut dire de sa place.
    owner_kind: OwnerKind = OwnerKind.REFERENT


@dataclass(frozen=True)
class EnrichCase(_Effect):
    """Le cas existe déjà : on lui ajoute ce qu'on vient d'apprendre, sans le dupliquer.

    `annotation` est une phrase **ajoutée** à la fiche du cas — jamais une réécriture de sa
    raison d'origine. `downgrade` abaisse la priorité : ce qui vient d'arriver rend le cas moins
    urgent sans le rendre inexistant."""

    origin: CasePriority
    extend_to: datetime | None = None
    annotation: str | None = None
    priority: CasePriority | None = None  # adoptée si plus urgente ; abaissée si `downgrade`
    downgrade: bool = False


@dataclass(frozen=True)
class MarkCaseSeen(_Effect):
    """Le propriétaire a **ouvert** le cas — la mesure la plus précoce du pilote.

    Elle vise le cas vivant de cette personne, pas un identifiant : un rejeu recrée les cas avec de
    nouveaux identifiants, et un geste qui pointerait vers l'ancien ne retrouverait rien. Il y a au
    plus un cas vivant par personne — c'est un invariant de l'arbitrage, et il suffit."""

    at: datetime
    by_account_id: UUID


@dataclass(frozen=True)
class ResolveCase(_Effect):
    """Le responsable a dit ce qui s'est passé. **L'issue est choisie, jamais déduite.**

    C'est de là que vient toute la calibration : sans issue humaine, on ne saurait pas distinguer
    une intuition juste d'une intuition fausse, et le taux de justesse mesurerait le vide."""

    at: datetime
    by_account_id: UUID
    outcome: str


@dataclass(frozen=True)
class RecordContactAttempt(_Effect):
    """L'effort, écrit **avant** que l'application perde la main.

    `attempt_id` vient du fait : généré une fois à l'émission, il rend l'écriture idempotente au
    rejeu. Le cas visé, lui, est retrouvé par la personne — un rejeu recrée les cas avec de
    nouveaux identifiants."""

    attempt_id: UUID
    channel: str
    at: datetime
    by_account_id: UUID


@dataclass(frozen=True)
class ResolveContactAttempt(_Effect):
    """« Voilà comment ça s'est passé » — et, s'il l'a écrit, ce que le responsable fera ensuite.

    `commitment` porte sur **son geste**, jamais sur la personne : c'est ce qui fait qu'il n'existe
    toujours aucun endroit où écrire quelque chose sur quelqu'un."""

    attempt_id: UUID
    result: str
    at: datetime
    commitment: str | None = None


@dataclass(frozen=True)
class Neutralise(_Effect):
    starts_at: datetime
    expected_return_at: datetime
    role: str | None = None


@dataclass(frozen=True)
class Extinguish(_Effect):
    cause: ExtinguishCause
    at: datetime


@dataclass(frozen=True)
class ExcludeForever(_Effect):
    cause: ExclusionCause
    at: datetime


@dataclass(frozen=True)
class RecordMemory(_Effect):
    """La mémoire du lien — restituée au référent seul, jamais agrégée par membre."""

    at: datetime
    item: str


@dataclass(frozen=True)
class ScheduleCheck(_Effect):
    """Une échéance. Quand elle tombera, le worker écrira un `CHECK_FIRED` au ledger — c'est
    ainsi que le temps entre dans le moteur sans casser la rejouabilité.

    `payload` voyage avec l'échéance et se retrouve dans le fait émis. C'est ce qui permet à
    l'interpreter du tir de rester **pur** : tout ce dont il aura besoin dans trois semaines — le
    groupe concerné, la cadence choisie, la date de la dernière parole — est écrit maintenant, au
    moment où on le sait, plutôt que relu plus tard dans un état qui aura bougé."""

    at: datetime
    kind: str
    payload: Mapping[str, Any] = _NO_PAYLOAD


@dataclass(frozen=True)
class CancelScheduledChecks(_Effect):
    """« Ne me relancez plus » — le membre reprend la main sur son propre rythme."""

    kind: str | None = None  # None = toutes


@dataclass(frozen=True)
class CoverageSignal(_Effect):
    """Un trou dans le dispositif, adressé au responsable et au pasteur — jamais au référent.

    Sa sortie n'est pas un contact mais une **désignation** : il ne s'agit pas d'aller voir
    quelqu'un, il s'agit que quelqu'un lui soit donné."""

    gap: CoverageGap
    at: datetime


ProposedEffect = (
    OpenCase
    | EnrichCase
    | MarkCaseSeen
    | ResolveCase
    | RecordContactAttempt
    | ResolveContactAttempt
    | Neutralise
    | Extinguish
    | ExcludeForever
    | RecordMemory
    | ScheduleCheck
    | CancelScheduledChecks
    | CoverageSignal
)
