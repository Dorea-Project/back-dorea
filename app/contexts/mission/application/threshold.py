"""Le **seuil** — l'endroit exact où la veille commence.

> *La capsule va partout. La veille s'engage là où un référent existe.*

L'évangélisation n'a pas de frontière ; le suivi en a une. Il suppose un humain nommé, capable
de décrocher son téléphone. La promesse de Dorea — *« si tu as besoin, quelqu'un répond »* — ne
peut pas être faite à quelqu'un pour qui il n'y a personne. Ce n'est pas un abandon : c'est ne
pas promettre ce qu'on ne peut pas tenir.

Trois seuils, **un seul** fait entrer dans la veille :

| Seuil | Effet |
|---|---|
| Atteint — a vu, a réagi | **aucun.** Ni fait, ni personne en base |
| **Accepté — laisse un contact** | une **personne** en base, `INVITED`, référent = l'inviteur |
| Venu — franchit la porte | statut `VISITOR`, la veille s'épaissit |

**Dès qu'un contact existe, c'est une personne, pas un agrégat parallèle.** Tant que le chercheur
vivait dans sa propre table, trois choses cassaient : la cascade de référent ne travaille que sur
des personnes, la couverture les ignorait — c'est-à-dire précisément les plus fragiles — et le
passage à membre était une *migration*, donc la perte de l'histoire de celui dont l'histoire
compte le plus : quelqu'un l'a amené.

Le statut change. **L'identité, jamais.**
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.iam.application.commands.admit_person import AdmitPerson
from app.contexts.iam.domain.enums import AccountCreationSource
from app.contexts.mission.domain.aggregates import MissionLink
from app.contexts.watch.application.intake import Intake, warn_if_disconnected
from app.contexts.watch.application.referent_ports import (
    GroupDirectory,
    ReferentOverrideRepository,
)
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.referent import ReferentOrigin, ReferentOverride
from app.contexts.watch.domain.registry import MISSION


@dataclass(frozen=True)
class CrossedThreshold:
    account_id: UUID
    reused_existing: bool  # cette personne était déjà connue de l'église


class CrossTheThreshold:
    """Fait exister la personne, lui donne un référent, et l'annonce au moteur.

    Les trois gestes sont indissociables : une personne sans référent est une promesse qu'on ne
    peut pas tenir, et un référent sans fait au ledger est un lien que rien ne déclenchera.
    """

    def __init__(
        self,
        admit: AdmitPerson,
        overrides: ReferentOverrideRepository,
        groups: GroupDirectory,
        intake: Intake | None = None,
    ) -> None:
        warn_if_disconnected("mission", intake)
        self._admit = admit
        self._overrides = overrides
        self._groups = groups
        self._intake = intake

    async def execute(
        self,
        *,
        link: MissionLink,
        name: str,
        phone: str | None,
        now: datetime,
    ) -> CrossedThreshold:
        account_id, reused = await self._person(
            tenant_id=link.tenant_id, name=name, phone=phone, now=now
        )
        await self._set_inviter_as_referent(link, account_id, now)
        await self._announce(link, account_id, now)
        return CrossedThreshold(account_id=account_id, reused_existing=reused)

    async def _person(
        self, *, tenant_id: UUID, name: str, phone: str | None, now: datetime
    ) -> tuple[UUID, bool]:
        """Confié à IAM — **un seul écrivain du statut de personne**.

        `mission` ne construit plus d'appartenance et ne nomme plus de palier : il dit qu'une
        personne se présente, IAM décide où elle entre. C'est ce qui empêche trois modules
        d'inventer chacun leur règle d'entrée."""
        first, _, last = name.strip().partition(" ")
        return await self._admit.execute(
            tenant_id=tenant_id,
            phone=phone,
            first_name=first,
            last_name=last.strip() or None,
            creation_source=AccountCreationSource.MISSION_CAPSULE,
            actor_account_id=None,  # personne d'autre : c'est son propre geste
            now=now,
        )

    async def _set_inviter_as_referent(
        self, link: MissionLink, account_id: UUID, now: datetime
    ) -> None:
        """L'inviteur devient le référent — via l'origine `INVITER` de la cascade.

        Aucune ligne n'a été ajoutée au résolveur pour ce cas : c'est **précisément** celui pour
        lequel cette origine existe. Pour une capsule de groupe, c'est le responsable du groupe."""
        inviter = link.inviter_account_id
        if inviter is None and link.inviter_group_id is not None:
            inviter = await self._groups.active_leader_of(
                link.inviter_group_id, link.tenant_id
            )
        if inviter is None or inviter == account_id:
            return  # personne à désigner, ou la personne s'est invitée elle-même

        await self._overrides.add(
            ReferentOverride(
                id=uuid4(),
                tenant_id=link.tenant_id,
                person_id=account_id,
                referent_person_id=inviter,
                origin=ReferentOrigin.INVITER,
                started_at=now,
                started_by_account_id=inviter,
            )
        )

    async def _announce(
        self, link: MissionLink, account_id: UUID, now: datetime
    ) -> None:
        """Un `SELF_DECLARATION` — parce que c'est **elle** qui a tendu la main en retour.

        Le consentement n'est pas une case cochée : c'est le geste de laisser un contact. On le
        matérialise comme tel, avec sa portée exacte."""
        if self._intake is None:
            return
        await self._intake.submit(
            Fact(
                fact_id=uuid4(),
                tenant_id=link.tenant_id,
                occurred_at=now,
                recorded_at=now,
                source=MISSION,
                kind=FactKind.SELF_DECLARATION,
                subject_kind=SubjectKind.PERSON,
                subject_id=account_id,
                payload={"kind": "capsule_accepted", "link_id": str(link.id)},
                consent=ConsentProof(
                    given_by=account_id,
                    scope=ConsentScope.BE_WATCHED,
                    given_at=now,
                ),
            )
        )
