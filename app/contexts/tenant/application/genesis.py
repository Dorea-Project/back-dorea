"""Construction de la **genèse** d'une église (les 4 agrégats), partagée.

Utilisée par `ProvisionTenant` (provisionnement direct Plateforme) **et** par
l'approbation d'un onboarding. Prend un `password_hash` **déjà calculé** (le clair
n'arrive jamais ici) et renvoie Tenant + Account (owner) + Membership + Ownership.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from app.contexts.iam.domain.aggregates import Account, Membership
from app.contexts.iam.domain.enums import AccountStatus, MembershipStatus
from app.contexts.tenant.domain.aggregates import Tenant
from app.contexts.tenant.domain.drafts import OwnerDraft, TenantDraft
from app.contexts.tenant.domain.enums import OwnershipMode
from app.contexts.tenant.domain.ownership import Ownership
from app.contexts.tenant.domain.slug import build_slug
from app.contexts.tenant.domain.value_objects import Location


@dataclass(frozen=True)
class Genesis:
    tenant: Tenant
    owner_account: Account
    owner_membership: Membership
    ownership: Ownership


def build_genesis(
    *,
    tenant: TenantDraft,
    owner: OwnerDraft,
    owner_password_hash: str,
    now: datetime,
    mode: OwnershipMode = OwnershipMode.BOOTSTRAP,
) -> Genesis:
    tenant_id = uuid4()
    tenant_agg = Tenant(
        id=tenant_id,
        name=tenant.name,
        created_at=now,
        parent_id=tenant.parent_id,
        denomination=tenant.denomination,
        contact_email=tenant.contact_email,
        estimated_member_count=tenant.estimated_member_count,
        location=Location(
            country=tenant.country,
            city=tenant.city,
            address=tenant.address,
            latitude=tenant.latitude,
            longitude=tenant.longitude,
        ),
        slug=build_slug(tenant.name, tenant_id),
        logo_url=tenant.logo_url,
        short_description=tenant.short_description,
        contact_name=tenant.contact_name,
        contact_phone=tenant.contact_phone,
        timezone=tenant.timezone,
        language=tenant.language,
        currency=tenant.currency,
        operates_annexes=tenant.operates_annexes,
    )
    account = Account(
        id=uuid4(),
        phone_number=owner.phone,
        status=AccountStatus.ACTIVE,
        first_name=owner.first_name,
        last_name=owner.last_name,
        email=owner.email,
    )
    membership = Membership(
        id=uuid4(),
        account_id=account.id,
        tenant_id=tenant_agg.id,
        status=MembershipStatus.CONFIRMED_MEMBER,  # bootstrap, sans rôle
        last_transition_at=now,
        role_assignments=[],
    )
    ownership = Ownership(
        id=uuid4(),
        account_id=account.id,
        tenant_id=tenant_agg.id,
        mode=mode,
        started_at=now,
    )
    return Genesis(tenant_agg, account, membership, ownership)


# NB : `owner_password_hash` est passé à la persistance (`ProvisioningStore`), pas
# porté par les agrégats (les credentials ne sont pas dans le domaine IAM).
