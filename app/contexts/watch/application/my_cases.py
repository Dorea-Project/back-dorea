"""La file d'un responsable, et la clôture d'un cas.

Deux gestes, et ils sont le minimum pour que tout ce qui précède serve à quelque chose : un
moteur qui détecte parfaitement et que personne ne peut lire ne veille sur rien.

**Ouvrir un cas est un acte mesuré.** `SeeCase` pose `first_seen_at`, qui alimente le taux
d'ignorés — le seul indicateur du pilote qui *anticipe* l'abandon. Tous les autres constatent.

**Fermer un cas est un acte humain.** La règle vit dans l'agrégat, pas ici : ce service ne
saurait pas la contourner même s'il le voulait. Il fournit seulement le `closed_by_account_id`
que l'agrégat exige — et il refuse qu'un tiers ferme le cas d'un autre.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.contexts.watch.application.ports import SignalStore
from app.contexts.watch.domain.errors import CaseNotFoundError, NotYourCaseError
from app.contexts.watch.domain.signal import Signal, SignalOutcome


@dataclass(frozen=True)
class CaseDTO:
    """Ce qu'un responsable lit. Le sujet est un identifiant : la fiche vit ailleurs."""

    id: UUID
    subject_id: UUID
    reason: str
    annotations: tuple[str, ...]
    previous_case_note: str | None
    occurrence_number: int
    priority: str
    status: str
    opened_at: object
    first_seen_at: object
    first_contact_at: object

    @classmethod
    def of(cls, signal: Signal) -> CaseDTO:
        return cls(
            id=signal.id,
            subject_id=signal.subject_id,
            reason=signal.reason,
            annotations=tuple(signal.annotations),
            # « Cas précédent clos le 3 février — repris contact, situation suivie. »
            previous_case_note=signal.previous_case_note,
            occurrence_number=signal.occurrence_number,
            priority=signal.priority.value,
            status=signal.status.value,
            opened_at=signal.opened_at,
            first_seen_at=signal.first_seen_at,
            first_contact_at=signal.first_contact_at,
        )


class ListMyCases:
    def __init__(self, signals: SignalStore) -> None:
        self._signals = signals

    async def execute(self, *, account_id: UUID, tenant_id: UUID) -> list[CaseDTO]:
        cases = await self._signals.cases_of_owner(
            account_id=account_id, tenant_id=tenant_id
        )
        return [CaseDTO.of(c) for c in cases]


class _OwnedCase:
    """Socle : charger le cas, et vérifier qu'il est bien sur les épaules de celui qui agit."""

    def __init__(self, signals: SignalStore, *, clock) -> None:
        self._signals = signals
        self._clock = clock

    async def _load(self, *, signal_id: UUID, tenant_id: UUID, actor_account_id: UUID) -> Signal:
        case = await self._signals.get_case(signal_id=signal_id, tenant_id=tenant_id)
        if case is None:
            raise CaseNotFoundError("Ce cas n'existe pas.", details={"case": str(signal_id)})
        # Un cas sans propriétaire est prenable — c'est justement le trou qu'on veut voir se
        # combler. Un cas confié à quelqu'un d'autre ne l'est pas : deux responsables sur la
        # même personne, c'est le double appel du même soir que tout le module évite.
        if case.owner_account_id not in (None, actor_account_id):
            raise NotYourCaseError(
                "Ce cas est confié à quelqu'un d'autre.", details={"case": str(signal_id)}
            )
        return case


class SeeCase(_OwnedCase):
    """Le responsable a **ouvert** le cas. La mesure la plus précoce dont dispose le pilote."""

    async def execute(
        self, *, signal_id: UUID, tenant_id: UUID, actor_account_id: UUID
    ) -> CaseDTO:
        case = await self._load(
            signal_id=signal_id, tenant_id=tenant_id, actor_account_id=actor_account_id
        )
        case.see(at=self._clock())
        await self._signals.save_case(case)
        return CaseDTO.of(case)


class CloseCase(_OwnedCase):
    """Fermer avec une issue **choisie**, jamais déduite.

    Aucune issue n'est proposée par défaut : le responsable dit ce qui s'est passé, et c'est de
    là que vient la calibration. Une valeur pré-cochée deviendrait le rangement par défaut, et
    la mesure ne mesurerait plus que la paresse du formulaire."""

    async def execute(
        self,
        *,
        signal_id: UUID,
        tenant_id: UUID,
        actor_account_id: UUID,
        outcome: SignalOutcome,
    ) -> CaseDTO:
        case = await self._load(
            signal_id=signal_id, tenant_id=tenant_id, actor_account_id=actor_account_id
        )
        # L'agrégat refuse tout seul ce qui n'a pas lieu d'être : issue absorbante, transition
        # inexistante, clôture sans humain. On ne rejoue aucune de ces règles ici.
        case.close(
            outcome=outcome, at=self._clock(), closed_by_account_id=actor_account_id
        )
        await self._signals.save_case(case)
        return CaseDTO.of(case)
