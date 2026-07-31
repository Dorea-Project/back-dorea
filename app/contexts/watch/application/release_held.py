"""La passe de nuit — **ce qui avait été détecté et retenu finit par sortir**.

Le plafond de débit protège le responsable : au-delà de N cas ouverts, il ne reçoit plus rien de
nouveau. Sans cette passe, cette protection deviendrait un oubli — les cas retenus resteraient
`HELD` indéfiniment, et le produit aurait détecté quelque chose que personne ne verrait jamais.
« Retenu ≠ perdu » n'est vrai que si quelque chose les relâche.

**Elle ne décide rien.** Elle n'invente aucun cas, ne juge aucune priorité, ne recalcule aucun
seuil : elle émet ce qui avait déjà été détecté, dans l'ordre où l'arbitrage l'aurait fait — par
origine du dire, puis du plus ancien au plus récent. C'est une opération de matérialisation
différée, pas un second étage de décision.

**Elle respecte le plafond, sinon elle le contourne.** On ne relâche que ce qui tient sous la
place libre de chaque responsable. Relâcher au-delà reviendrait à supprimer le plafond une nuit sur
deux, et à noyer précisément celui qu'il protège.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.contexts.watch.application.ports import SignalStore
from app.contexts.watch.application.referent_ports import WatchParameterRepository
from app.contexts.watch.domain.parameters import WatchParam
from app.contexts.watch.domain.regime import HeldReason
from app.contexts.watch.domain.signal import priority_rank


@dataclass(frozen=True)
class ReleasedCases:
    released: int
    still_held: int  # ce qui reste retenu — **dit**, jamais tu

    @property
    def has_backlog(self) -> bool:
        """Un arriéré permanent n'est pas un problème de plafond : c'est une détection trop
        bavarde. On remonte alors le seuil, on ne remonte pas le plafond — sinon on noie le
        responsable pour faire disparaître un indicateur."""
        return self.still_held > 0


class ReleaseHeldCases:
    def __init__(
        self, signals: SignalStore, params: WatchParameterRepository, *, clock
    ) -> None:
        self._signals = signals
        self._params = params
        self._clock = clock

    async def execute(self, *, tenant_id: UUID) -> ReleasedCases:
        cap = await self._params.get_int(tenant_id, WatchParam.OPEN_CASES_CAP)
        # **Le rodage n'est pas un plafond.** Un cas retenu parce que l'église observe ne se
        # relâche pas quand une place se libère : il attend que l'église décide de parler.
        # Les confondre ferait sortir une église de SHADOW toute seule, pendant la nuit.
        held = [
            case
            for case in await self._signals.held_cases(tenant_id=tenant_id)
            if case.held_reason != HeldReason.SHADOW.value
        ]

        # L'ordre de l'arbitrage, à l'identique : l'origine du dire d'abord, puis le plus ancien.
        # À origine égale, c'est le décrochage le plus vieux qui a le plus attendu.
        held.sort(key=lambda case: (priority_rank(case.priority), case.opened_at))

        budget: dict[UUID | None, int] = {}
        released = 0
        for case in held:
            owner = case.owner_account_id
            if owner not in budget:
                budget[owner] = await self._signals.open_cases_count(owner, tenant_id)
            if budget[owner] >= cap:
                continue
            case.release()
            await self._signals.save_case(case)
            budget[owner] += 1
            released += 1

        return ReleasedCases(released=released, still_held=len(held) - released)
