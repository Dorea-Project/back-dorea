"""Le domaine de la capture — **l'étape 1, et rien d'autre**.

Le verrou de séquencement est explicite : capture, transport, transcript brut **non exploité**,
jusqu'à mesure du taux d'erreur dans trois églises réelles. L'extraction des versets est l'étape 2,
l'alignement la 3, la synthèse la quatrième et dernière.

Ce module ne porte donc que ce que l'étape 1 exige, et il le porte **purement** : deux règles
métier, aucune I/O, aucune horloge — le temps entre par les paramètres.

---

## Les deux règles, et pourquoi elles sont ici plutôt que dans un worker

**« La capture n'est jamais refusée. »** Plafond atteint, l'enregistrement a lieu quand même et
l'audio est conservé ; c'est la *transcription* qui est différée. Le motif est temporel et il ne
se négocie pas :

> Ce qui n'est pas capté dimanche est perdu pour toujours. Un transcript, lui, peut attendre lundi.

**« Un travail abandonné laisse le transcript en `partielle` — jamais un silence. »** Après cinq
tentatives, on cesse d'essayer, mais on ne fait pas disparaître l'échec : le pasteur voit ce qui
n'a pas marché. Une capture qui échoue en silence est indiscernable d'un dimanche où personne n'a
prêché.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

#: Au-delà, on cesse de réessayer — mais on ne cesse pas de le dire (§3).
TENTATIVES_MAX = 5

#: L'audio ne survit pas à la semaine. La date se pose à la capture, jamais après coup : une
#: échéance qu'on peut repousser n'est pas une promesse de confidentialité.
RETENTION_AUDIO = timedelta(days=7)

#: Reprise exponentielle — 1, 2, 4, 8, 16 minutes. Un fournisseur de transcription qui tousse a
#: besoin qu'on le laisse respirer, pas qu'on insiste.
BACKOFF_BASE = timedelta(minutes=1)


class CaptureState(StrEnum):
    CAPTEE = "captée"  # l'audio est là, rien n'a encore été transcrit
    TRANSCRITE = "transcrite"  # le transcript est complet
    PARTIELLE = "partielle"  # un travail a été abandonné — visible, jamais silencieux
    ECHOUEE = "échouée"  # rien n'a pu être transcrit


class JobKind(StrEnum):
    TRANSCRIRE = "transcrire"
    EXTRAIRE_VERSETS = "extraire_versets"  # étape 2 — verrouillée
    ALIGNER = "aligner"  # étape 3 — verrouillée
    PURGER_AUDIO = "purger_audio"


class JobState(StrEnum):
    EN_ATTENTE = "en_attente"
    EN_COURS = "en_cours"
    FAIT = "fait"
    ECHOUE = "echoue"
    ABANDONNE = "abandonne"


@dataclass(frozen=True, slots=True)
class Capture:
    """Un culte enregistré. Immuable — chaque transition rend une nouvelle capture."""

    id: UUID
    church_id: UUID
    author_id: UUID
    preached_on: datetime
    audio_purge_at: datetime
    state: CaptureState = CaptureState.CAPTEE
    #: `None` quand on a prêché sans avoir préparé — un transcript reste utile.
    preparation_id: UUID | None = None
    #: Le fournisseur et son modèle, **stockés par transcript** : sans eux, impossible de savoir
    #: plus tard pourquoi certains dimanches sont mauvais.
    provider: str | None = None
    model_ref: str | None = None
    transcription_deferred: bool = False
    audio_purged_at: datetime | None = None

    @classmethod
    def ouvrir(
        cls,
        *,
        id: UUID,
        church_id: UUID,
        author_id: UUID,
        preached_on: datetime,
        at: datetime,
        preparation_id: UUID | None = None,
        ceiling_reached: bool = False,
    ) -> Capture:
        """**Jamais refusée.** Le plafond diffère la transcription, il n'empêche pas d'enregistrer.

        C'est la seule ressource du produit dont le refus serait irréparable : un dimanche ne se
        rejoue pas."""
        return cls(
            id=id,
            church_id=church_id,
            author_id=author_id,
            preached_on=preached_on,
            preparation_id=preparation_id,
            audio_purge_at=at + RETENTION_AUDIO,
            transcription_deferred=ceiling_reached,
        )

    def transcrite(self, *, provider: str, model_ref: str) -> Capture:
        return replace(
            self,
            state=CaptureState.TRANSCRITE,
            provider=provider,
            model_ref=model_ref,
            transcription_deferred=False,
        )

    def partielle(self) -> Capture:
        """Un travail abandonné — **visible**. L'échec silencieux est le seul inacceptable."""
        return replace(self, state=CaptureState.PARTIELLE)

    def echouee(self) -> Capture:
        return replace(self, state=CaptureState.ECHOUEE)

    def purgee(self, *, at: datetime) -> Capture:
        return replace(self, audio_purged_at=at)

    def audio_a_purger(self, *, at: datetime) -> bool:
        """L'échéance est dépassée et l'audio est encore là.

        Le travail qui lit ça **échoue bruyamment** s'il ne peut pas supprimer : une promesse de
        suppression qui échoue en silence est pire que pas de promesse."""
        return self.audio_purged_at is None and at >= self.audio_purge_at


@dataclass(frozen=True, slots=True)
class CaptureJob:
    """Un travail de la file. La reprise et l'abandon sont des règles, pas des réglages."""

    id: UUID
    capture_id: UUID
    kind: JobKind
    idempotency_key: str
    state: JobState = JobState.EN_ATTENTE
    attempts: int = 0
    not_before: datetime | None = None
    last_error: str | None = None

    @property
    def abandonne(self) -> bool:
        return self.state is JobState.ABANDONNE

    def echoue(self, *, motif: str, at: datetime) -> CaptureJob:
        """Une tentative de plus, ou l'abandon — et **le motif est conservé dans les deux cas**.

        Sans `last_error`, un travail abandonné devient un silence, et le pasteur cherche pourquoi
        son dimanche a disparu."""
        tentatives = self.attempts + 1
        if tentatives >= TENTATIVES_MAX:
            return replace(
                self, state=JobState.ABANDONNE, attempts=tentatives, last_error=motif
            )
        return replace(
            self,
            state=JobState.EN_ATTENTE,
            attempts=tentatives,
            last_error=motif,
            not_before=at + BACKOFF_BASE * (2 ** (tentatives - 1)),
        )

    def reussi(self) -> CaptureJob:
        return replace(self, state=JobState.FAIT, last_error=None)
