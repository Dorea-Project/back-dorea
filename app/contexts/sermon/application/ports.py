"""Ports du contexte Sermon vers l'extérieur."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date
from uuid import UUID

from app._shared.domain.locale import DEFAULT_LOCALE, Locale
from app.contexts.sermon.domain.digest import Capsule, SermonDigest
from app.contexts.sermon.domain.enums import SermonSourceKind


class CapsuleFeedPort(ABC):
    """Publie les **capsules** du sermon **dans le fil** (S-2) — la porte d'entrée du membre.

    À la publication du sermon, chaque capsule devient une **annonce église-entière** (type
    `sermon`, auteur = le pasteur). L'autorité vient déjà de `PUBLISH_SERMON` : l'adaptateur écrit
    directement, sans re-vérifier `PUBLISH_ANNOUNCEMENT` (que le pasteur n'a pas)."""

    @abstractmethod
    async def publish_capsules(
        self, *, tenant_id: UUID, author_account_id: UUID, capsules: Sequence[Capsule]
    ) -> None: ...


class CulteAttendancePort(ABC):
    """Pose une présence **déclarée** au culte du jour (S-4) — le « oui » du compagnon.

    Axe **physique** (distinct de la Résonance) : rejoint/crée la rencontre église-entière du culte
    et marque le membre présent, source `declared` — la plus basse confiance, **additive**, elle
    n'éteint jamais une alerte. Idempotent (déclarer deux fois = pareil). Un scan reste roi."""

    @abstractmethod
    async def mark_declared_present(
        self, *, tenant_id: UUID, member_account_id: UUID, on_date: date, now
    ) -> None: ...


class SermonTextExtractor(ABC):
    """Normalise n'importe quel dépôt en **texte** (S-5/S-6) — l'IA ne voit jamais que du texte.

    Un seul port ; les formats (texte, PDF, PPTX, audio) sont des adaptateurs derrière lui, ajoutés
    sans toucher le domaine. Le pipeline de digestion (S-1) travaille sur le texte qui en sort."""

    @abstractmethod
    async def extract(self, data: bytes, *, kind: SermonSourceKind) -> str: ...


class SermonDigester(ABC):
    """Le **moteur IA** (S-1) : d'un texte de sermon → le **digest** en **un seul appel**.

    Produit tout l'arbre d'un coup (résumé, points essentiels, capsules, Q&R de consolidation) ;
    le pasteur relit et approuve, puis c'est gelé. Le runtime ne rappelle jamais l'IA — coût en
    O(sermons), pas O(membres x interactions). Un repli déterministe permet de tourner sans clé.

    ⚠️ `locale` est la langue de l'**église**, jamais celle d'un lecteur. Le digest est écrit une
    fois, gelé à l'approbation, puis lu par toute l'assemblée : il n'a qu'une langue possible,
    celle du culte qui a été prêché. C'est la différence de fond avec une notification, qui se
    rend par destinataire.
    """

    @abstractmethod
    async def digest(
        self, text: str, *, title: str, reference: str | None, locale: Locale = DEFAULT_LOCALE
    ) -> SermonDigest: ...
