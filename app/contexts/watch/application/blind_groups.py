"""Le groupe **aveugle** — celui dont on ne sait rien, et dont le silence n'est pas un signal.

Un groupe qui a déclaré un rythme mais dont aucune rencontre n'est jamais saisie met le moteur dans
l'état le plus trompeur qui soit : **il ne détecte rien, et son écran vide ressemble à la santé.**
Personne n'y est jamais absent, puisqu'il n'y a aucune rencontre à manquer.

C'est pourquoi ce défaut porte sur le **groupe**, jamais sur une personne. La faute n'est à
personne en particulier : personne ne saisit, donc le dispositif ne voit pas. Ouvrir des cas sur
les membres d'un groupe qui ne saisit rien serait exactement l'erreur inverse — accuser des gens
d'un silence qui est le nôtre.

**On compte les occurrences attendues, pas les jours.** Un groupe mensuel dont la dernière
rencontre saisie remonte à six semaines est parfaitement normal ; une cellule hebdomadaire dans le
même cas ne l'est pas. Le seuil est donc le même que celui de l'absence, et pour la même raison :
c'est le rythme du groupe qui donne son sens au temps qui passe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.attendance.domain.cadence import expected_occurrences
from app.contexts.watch.application.referent_ports import (
    CoverageGapStore,
    WatchParameterRepository,
)
from app.contexts.watch.domain.coverage import CoverageGapRecord
from app.contexts.watch.domain.effects import CoverageGap, CoverageScope
from app.contexts.watch.domain.parameters import WatchParam


@dataclass(frozen=True)
class GroupWatchRhythm:
    """Un groupe qui attend des rencontres, et la dernière qu'on lui connaisse."""

    group_id: UUID
    label: str
    cadence: object  # `GroupCadence` — la règle, jamais le roster
    last_gathering_at: datetime | None


@dataclass(frozen=True)
class RhythmlessGroup:
    """Un groupe qui a des membres et n'a jamais dit quand il se réunit."""

    group_id: UUID
    label: str
    member_count: int


@dataclass(frozen=True)
class BlindGroups:
    detected: int
    recorded: int  # ceux qui n'étaient pas déjà consignés — un rappel nocturne devient du bruit
    # Ceux d'un cran avant : sans cadence du tout. Comptés à part parce que l'action du pasteur
    # n'est pas la même — « faites saisir vos rencontres » d'un côté, « dites quand vous vous
    # réunissez » de l'autre.
    rhythmless: int = 0


class DetectBlindGroups:
    def __init__(
        self,
        rhythms,
        gaps: CoverageGapStore,
        params: WatchParameterRepository,
        *,
        clock,
        id_factory=uuid4,
    ) -> None:
        self._rhythms = rhythms
        self._gaps = gaps
        self._params = params
        self._clock = clock
        self._new_id = id_factory

    async def execute(self, *, tenant_id: UUID) -> BlindGroups:
        now = self._clock()
        threshold = await self._params.get_int(
            tenant_id, WatchParam.ABSENCE_OCCURRENCES_THRESHOLD
        )

        detected = recorded = 0
        for rhythm in await self._rhythms.watched_groups(tenant_id=tenant_id):
            missed = self._expected_since(rhythm, now)
            if missed < threshold:
                continue
            detected += 1
            if await self._gaps.record_once(self._record(rhythm, tenant_id, missed, now)):
                recorded += 1

        return BlindGroups(
            detected=detected,
            recorded=recorded,
            rhythmless=await self._record_rhythmless(tenant_id, now),
        )

    async def _record_rhythmless(self, tenant_id: UUID, now: datetime) -> int:
        """Les groupes qui n'ont **jamais déclaré de rythme**, et qui ont des membres.

        La boucle du dessus part des cadences : par construction, elle ne peut pas voir un groupe
        qui n'en a pas. C'est le trou que ce passage ferme — et il est plus grave que celui qu'elle
        couvre, parce qu'aucune détection ne s'arme jamais dans un tel groupe.

        « Qui a des membres » est la condition : un groupe fraîchement créé et encore vide n'a
        rien à déclarer, et le signaler ferait du défaut de couverture un reproche de démarrage.
        """
        if not hasattr(self._rhythms, "groups_without_rhythm"):
            return 0  # adaptateur d'ancienne génération : on ne casse rien
        recorded = 0
        for group in await self._rhythms.groups_without_rhythm(tenant_id=tenant_id):
            created = await self._gaps.record_once(
                CoverageGapRecord(
                    id=self._new_id(),
                    tenant_id=tenant_id,
                    scope=CoverageScope.GROUP,
                    subject_id=group.group_id,
                    gap=CoverageGap.NO_RHYTHM,
                    reason=(
                        f"{group.label} n'a déclaré aucun rythme de rencontre : ses "
                        f"{group.member_count} membres ne sont attendus nulle part, et le moteur "
                        "n'y verra jamais personne manquer."
                    ),
                    observed_at=now,
                )
            )
            recorded += 1 if created else 0
        return recorded

    def _expected_since(self, rhythm: GroupWatchRhythm, now: datetime) -> int:
        """Combien de rencontres auraient dû être saisies depuis la dernière qu'on connaisse.

        Sans aucune rencontre jamais saisie, on compte depuis le début de la cadence : un groupe
        qui n'a **jamais** rien saisi est le cas le plus aveugle des deux."""
        since = rhythm.last_gathering_at or rhythm.cadence.active_from
        return len([o for o in expected_occurrences(rhythm.cadence, since, now) if o > since])

    def _record(
        self, rhythm: GroupWatchRhythm, tenant_id: UUID, missed: int, now: datetime
    ) -> CoverageGapRecord:
        never = rhythm.last_gathering_at is None
        reason = (
            f"Aucune rencontre n'a jamais été saisie pour {rhythm.label} "
            f"({missed} attendues depuis)."
            if never
            else f"Aucune rencontre saisie pour {rhythm.label} depuis {missed} occurrences."
        )
        return CoverageGapRecord(
            id=self._new_id(),
            tenant_id=tenant_id,
            # Le défaut porte sur le **groupe** : ce n'est pas une personne qui manque, c'est le
            # regard qui n'existe pas.
            scope=CoverageScope.GROUP,
            subject_id=rhythm.group_id,
            gap=CoverageGap.BLIND,
            reason=reason,
            observed_at=now,
        )
