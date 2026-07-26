"""DTO applicatifs du contexte Mission."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class MissionLinkDTO:
    """Le lien tel que le voit son **propriétaire** (à partager)."""

    id: UUID
    code: str
    inviter_kind: str  # person | group
    message: str
    media_urls: list[str]
    place_label: str | None
    latitude: float | None
    longitude: float | None
    expires_at: datetime
    revoked: bool


@dataclass(frozen=True)
class MissionCardDTO:
    """La **carte publique** — ce que voit celui qui reçoit le lien (sans compte)."""

    inviter_label: str  # « Awa » ou « Cellule Jeunesse » — le visage
    inviter_kind: str
    church_label: str  # le nom de l'église
    message: str
    media_urls: list[str]
    place_label: str | None
    latitude: float | None
    longitude: float | None
    active: bool  # False si expiré/révoqué (le client affiche « invitation clôturée »)


@dataclass(frozen=True)
class SeekerDTO:
    id: UUID
    name: str
    status: str
    created_at: datetime
    accompanied_by: UUID | None = None  # qui a pris le relais (None = pas encore accompagné)
    accompanied_at: datetime | None = None  # le signal « quelqu'un s'en occupe »


@dataclass(frozen=True)
class MySeekersDTO:
    """Le fruit missionnaire — **privé** à l'inviteur (anti-vitrine, pas un score public)."""

    total: int
    seekers: list[SeekerDTO]
    reaction_counts: dict[str, int]  # touché/édifié/Amen : le signal « ça a résonné »


@dataclass(frozen=True)
class IntegrateSeekerResult:
    """Le chercheur **devenu membre** — le fruit versé dans le tunnel d'intégration existant."""

    account_id: UUID  # le compte (créé ou réutilisé par téléphone)
    tenant_id: UUID
    group_id: UUID | None  # la cellule où il est inscrit (seulement pour un chercheur de groupe)
    membership_status: str  # « invited » — le début du tunnel visiteur→membre
    reused_account: bool  # True si le téléphone existait déjà (identité globale, M-2)
    seeker_status: str  # « integrated »


@dataclass(frozen=True)
class VerseCardDTO:
    """La carte engendrée (M9-1) : la **référence** reconnue, le **texte exact** (canonique) et
    l'**image** designée (URL) — prête à devenir le média d'un lien d'invitation."""

    reference: str  # « Jean 3.16 » — reconnu par l'IA
    text: str  # le texte EXACT (Bible canonique, pas la mémoire de l'IA)
    image_url: str  # la carte designée, rangée dans le stockage média
