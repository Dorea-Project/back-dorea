"""Faire entrer au journal ce qu'un responsable vient de faire.

Le pendant, côté écriture, de `CaseSeenV1` et `CaseClosedV1` : l'écran du responsable ne mute plus
la projection, il **émet un fait**, et la chaîne normale suit — interpréter, arbitrer, écrire. Le
geste devient donc rejouable comme tout le reste, et une reprojection ne l'efface plus.

Deux précisions qui font la sûreté de ce chemin :

- **l'identité du fait est dérivée du geste** (`case + acte`), donc rejouer ou double-cliquer
  n'écrit rien deux fois. Un cas ne peut être « vu pour la première fois » qu'une fois ;
- **l'autorité est vérifiée avant**, par `_OwnedCase`. L'interpreter ne la rejoue pas : un fait
  admis au journal est un geste dont on a déjà établi qu'il avait le droit d'exister.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from app.contexts.watch.application.intake import Intake
from app.contexts.watch.domain.facts import Fact, FactKind, SubjectKind
from app.contexts.watch.domain.registry import CASE_ACTIONS
from app.contexts.watch.domain.signal import Signal, SignalOutcome

_FACT_NAMESPACE = uuid5(NAMESPACE_URL, "dorea:watch:case_act")


def fact_id_for(signal_id: UUID, act: FactKind) -> UUID:
    """Identité **dérivée** de (cas, acte) : on n'ouvre un cas pour la première fois qu'une fois."""
    return uuid5(_FACT_NAMESPACE, f"{signal_id}:{act.value}")


class RecordCaseAct:
    def __init__(self, intake: Intake, *, clock) -> None:
        self._intake = intake
        self._clock = clock

    async def seen(self, *, case: Signal, tenant_id: UUID, actor_account_id: UUID) -> None:
        await self._submit(
            case=case,
            tenant_id=tenant_id,
            actor_account_id=actor_account_id,
            kind=FactKind.CASE_SEEN,
        )

    async def closed(
        self,
        *,
        case: Signal,
        tenant_id: UUID,
        actor_account_id: UUID,
        outcome: SignalOutcome,
    ) -> None:
        await self._submit(
            case=case,
            tenant_id=tenant_id,
            actor_account_id=actor_account_id,
            kind=FactKind.CASE_CLOSED,
            extra={"outcome": outcome.value},
        )

    async def attempted(
        self,
        *,
        attempt_id: UUID,
        signal_id: UUID,
        subject_id: UUID,
        tenant_id: UUID,
        by_account_id: UUID,
        channel,
    ) -> None:
        """L'effort, écrit **avant** que l'application perde la main.

        `attempt_id` est généré ici et voyage dans le fait : c'est lui qui rend l'écriture
        idempotente au rejeu, sans quoi chaque reconstruction empilerait une tentative de plus."""
        now = self._clock()
        await self._emit(
            fact_id=uuid5(_FACT_NAMESPACE, f"{attempt_id}:{FactKind.CONTACT_ATTEMPTED.value}"),
            tenant_id=tenant_id,
            subject_id=subject_id,
            kind=FactKind.CONTACT_ATTEMPTED,
            at=now,
            payload={
                "attempt_id": str(attempt_id),
                "signal_id": str(signal_id),
                "actor_account_id": str(by_account_id),
                "channel": getattr(channel, "value", str(channel)),
            },
        )

    async def answered(
        self,
        *,
        attempt,
        subject_id: UUID,
        result,
        commitment: str | None,
        failed_attempts: int,
        origin: str | None,
    ) -> None:
        """Ce que le responsable rapporte — avec ce que le monde sait au moment où il le dit.

        Le décompte des tentatives sans réponse et l'origine du cas voyagent dans le fait : c'est
        ce qui permet à l'interpreter de décider seul de la péremption dure, sans rien relire."""
        now = self._clock()
        payload: dict[str, str] = {
            "attempt_id": str(attempt.id),
            "actor_account_id": str(attempt.by_account_id),
            "result": getattr(result, "value", str(result)),
            "failed_attempts": str(failed_attempts),
        }
        if origin is not None:
            payload["origin"] = origin
        if commitment and commitment.strip():
            payload["commitment"] = commitment.strip()
        await self._emit(
            fact_id=uuid5(_FACT_NAMESPACE, f"{attempt.id}:{FactKind.CONTACT_ANSWERED.value}"),
            tenant_id=attempt.tenant_id,
            subject_id=subject_id,
            kind=FactKind.CONTACT_ANSWERED,
            at=now,
            payload=payload,
        )

    async def _emit(
        self, *, fact_id: UUID, tenant_id: UUID, subject_id: UUID, kind: FactKind, at, payload
    ) -> None:
        await self._intake.submit(
            Fact(
                fact_id=fact_id,
                tenant_id=tenant_id,
                occurred_at=at,
                recorded_at=at,
                source=CASE_ACTIONS,
                kind=kind,
                subject_kind=SubjectKind.PERSON,
                subject_id=subject_id,
                payload=payload,
            )
        )

    async def _submit(
        self,
        *,
        case: Signal,
        tenant_id: UUID,
        actor_account_id: UUID,
        kind: FactKind,
        extra: dict[str, str] | None = None,
    ) -> None:
        now = self._clock()
        await self._intake.submit(
            Fact(
                fact_id=fact_id_for(case.id, kind),
                tenant_id=tenant_id,
                occurred_at=now,
                recorded_at=now,
                source=CASE_ACTIONS,
                kind=kind,
                subject_kind=SubjectKind.PERSON,
                # Le fait porte sur la **personne** du cas : c'est d'elle qu'il s'agit, et c'est
                # par elle que l'effet retrouvera le cas vivant au rejeu.
                subject_id=case.subject_id,
                payload={
                    # Le cas visé voyage pour la trace — il ne sert pas à le retrouver : un rejeu
                    # recrée les cas avec de nouveaux identifiants.
                    "signal_id": str(case.id),
                    "actor_account_id": str(actor_account_id),
                    **(extra or {}),
                },
            )
        )
