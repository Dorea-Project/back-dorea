"""Le contrat de fait — la **seule** porte d'entrée du moteur de veille.

Tout ce qui entre dans l'engine est un `Fact`. Rien d'autre n'existe à l'entrée : une source
propose, l'engine décide, une sortie restitue. Aucun greffon n'écrit jamais l'état d'un signal,
d'une neutralisation ou d'un épisode.

**La protection est dans ce que ce module ne nomme pas.** L'asymétrie fondatrice — la parole est
un signal, le silence n'est rien — n'est pas une règle de gestion qu'on applique : c'est
l'absence de `DID_NOT_REACT`, `DID_NOT_OPEN`, `MEMBER_INACTIVE` dans `FactKind`. Un développeur
futur, bien intentionné, ne peut pas l'oublier — le type qui la violerait n'existe pas. Même
chose pour la donnée financière et pour le sujet déduit d'une analyse de contenu.

Un `Fact` est **immuable** (gelé) : le ledger est append-only, et rejouer le passé doit produire
exactement le même état. Rien de ce qui est écrit ici ne se corrige — on ajoute un fait qui dit
autre chose.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

SourceId = str


class FactKind(StrEnum):
    """Ce qu'une source a le droit de dire. Registre extensible — **sous filtre** (§6).

    Chaque membre décrit quelque chose **qui a eu lieu**. Aucun ne décrit une omission : c'est la
    condition structurelle pour que le produit ne devienne jamais un outil de surveillance.
    """

    PRESENCE_RECORDED = "presence_recorded"  # présence positive, toute modalité
    # **Quelqu'un entre dans un groupe.** Un acte, comme tous les autres membres de cette liste —
    # et le seul moyen de regarder celui qui n'est **jamais** venu. Sans lui, la détection
    # d'absence ne s'arme qu'au premier retour : le nouveau inscrit qu'on ne revoit pas reste
    # invisible, alors que c'est précisément la personne qu'il fallait voir.
    JOINED_GROUP = "joined_group"
    GESTURE_DONE = "gesture_done"  # visite, appel abouti, aide déclarée
    LIFE_EVENT_ANNOUNCED = "life_event_announced"  # annonce à sujet (le rôle est au payload)
    LIFE_EVENT_PRIVATE = "life_event_private"  # événement enregistré sans publication
    SELF_DECLARATION = "self_declaration"  # « rappelez-moi », « priez pour moi », rythme choisi
    # « je pense à quelqu'un » — **un seul** type pour l'intuition du responsable et le
    # signalement du membre. Ils sont structurellement identiques : quelqu'un qui n'est pas le
    # sujet signale une inquiétude. La seule différence — le rôle de l'émetteur — se dissout
    # dans la résolution du propriétaire : si l'émetteur *est* le référent, le cas lui revient ;
    # sinon il revient au référent, sans que l'émetteur soit nommé. Deux types auraient divergé
    # dans six mois, et le cas du responsable n'est que le cas général replié sur lui-même.
    THIRD_PARTY_CONCERN = "third_party_concern"
    GRATITUDE_DEPOSITED = "gratitude_deposited"  # signe de vie positif
    APPOINTMENT_REQUESTED = "appointment_requested"  # + payload : décliné / annulé / non honoré
    QUALIFICATION_SET = "qualification_set"  # qualification manuelle d'absence
    OCCURRENCE_ACKNOWLEDGED = "occurrence_acknowledged"  # « pas de rencontre cette semaine »
    GROUP_TEMPERATURE = "group_temperature"  # compagnon collectif — agrégé, jamais individuel
    CHECK_FIRED = "check_fired"  # une échéance posée par l'engine est arrivée à terme
    # --- Les gestes du responsable, **sur un cas** -------------------------------------------
    #
    # Le journal ne contenait que ce que les sources disent du monde ; ce qu'un responsable
    # *faisait* vivait uniquement sur la projection. Une reprojection l'effaçait donc sans pouvoir
    # le reconstruire : les issues qu'il avait conclues, le premier regard, le premier contact —
    # c'est-à-dire les deux métriques du pilote et toute la matière dont la calibration a besoin.
    #
    # Ce sont des **actes**, au même titre qu'une présence : quelqu'un a fait quelque chose, à une
    # date, et l'a signé. Rien ici ne décrit une omission.
    CASE_SEEN = "case_seen"  # « je l'ai ouvert » — la mesure la plus précoce du pilote
    CASE_CLOSED = "case_closed"  # « voilà ce qui s'est passé » — l'issue, choisie, jamais déduite
    # L'effort, écrit **au départ** : on sort vers WhatsApp ou le téléphone et on ne revient
    # pas toujours. Sans cette trace posée avant de perdre la main, le produit conclurait à un
    # échec de veille là où il y a eu un appel de vingt minutes.
    CONTACT_ATTEMPTED = "contact_attempted"
    CONTACT_ANSWERED = "contact_answered"  # « voilà comment ça s'est passé », et ce que je ferai


# Le **temps lui-même entre par le ledger** : `CHECK_FIRED` est ce qui rend l'évaluation des
# échéances rejouable. Un interpreter ne lit jamais l'horloge — sinon rejouer demain donnerait un
# autre résultat, et l'invariant de déterminisme tomberait.


# Formes de `kind` interdites — vérifiées à l'enregistrement d'une source **et** par la suite
# d'invariants qui balaie l'enum entier. Ce n'est pas une convention de nommage : c'est le
# grillage qui empêche d'ajouter un jour `MEMBER_INACTIVE_ON_APP` « juste pour voir ».
FORBIDDEN_KIND_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(^|_)(did_not|not_|never_|missing|inactive|unread|unopened|ignored)", "inaction"),
    (r"(donation|contribution|tithe|offering|payment|pledge|amount|fee)", "financier"),
    (r"(inferred|predicted|detected_from|analyz|analys|sentiment|score)", "inféré"),
    # **Télémétrie d'usage.** Le complément indispensable de « inaction » : on interdit déjà de
    # dire l'absence, il faut interdire de la **dériver d'une fréquence**. Sans cette famille,
    # `COMPANION_OPENED` passerait le filtre — et « il l'ouvre moins souvent » redeviendrait un
    # signal, déguisé en donnée positive. Ouvrir une application n'est pas un acte de vie.
    (r"(opened|open_count|session_start|login|sign_in|screen_view|app_usage|last_seen|"
     r"heartbeat|activity_ping)", "télémétrie"),
)


def forbidden_reason(kind_value: str) -> str | None:
    """Renvoie la famille interdite si ce nom de kind en relève, sinon None."""
    for pattern, family in FORBIDDEN_KIND_PATTERNS:
        if re.search(pattern, kind_value, re.IGNORECASE):
            return family
    return None


class SubjectKind(StrEnum):
    """Sur **qui**, ou sur **quoi**, porte le fait.

    `GROUP` n'est pas une commodité : c'est ce qui permet au compagnon collectif d'exister sans
    qu'aucune donnée individuelle ne soit jamais écrite."""

    PERSON = "person"
    GROUP = "group"


class ConsentScope(StrEnum):
    """À quoi la personne a consenti."""

    BE_NAMED = "be_named"  # être nommée dans ce qui est publié
    BE_WATCHED = "be_watched"  # être suivie (rythme choisi, « rappelez-moi »)
    SPEAK_FOR_ANOTHER = "speak_for_another"  # porter le souci de quelqu'un d'autre


@dataclass(frozen=True)
class ConsentProof:
    """Le consentement est un **type**, pas une case à cocher.

    Un `FactKind` qui l'exige ne peut pas entrer sans lui — le refus est à l'intake, pas dans une
    revue de code."""

    given_by: UUID
    scope: ConsentScope
    given_at: datetime
    revocable: bool = True


# Les kinds qui **exigent** une preuve de consentement à l'intake.
# `LIFE_EVENT_ANNOUNCED` n'y figure pas volontairement : l'accord du sujet est une garde du
# contexte Annonces, en amont — un rôle intime sans accord n'émet simplement jamais de fait.
CONSENT_REQUIRED: frozenset[FactKind] = frozenset(
    {
        FactKind.SELF_DECLARATION,
        FactKind.THIRD_PARTY_CONCERN,
        FactKind.LIFE_EVENT_PRIVATE,
    }
)


# La clé du payload qui dit **qui a posé le geste**. À défaut, la matérialisation retombe sur le
# sujet lui-même — ce qui est juste pour une auto-déclaration (elle *est* un acte du sujet) et faux
# pour tout ce qui est posé sur quelqu'un.
ACTOR_KEY = "actor_account_id"


# Les kinds dont l'interprétation peut aboutir à un **retrait définitif de la veille**. Pour eux,
# l'acteur n'est pas une commodité d'audit : sans lui, le repli sur le sujet enregistrait le
# **défunt** comme ayant déclaré sa propre exclusion. Une source enregistrée pour l'un de ces kinds
# sans exiger l'acteur fait échouer le démarrage de l'application.
ACTOR_REQUIRED: frozenset[FactKind] = frozenset({FactKind.LIFE_EVENT_ANNOUNCED})


# Les gestes posés **par un humain sur un cas**. Deux règles les distinguent de tout le reste :
#
# - ils exigent l'acteur et le cas visé — un geste anonyme n'est pas un geste ;
# - ils **traversent l'exclusion**. Le filtre « personne retirée de la veille » protège des
#   sources : plus rien n'entre *sur* quelqu'un qui est mort ou qui a demandé qu'on cesse. Mais
#   fermer le cas d'un défunt est justement l'acte qu'on attend du responsable, et le lui refuser
#   laisserait le cas ouvert pour toujours sur l'écran de quelqu'un.
CASE_ACTS: frozenset[FactKind] = frozenset(
    {
        FactKind.CASE_SEEN,
        FactKind.CASE_CLOSED,
        FactKind.CONTACT_ATTEMPTED,
        FactKind.CONTACT_ANSWERED,
    }
)


# Ce que certains kinds exigent du payload, **quelle que soit la source**. Le registre porte les
# clés par source ; ceci porte celles qui tiennent au type de fait lui-même.
KIND_REQUIRED_KEYS: dict[FactKind, frozenset[str]] = {
    FactKind.CASE_SEEN: frozenset({"signal_id", ACTOR_KEY}),
    FactKind.CASE_CLOSED: frozenset({"signal_id", ACTOR_KEY, "outcome"}),
    FactKind.CONTACT_ATTEMPTED: frozenset({"attempt_id", "signal_id", ACTOR_KEY, "channel"}),
    FactKind.CONTACT_ANSWERED: frozenset({"attempt_id", ACTOR_KEY, "result"}),
}


_EMPTY: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class Fact:
    """Un fait admis au ledger. Immuable, daté deux fois, attribué à une source enregistrée.

    `occurred_at` est la date de l'**événement** ; `recorded_at` celle de l'ingestion. Les deux
    sont nécessaires : la première fait courir les durées (une saisie tardive ne décale pas
    l'histoire), la seconde donne l'ordre du rejeu et choisit la version d'interpreter.
    """

    fact_id: UUID
    tenant_id: UUID  # Dorea est multi-église : sans lui aucune projection n'est isolable
    occurred_at: datetime
    recorded_at: datetime
    source: SourceId
    kind: FactKind
    subject_kind: SubjectKind
    subject_id: UUID
    payload: Mapping[str, Any] = field(default=_EMPTY)
    payload_version: int = 1
    consent: ConsentProof | None = None
    seq: int | None = None  # ordre **total** du ledger — assigné à l'écriture, jamais par la source

    @property
    def is_about_person(self) -> bool:
        return self.subject_kind is SubjectKind.PERSON

    def requires_consent(self) -> bool:
        return self.kind in CONSENT_REQUIRED

    def sealed(self, seq: int) -> Fact:
        """Le même fait, scellé à sa place dans le ledger."""
        return replace(self, seq=seq)
