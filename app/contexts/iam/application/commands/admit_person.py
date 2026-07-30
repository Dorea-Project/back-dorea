"""`AdmitPerson` — **le seul endroit** qui donne à quelqu'un sa première appartenance.

Le statut d'une personne a deux moments, et deux écrivains, pas plus :

| Moment | Écrivain | Où |
|---|---|---|
| **Entrer** — recevoir sa première appartenance | `AdmitPerson` | ici |
| **Avancer** — franchir un palier de la chaîne | `TransitionStatus` | le module voisin |

Ce module existe pour une raison précise. `mission` construisait lui-même un `Membership` avec
son statut, en deux endroits ; demain `attendance` voudra promouvoir un visiteur régulier en
sympathisant. Trois modules écrivant ce statut, c'est trois règles de transition qui divergent —
le même problème, simplement déplacé. À poser maintenant, pendant qu'il n'y a qu'un appelant.

**Il n'y a pas de troisième écrivain, et surtout pas de raccourci.** Le palier d'entrée est
toujours `INVITED` : la chaîne se franchit un cran à la fois, et `transitions.py` refuse déjà les
sauts. Un module qui pourrait nommer un membre confirmé en un appel viderait cette règle de son
sens sans jamais la contredire explicitement.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.contexts.iam.application.ports import MemberEnrollmentStore
from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import (
    AccountCreationSource,
    AccountStatus,
    MembershipStatus,
)
from app.contexts.iam.domain.repositories import AccountRepository, MembershipRepository

# Le seul statut auquel on entre. Nommé une fois, ici.
ADMISSION_STATUS = MembershipStatus.INVITED


class AdmitPerson:
    """Fait exister la personne dans une église, sans jamais dupliquer son identité.

    Pas de garde RBAC ici : ce service sert des chemins qui portent **déjà** leur propre
    autorité — le geste de quelqu'un qui laisse son contact (aucune autorité requise, c'est le
    sien), et l'enrôlement d'un chercheur (autorité vérifiée par l'appelant avant d'arriver ici).
    Poser une seconde garde ici les rendrait incohérents entre eux."""

    def __init__(
        self,
        accounts: AccountRepository,
        memberships: MembershipRepository,
        enrollment: MemberEnrollmentStore,
    ) -> None:
        self._accounts = accounts
        self._memberships = memberships
        self._enrollment = enrollment

    async def execute(
        self,
        *,
        tenant_id: UUID,
        phone: str | None,
        first_name: str | None,
        last_name: str | None,
        creation_source: AccountCreationSource,
        actor_account_id: UUID | None,
        now,
    ) -> tuple[UUID, bool]:
        """`(account_id, réutilisé)`. **L'identité ne se duplique jamais.**

        Quelqu'un qui revient par une autre porte est la même personne : lui fabriquer un second
        compte effacerait justement l'histoire qu'on veut garder."""
        if phone:
            existing = await self._accounts.get_by_phone(phone)
            if existing is not None:
                await self._ensure_membership(
                    existing.id, tenant_id, actor_account_id or existing.id, now
                )
                return existing.id, True

        account = Account(
            id=uuid4(),
            phone_number=phone,
            status=AccountStatus.ACTIVE,
            first_name=first_name,
            last_name=last_name,
        )
        await self._enrollment.enroll(
            account=account,
            membership=self._membership(account.id, tenant_id, now),
            creation_source=creation_source,
            # Personne d'autre quand c'est son propre geste.
            actor_account_id=actor_account_id or account.id,
        )
        return account.id, False

    async def _ensure_membership(
        self, account_id: UUID, tenant_id: UUID, actor_account_id: UUID, now
    ) -> None:
        """Une appartenance existante n'est **jamais** rétrogradée à l'admission.

        Quelqu'un de déjà confirmé qui accepte une capsule ne redevient pas invité."""
        if await self._memberships.get_active(account_id, tenant_id) is not None:
            return
        await self._enrollment.add_membership(
            membership=self._membership(account_id, tenant_id, now),
            actor_account_id=actor_account_id,
        )

    @staticmethod
    def _membership(account_id: UUID, tenant_id: UUID, now) -> Membership:
        return Membership(
            id=uuid4(),
            account_id=account_id,
            tenant_id=tenant_id,
            status=ADMISSION_STATUS,
            last_transition_at=now,
            role_assignments=[],
        )
