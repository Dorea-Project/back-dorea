"""Ports du contexte Annonces vers le monde extérieur."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class GatheringRsvpPort(ABC):
    """Relie le « je viens » d'une annonce *convoquer* à la **présence attendue** M6.

    iam-style : Annonces exprime son besoin (poser/retirer un « je viens » sur une rencontre) ;
    un adaptateur côté Présence l'écrit. Le pré-signal pré-remplit le roster, sans écrire de
    présence réelle (M6 reste propre)."""

    @abstractmethod
    async def set_rsvp(
        self, *, gathering_id: UUID, account_id: UUID, now: datetime
    ) -> None: ...

    @abstractmethod
    async def clear_rsvp(self, *, gathering_id: UUID, account_id: UUID) -> None: ...


class AudiencePort(ABC):
    """Résout la **portée sous-arbre** d'un membre : à quels groupes une annonce peut-elle
    scoper pour l'atteindre. Renvoie tous les **ancêtres-ou-soi** de ses groupes actifs
    (chemin matérialisé). Implémenté côté Groupes ; faux en test."""

    @abstractmethod
    async def covering_group_ids(self, *, account_id: UUID, tenant_id: UUID) -> set[UUID]:
        ...


class MemberDirectoryPort(ABC):
    """Liste les **comptes** des membres actifs d'une église — la cible d'un broadcast (notif)."""

    @abstractmethod
    async def member_account_ids(self, tenant_id: UUID) -> list[UUID]: ...

    @abstractmethod
    async def member_account_ids_in_subtree(
        self, tenant_id: UUID, group_id: UUID
    ) -> list[UUID]:
        """Les comptes actifs du **sous-arbre** d'un groupe (le groupe + ses descendants) —
        la cible d'un broadcast d'annonce à portée groupe."""
        ...
