"""« Voici ce que Dorea aurait signalé cette semaine. »

La sortie du rodage. Pendant que l'église observe, tout est détecté et rien n'est émis — mais le
silence ne suffirait pas : une église qui ne voit rien pendant six semaines conclut que le produit
ne fonctionne pas, et elle a raison de le conclure. Le rapport est ce qui rend le rodage lisible.

**À qui, et pourquoi lui.** Au pasteur, pas aux responsables. C'est justement le point du rodage :
personne n'est encore chargé de rien. Le pasteur regarde ce que le moteur aurait dit, décide si ça
lui ressemble, et c'est lui qui décidera de laisser Dorea parler.

**Ce que le rapport ne fait pas.** Il ne classe pas les personnes, il ne note rien, il ne propose
aucune action. Il rend ce qui a été détecté, dans l'ordre de l'arbitrage — c'est-à-dire l'ordre où
ces cas seraient sortis si l'église parlait. Rien de plus : le rodage sert à décider si le moteur
voit juste, pas à faire du soin en cachette.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.iam.domain.permissions import Permission
from app.contexts.notifications.application.notifier import Notifier, PushNotification
from app.contexts.watch.application.ports import RegimeStore, SignalStore
from app.contexts.watch.application.referent_ports import PeopleDirectory
from app.contexts.watch.domain.regime import HeldReason, TenantRegime
from app.contexts.watch.domain.signal import priority_rank


@dataclass(frozen=True)
class WouldHaveSignalled:
    """Un cas que l'église aurait reçu. Sa **raison** est celle qui aurait été affichée."""

    subject_id: UUID
    reason: str
    origin: str
    detected_at: datetime
    owner_account_id: UUID | None


@dataclass(frozen=True)
class ShadowReport:
    regime: TenantRegime
    cases: tuple[WouldHaveSignalled, ...] = ()

    @property
    def is_observing(self) -> bool:
        return self.regime is TenantRegime.SHADOW

    @property
    def count(self) -> int:
        return len(self.cases)


class BuildShadowReport:
    def __init__(
        self,
        signals: SignalStore,
        regimes: RegimeStore,
        access: GroupAccessPolicy | None = None,
    ) -> None:
        self._signals = signals
        self._regimes = regimes
        self._access = access

    async def execute(
        self, *, tenant_id: UUID, actor_account_id: UUID | None = None
    ) -> ShadowReport:
        """Autorité **église-entière** : ce rapport nomme des personnes de toute l'église.

        Même garde que la liste de soin — un responsable de cellule n'a pas à lire ce que le
        moteur aurait dit des membres d'un autre groupe."""
        if self._access is not None and actor_account_id is not None:
            await self._access.ensure_church_wide(
                actor_account_id=actor_account_id,
                tenant_id=tenant_id,
                permission=Permission.VIEW_PASTORAL_ALERTS,
            )
        regime = await self._regimes.regime_of(tenant_id)
        if regime is not TenantRegime.SHADOW:
            # Une église qui parle n'a pas de rapport d'ombre : ses cas sont sur des écrans.
            return ShadowReport(regime=regime)

        held = [
            case
            for case in await self._signals.held_cases(tenant_id=tenant_id)
            if case.held_reason == HeldReason.SHADOW.value
        ]
        # L'ordre de l'arbitrage : celui dans lequel ces cas seraient sortis. Le pasteur lit donc
        # la file telle qu'elle aurait été, pas un tas trié par date d'insertion.
        held.sort(key=lambda case: (priority_rank(case.priority), case.opened_at))
        return ShadowReport(
            regime=regime,
            cases=tuple(
                WouldHaveSignalled(
                    subject_id=case.subject_id,
                    reason=case.reason,
                    origin=case.origin.value,
                    detected_at=case.opened_at,
                    owner_account_id=case.owner_account_id,
                )
                for case in held
            ),
        )


class LetDoreaSpeak:
    """Sortir du rodage — **le moment où l'église accepte que Dorea parle à ses responsables**.

    C'est un acte de gouvernance, pas une lecture pastorale : quelqu'un engage l'église à recevoir
    des cas sur ses membres, et à en répondre. On exige donc l'autorité qui enrôle le personnel
    (`MANAGE_STAFF`, c'est-à-dire le propriétaire de l'église), la même famille que le mandat de
    diffusion élargie — parler au nom d'un corps, dans les deux cas.

    Rien n'est rétroactif : les cas retenus pendant l'observation restent retenus. Ils ont été
    détectés dans un régime où personne n'était chargé de rien, et les déverser d'un coup sur des
    responsables qui découvrent le produit serait exactement l'inverse de ce que le rodage protège.
    Ce qui suit la décision sortira normalement.
    """

    def __init__(
        self, regimes: RegimeStore, access: GroupAccessPolicy, *, clock
    ) -> None:
        self._regimes = regimes
        self._access = access
        self._clock = clock

    async def execute(
        self,
        *,
        tenant_id: UUID,
        actor_account_id: UUID,
        regime: TenantRegime = TenantRegime.ASSISTED,
    ) -> TenantRegime:
        await self._access.ensure_church_wide(
            actor_account_id=actor_account_id,
            tenant_id=tenant_id,
            permission=Permission.MANAGE_STAFF,
        )
        await self._regimes.set_regime(
            tenant_id=tenant_id,
            regime=regime,
            at=self._clock(),
            by_account_id=actor_account_id,
        )
        return regime


@dataclass(frozen=True)
class DigestSent:
    tenants: int  # églises en rodage
    notified: int  # celles où il y avait quelque chose à dire


class SendShadowDigest:
    """L'envoi hebdomadaire — **la seule chose que Dorea dise à une église en rodage**.

    Sans lui, le rodage serait indiscernable d'un produit en panne : six semaines de silence, et le
    pasteur conclut que rien ne fonctionne. Il aurait raison de le conclure.

    **La cadence n'est pas ici.** Le service ne sait pas qu'il est hebdomadaire : c'est le cron qui
    le décide, comme pour les autres passes. Écrire « une fois par semaine » dans le code aurait
    demandé de mémoriser la date du dernier envoi — un état de plus, pour un rythme qui se règle
    très bien dans une ligne de crontab.

    **Une seule phrase, et un nombre.** Pas la liste des personnes : une notification qui nomme
    quelqu'un sur l'écran de verrouillage d'un téléphone est une fuite. Le pasteur ouvre le rapport
    s'il veut savoir qui.
    """

    def __init__(
        self,
        report: BuildShadowReport,
        people: PeopleDirectory,
        notifier: Notifier | None = None,
    ) -> None:
        self._report = report
        self._people = people
        self._notifier = notifier

    async def execute(self, *, tenant_id: UUID) -> DigestSent:
        report = await self._report.execute(tenant_id=tenant_id)
        if not report.is_observing:
            return DigestSent(tenants=0, notified=0)
        if report.count == 0 or self._notifier is None:
            # Rien détecté cette semaine : on ne notifie pas pour dire qu'il n'y a rien. Le
            # rapport reste consultable, et le silence d'une semaine calme est un vrai silence.
            return DigestSent(tenants=1, notified=0)

        pastors = await self._people.pastors(tenant_id)
        if not pastors:
            return DigestSent(tenants=1, notified=0)
        await self._notifier.notify(
            pastors,
            PushNotification(
                title="Dorea observe",
                body=(
                    f"{report.count} situation(s) auraient été signalées cette semaine. "
                    "Ouvrez le rapport pour les voir."
                ),
                data={"type": "shadow_digest", "tenant_id": str(tenant_id)},
            ),
        )
        return DigestSent(tenants=1, notified=1)
