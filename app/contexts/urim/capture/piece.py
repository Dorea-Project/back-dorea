"""La **pièce** — ce qu'un pasteur publie, et le seul objet de « prêcher » qui traverse.

D70 a renversé le tronc de la branche : l'audio retravaillé est le produit, pas le
transcript. Un dimanche donne une heure et demie d'un seul tenant — une prédication
enchaînée par une prière, avec du bruit et des chants au démarrage. On ne publie pas ça.
Le pasteur écoute, coupe, et en tire deux pièces qui sortent à trois jours d'intervalle.

---

## Ce qui la distingue d'une capture

| | La capture | La pièce |
| :-- | :-- | :-- |
| Ce que c'est | ce que le micro a pris **sans intention** | ce qu'il a **décidé de garder** |
| Durée de vie | sept jours, puis purge | **elle vit avec sa publication** |
| Combien par dimanche | une | autant qu'il en taille |

🔴 **Le découpage est le consentement.** La matière brute expire parce qu'*un micro capte
la salle* et qu'un témoignage donné au micro du prédicateur peut s'y trouver. Une pièce a
été écoutée puis choisie : c'est cet acte, et non une durée de rétention, qui la rend
publiable. Rien ici ne porte de date de péremption, et ce n'est pas un oubli.

## Pur, comme `Capture`

Aucune I/O, aucune horloge : les deux instants entrent par les paramètres. `cut_at` vient
de l'appareil — le pasteur a coupé hors ligne — et `published_at` du serveur, seul à savoir
quand la pièce a réellement traversé.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app._shared.domain.errors import DomainError


class PieceInvalideError(DomainError):
    """Des bornes inversées, ou un titre vide.

    ⚠️ **La base tient déjà les deux** (`piece_bornes_ordonnees`,
    `piece_titre_non_vide`). Cette erreur existe pour que le refus ait une phrase que le
    pasteur puisse lire, au lieu d'une violation de contrainte remontée telle quelle."""

    code = "URIM_PIECE_INVALIDE"
    http_status = 422


@dataclass(frozen=True, slots=True)
class Piece:
    """Une pièce taillée, publiée."""

    id: UUID
    capture_id: UUID
    church_id: UUID
    author_id: UUID
    title: str
    start_ms: int
    end_ms: int
    media_url: str
    cut_at: datetime
    published_at: datetime

    @classmethod
    def publier(
        cls,
        *,
        id: UUID,
        capture_id: UUID,
        church_id: UUID,
        author_id: UUID,
        title: str,
        start_ms: int,
        end_ms: int,
        media_url: str,
        cut_at: datetime,
        at: datetime,
    ) -> Piece:
        """Construit la pièce publiée, ou refuse avec une phrase lisible."""
        titre = title.strip()

        if not titre:
            raise PieceInvalideError(
                "Une pièce porte un nom : sans lui, deux extraits du même dimanche ne se "
                "distinguent pas dans une liste."
            )
        if end_ms <= start_ms:
            raise PieceInvalideError(
                "Les bornes de cette pièce se croisent : il n'y a rien entre les deux."
            )

        return cls(
            id=id,
            capture_id=capture_id,
            church_id=church_id,
            author_id=author_id,
            title=titre,
            start_ms=start_ms,
            end_ms=end_ms,
            media_url=media_url,
            cut_at=cut_at,
            published_at=at,
        )

    @property
    def duree_ms(self) -> int:
        return self.end_ms - self.start_ms


class AudioRefuseError(DomainError):
    """Ce que le pasteur a envoyé n'est pas une pièce jouable.

    🔴 **Urim a sa propre garde, et ne l'emprunte pas au contexte `media`.** Celui-ci en
    porte une, écrite pour les images d'annonces, avec ses propres erreurs et sa limite de
    trente secondes de vidéo. L'importer ferait franchir à Urim une frontière que son
    architecture interdit — *un seul point de contact avec le reste du système* — et
    l'attacherait à des règles qui ne sont pas les siennes : une prédication dure une heure,
    c'est son état normal."""

    code = "URIM_PIECE_AUDIO_REFUSE"
    http_status = 415


class PieceAudioStore(Protocol):
    """Où les octets d'une pièce publiée vont vivre.

    ⚠️ **Un port, comme `FragmentStore`, et pour la même raison** : Urim ne connaît pas le
    magasin qui range réellement. L'adaptateur vit dans `adapters/`, seul endroit autorisé à
    toucher un autre contexte.

    🔴 **Ce magasin-ci ne purge pas**, contrairement à celui des fragments. La matière brute
    expire à sept jours ; une pièce vit avec sa publication. Ce port n'offre donc **aucun
    verbe pour effacer** — en donner un inviterait à s'en servir pour du ménage."""

    async def ranger(self, octets: bytes, *, content_type: str) -> str:
        """Range les octets et rend l'**URL** à laquelle l'assemblée les atteindra."""
        ...


class PieceRepository(Protocol):
    """Où les pièces publiées se rangent.

    🔴 **Aucun verbe n'efface.** Rien n'expire ici : la seule disparition possible est un
    geste du pasteur, et il n'a pas encore de route. Offrir un `delete` avant qu'un écran
    le demande inviterait à l'utiliser pour du ménage."""

    async def add(self, piece: Piece) -> Piece:
        """Range une pièce, et rend **celle qui fait foi**.

        🔴 **Sans effet si l'identifiant existe déjà — et c'est le contrat.** L'appareil
        produit l'identifiant avant que le réseau existe (D64) ; un pasteur qui appuie deux
        fois sur « publier » dans un tunnel, ou dont la réponse s'est perdue, renverra la
        même pièce. Lever ici lui ferait croire à un échec, et il recommencerait — jusqu'à
        ce qu'il abandonne ou que son assemblée reçoive la même prière trois fois.

        Rend donc la ligne déjà présente le cas échéant, jamais une seconde."""
        ...

    async def get(self, piece_id: UUID) -> Piece | None:
        """La pièce, ou `None`. Ne lève pas : une pièce inconnue est une réponse."""
        ...

    async def pour_eglise(self, church_id: UUID, *, limite: int = 50) -> tuple[Piece, ...]:
        """Le fil d'une assemblée — la plus récemment publiée en tête."""
        ...
