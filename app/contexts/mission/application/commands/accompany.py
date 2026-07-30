"""**Accompagner** et **Clôturer** (M9-3) — désormais portés par le `Signal`.

*L'humain garde la place essentielle.* Ce qui change n'est pas le geste, c'est où il s'écrit :
`SeekerStatus` était une seconde machine à états suivant la même personne que le cas de veille.
Les deux auraient divergé. Ici, **le `Signal` est la vérité** ; l'état du chercheur se lit.

| Geste | Ce qui s'écrit |
|---|---|
| Accompagner | le cas est **assigné** à celui qui prend le relais, et le contact commence |
| Clôturer | le cas se ferme, avec une issue **choisie** |

L'autorisation ne bouge pas d'un pouce : chercheur **personnel** → son inviteur ; chercheur **de
groupe** → un responsable du groupe qui l'a amené. Elle correspond exactement à la cascade
`INVITER` / `GROUP_LEAD`, et un test la fige — passer à « propriétaire du cas » aurait pu
l'élargir en silence.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.groups.application.group_access import GroupAccessPolicy
from app.contexts.groups.application.group_lookup import load_group_in_tenant
from app.contexts.groups.domain.errors import UnauthorizedGroupActionError
from app.contexts.groups.domain.repositories import GroupRepository
from app.contexts.iam.domain.permissions import Permission
from app.contexts.mission.application.dtos import SeekerDTO
from app.contexts.mission.domain.aggregates import Seeker
from app.contexts.mission.domain.derived_status import derive_seeker_status
from app.contexts.mission.domain.errors import (
    SeekerAlreadyResolvedError,
    SeekerNotFoundError,
)
from app.contexts.mission.domain.repositories import SeekerRepository
from app.contexts.watch.application.ports import ContactAttemptStore, SignalStore
from app.contexts.watch.domain.contact import ContactAttempt, ContactChannel, ContactResult
from app.contexts.watch.domain.signal import Signal, SignalOutcome, SignalStatus

# Les seules issues qu'un parcours de chercheur peut prendre. `KNOWN_AND_FOLLOWED` est la porte
# qui manquait : « elle vient, on la connaît par son nom, elle ne veut pas encore de cellule. »
# C'est une sortie **réussie**, pas un abandon — sans elle, le module reste un entonnoir de
# conversion quelle que soit la propreté de l'architecture en dessous.
SEEKER_OUTCOMES: frozenset[SignalOutcome] = frozenset(
    {
        SignalOutcome.UNREACHABLE_ARCHIVED,  # le défaut : n'a pas donné suite, sans jugement
        SignalOutcome.KNOWN_AND_FOLLOWED,
        SignalOutcome.CHANGED_CHURCH,
        SignalOutcome.DO_NOT_CONTACT,
        SignalOutcome.RESTORED,
    }
)


def to_seeker_dto(seeker: Seeker, case: Signal | None) -> SeekerDTO:
    """Le chercheur tel qu'il se **lit** — son état vient du cas, plus d'une colonne."""
    return SeekerDTO(
        id=seeker.id,
        name=seeker.name,
        status=derive_seeker_status(seeker, case).value,
        created_at=seeker.created_at,
        accompanied_by=case.owner_account_id if case is not None else None,
        accompanied_at=case.first_contact_at if case is not None else None,
    )


async def load_owned_seeker(
    seekers: SeekerRepository,
    groups: GroupRepository,
    access: GroupAccessPolicy,
    *,
    actor_account_id: UUID,
    seeker_id: UUID,
) -> Seeker:
    """Charge le chercheur et vérifie que l'acteur en est le **propriétaire** du suivi.

    Inchangé — et volontairement : le raccordement au `Signal` ne doit ouvrir aucun accès qui
    n'existait pas. À périmètre égal, pas plus large."""
    seeker = await seekers.get(seeker_id)
    if seeker is None:
        raise SeekerNotFoundError("Chercheur introuvable.", details={"seeker_id": str(seeker_id)})
    # Personnel → l'inviteur lui-même ; groupe → un responsable du groupe (comme RevokeLink).
    if seeker.inviter_account_id is not None:
        if seeker.inviter_account_id != actor_account_id:
            raise UnauthorizedGroupActionError(
                "Seul l'inviteur peut accompagner ce chercheur.",
                details={"seeker_id": str(seeker_id)},
            )
    else:
        group = await load_group_in_tenant(groups, seeker.inviter_group_id, seeker.tenant_id)
        await access.ensure_can(
            actor_account_id=actor_account_id, group=group, permission=Permission.MANAGE_GROUP
        )
    return seeker


class _SeekerCase:
    """Socle : l'autorisation d'hier, le cas de veille pour aujourd'hui."""

    def __init__(
        self,
        seekers: SeekerRepository,
        groups: GroupRepository,
        access: GroupAccessPolicy,
        signals: SignalStore,
        *,
        clock,
    ) -> None:
        self._seekers = seekers
        self._groups = groups
        self._access = access
        self._signals = signals
        self._clock = clock

    async def _load(self, *, actor_account_id: UUID, seeker_id: UUID):
        seeker = await load_owned_seeker(
            self._seekers, self._groups, self._access,
            actor_account_id=actor_account_id, seeker_id=seeker_id,
        )
        if seeker.integrated_account_id is not None:
            raise SeekerAlreadyResolvedError(
                "Ce chercheur est devenu membre : son parcours ne se rejoue pas.",
                details={"seeker_id": str(seeker_id)},
            )
        case = None
        if seeker.person_account_id is not None:
            case = await self._signals.live_case_of(
                subject_id=seeker.person_account_id, tenant_id=seeker.tenant_id
            )
        return seeker, case


class AccompanySeeker(_SeekerCase):
    """Un membre prend le relais : le cas lui est **assigné**, et le contact commence.

    Ré-appeler réattribue l'accompagnement — c'est un nouveau relais, pas une erreur. Un
    parcours déjà clos ne revient pas en arrière : l'agrégat `Signal` refuse la transition, et
    ce service ne rejoue pas cette règle."""

    def __init__(
        self,
        *args,
        attempts: ContactAttemptStore | None = None,
        id_factory=uuid4,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._attempts = attempts
        self._new_id = id_factory

    async def execute(self, *, actor_account_id: UUID, seeker_id: UUID) -> SeekerDTO:
        seeker, case = await self._load(
            actor_account_id=actor_account_id, seeker_id=seeker_id
        )
        if case is None:
            raise SeekerAlreadyResolvedError(
                "Ce chercheur n'a plus de suivi ouvert.", details={"seeker_id": str(seeker_id)}
            )

        now = self._clock()
        if case.status is SignalStatus.OPEN or case.owner_account_id != actor_account_id:
            case.owner_account_id = actor_account_id
            if case.status is SignalStatus.OPEN:
                case.assign(owner_account_id=actor_account_id)
        # Prendre le relais **est** un contact engagé : c'est ce qui fait tomber
        # `first_contact_at`, la métrique reine du pilote. Sans elle, l'escalade croirait que
        # personne n'a rien fait.
        case.record_contact_attempt(at=now)
        await self._signals.save_case(case)
        await self._trace(case, actor_account_id, now)
        return to_seeker_dto(seeker, case)

    async def _trace(self, case: Signal, by_account_id: UUID, now) -> None:
        """La trace de l'effort, du même type que celle de la boucle boomerang.

        `REACHED` d'emblée, et `answered_at` posé : ici le relais est **déclaré** par un humain
        qui l'a déjà pris. Il n'y a aucun retour à attendre — contrairement à un appel lancé
        depuis l'application, dont on ne sait pas encore s'il a abouti. La laisser en attente
        ferait apparaître ce responsable dans l'invite de réouverture pour rien."""
        if self._attempts is None:
            return
        await self._attempts.add(
            ContactAttempt(
                id=self._new_id(),
                tenant_id=case.tenant_id,
                signal_id=case.id,
                by_account_id=by_account_id,
                channel=ContactChannel.VISIT,
                attempted_at=now,
                result=ContactResult.REACHED,
                answered_at=now,
            )
        )


class CloseSeeker(_SeekerCase):
    """Le parcours s'arrête — avec une issue **choisie**, et sans jugement.

    Le défaut reste « n'a pas donné suite » pour que les clients existants ne changent pas de
    comportement. Mais « connu et suivi » est désormais disponible, et c'est une réussite."""

    async def execute(
        self,
        *,
        actor_account_id: UUID,
        seeker_id: UUID,
        outcome: SignalOutcome = SignalOutcome.UNREACHABLE_ARCHIVED,
    ) -> SeekerDTO:
        if outcome not in SEEKER_OUTCOMES:
            raise SeekerAlreadyResolvedError(
                "Cette issue n'appartient pas au parcours d'un chercheur.",
                details={"outcome": outcome.value},
            )
        seeker, case = await self._load(
            actor_account_id=actor_account_id, seeker_id=seeker_id
        )
        if case is None:
            return to_seeker_dto(seeker, None)  # déjà clos : idempotent, comme avant

        case.close(
            outcome=outcome, at=self._clock(), closed_by_account_id=actor_account_id
        )
        await self._signals.save_case(case)
        return to_seeker_dto(seeker, case)
