"""L'interprétation d'une pièce en langue locale — D62, et **un service, pas un moteur**.

Le pasteur prêche en français ; une part de son assemblée entend le dioula, le baoulé ou le
malinké. D62 a tranché : ce travail est tenu par **l'équipe Dorea**, un interprète maîtrisé
par langue. Aucune synthèse vocale ne dit ces langues, et faire semblant serait pire que se
taire.

---

## 🔴 Pourquoi c'est possible aujourd'hui, et pas la semaine dernière

L'interprète **écoute la pièce**. Tant que l'interprétation partait d'une synthèse validée,
elle attendait le transcript, qui attend la mesure dans trois églises. D71 l'a fait partir
de l'audio : elle n'attend plus rien.

## Aucun délai n'est promis

⚠️ **Il n'y a pas d'échéance dans cet agrégat.** Le pasteur demande le samedi et voudrait
publier le samedi soir ; personne n'a encore dit si l'équipe tient la journée. **Un délai
affiché est une promesse ; un état est un fait.** Le second se tient sans engager quiconque,
et c'est ce qu'on rend tant que le premier n'existe pas.

## Quatre états, et le dernier parle

`demandée` → `prise` → `rendue`, ou `refusée` **avec son motif**. Une demande qui disparaît
est indiscernable d'une demande jamais partie, et le pasteur attendrait un samedi soir
devant un écran muet.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app._shared.domain.errors import DomainError


class InterpretationEtat(StrEnum):
    DEMANDEE = "demandée"
    PRISE = "prise"
    RENDUE = "rendue"
    REFUSEE = "refusée"


class InterpretationInvalideError(DomainError):
    """Une langue vide, ou une transition que l'agrégat refuse."""

    code = "URIM_INTERPRETATION_INVALIDE"
    http_status = 422


class InterpretationIntrouvableError(DomainError):
    """On agit sur une demande que le serveur ne connaît pas."""

    code = "URIM_INTERPRETATION_INTROUVABLE"
    http_status = 404


@dataclass(frozen=True, slots=True)
class Interpretation:
    """Une pièce, une langue, un travail humain."""

    id: UUID
    piece_id: UUID
    church_id: UUID
    requested_by: UUID
    language: str
    state: InterpretationEtat
    requested_at: datetime
    media_url: str | None = None
    refused_reason: str | None = None
    taken_at: datetime | None = None
    settled_at: datetime | None = None

    @classmethod
    def demander(
        cls,
        *,
        id: UUID,
        piece_id: UUID,
        church_id: UUID,
        requested_by: UUID,
        language: str,
        at: datetime,
    ) -> Interpretation:
        langue = language.strip()
        if not langue:
            raise InterpretationInvalideError(
                "Dites dans quelle langue vous voulez l'entendre : « baoulé de Bouaké » "
                "vaut mieux qu'une case vide."
            )

        return cls(
            id=id,
            piece_id=piece_id,
            church_id=church_id,
            requested_by=requested_by,
            language=langue,
            state=InterpretationEtat.DEMANDEE,
            requested_at=at,
        )

    def prendre(self, *, at: datetime) -> Interpretation:
        """Un interprète s'en charge.

        ⚠️ **Seule une demande en attente se prend.** Reprendre un travail rendu effacerait
        sa date de livraison, et le pasteur verrait sa version en langue redevenir « en
        cours » sans que rien ne se soit passé."""
        self._exiger(InterpretationEtat.DEMANDEE, "Ce travail n'attend plus d'être pris.")
        return replace(self, state=InterpretationEtat.PRISE, taken_at=at)

    def rendre(self, *, media_url: str, at: datetime) -> Interpretation:
        """Le travail est fait, et voici l'audio.

        🔴 **Une interprétation sans audio n'est pas rendue.** Marquer « rendue » sur rien
        ferait disparaître la demande de la file tout en laissant le pasteur sans version —
        le pire des deux mondes, et personne ne le verrait."""
        if not media_url:
            raise InterpretationInvalideError(
                "Une interprétation se rend avec son audio, jamais seule."
            )
        self._exiger(InterpretationEtat.PRISE, "Ce travail n'a pas été pris.")
        return replace(
            self, state=InterpretationEtat.RENDUE, media_url=media_url, settled_at=at
        )

    def refuser(self, *, motif: str, at: datetime) -> Interpretation:
        """L'équipe ne peut pas — et elle dit pourquoi.

        🔴 *Un travail abandonné laisse une trace, jamais un silence.*"""
        raison = motif.strip()
        if not raison:
            raise InterpretationInvalideError(
                "Un refus sans motif laisse le pasteur devant un écran muet."
            )
        if self.state in (InterpretationEtat.RENDUE, InterpretationEtat.REFUSEE):
            raise InterpretationInvalideError("Ce travail est déjà clos.")

        return replace(
            self, state=InterpretationEtat.REFUSEE, refused_reason=raison, settled_at=at
        )

    def _exiger(self, attendu: InterpretationEtat, message: str) -> None:
        if self.state is not attendu:
            raise InterpretationInvalideError(message, details={"etat": self.state.value})


class InterpretationRepository(Protocol):
    """Où les demandes d'interprétation vivent.

    🔴 **Aucun verbe n'efface.** Une demande refusée reste : elle dit à l'équipe ce qu'elle
    n'a pas su faire, et au pasteur pourquoi il n'a rien reçu."""

    async def add(self, demande: Interpretation) -> Interpretation:
        """Range une demande, et rend **celle qui fait foi**.

        ⚠️ **Une pièce, une langue, une fois.** Redemander la même chose ne doit pas ouvrir
        un second travail dans la file de l'équipe : un pasteur qui appuie deux fois, ou dont
        la réponse s'est perdue, retrouve sa demande."""
        ...

    async def get(self, demande_id: UUID) -> Interpretation | None: ...

    async def pour_piece(self, piece_id: UUID) -> tuple[Interpretation, ...]:
        """Ce qui a été demandé sur cette pièce, toutes langues confondues."""
        ...

    async def save(self, demande: Interpretation) -> None:
        """Écrit une transition. L'agrégat est immuable — un remplacement, pas un patch."""
        ...
