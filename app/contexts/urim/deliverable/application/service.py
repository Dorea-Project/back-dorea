"""Le livrable — **la validation, et rien que la validation**.

Ce service ne produit aucun fichier, et c'est l'ordre qui compte :

```
il compose ses diapositives  →  le serveur juge CHAQUE texte contre le corpus
                                       ↓
                        altere ?  → 'rejete', aucun fichier n'existera
                        tout passe → 'conforme', signé, et alors seulement
                                     un rendu pourra être demandé
```

**Un fichier produit est un fichier qui circule.** Le contrôle d'après coup protège la base de
données, pas l'assemblée. C'est pourquoi le jugement précède le premier octet, et pourquoi la
route de rendu ne servira que ce qui porte déjà `conforme`.

## Les trois conditions, dans l'ordre où elles coûtent

1. **Quelque chose de lui** — une division du plan (`documents.POINT_CENTRAL`). Gratuit, et
   c'est la règle centrale : le document met en page ce qu'il a écrit, il ne l'écrit pas à sa
   place.
2. **Une référence lisible** par diapositive — sinon on ne sait pas contre quoi juger.
3. **Le texte projeté reconnu** par une des versions détenues (Q9).

## Ce qu'un refus n'est pas

Une citation altérée **n'est pas une erreur HTTP**. C'est ce que le produit veut montrer : la
réponse porte `rejete` et, diapositive par diapositive, ce qu'il a écrit et ce que le corpus
porte. Un 422 ferait disparaître le seul écran où un verset abîmé se voit avant le dimanche.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.urim.application.access import ensure_may_read
from app.contexts.urim.application.ports import PreacherAuthorization, StudyRepository
from app.contexts.urim.application.reference_libre import lire
from app.contexts.urim.deliverable.application.ports import (
    ControleRecord,
    DeliverableRepository,
    DiapositiveSoumise,
    LivrableRecord,
    VerseTextReader,
)
from app.contexts.urim.deliverable.domain.citation import ALTERE, juger_parmi
from app.contexts.urim.deliverable.domain.documents import point_central_renseigne
from app.contexts.urim.domain.errors import (
    LivrableSansPlanError,
    PreparationIntrouvableError,
)
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex
from app.contexts.urim.infrastructure.corpus.readers import IndexedCorpusReader

DECK, NOTE = "deck", "note"

#: Le format natif de chaque document. Le PDF est une **conversion** demandée à la lecture, pas
#: un troisième document : il n'apparaît donc pas ici.
FORMAT_NATIF = {DECK: "pptx", NOTE: "docx"}


@dataclass(slots=True)
class LivrableDTO:
    record: LivrableRecord
    controles: list[ControleRecord]

    @property
    def conforme(self) -> bool:
        return self.record.validation == "conforme"


@dataclass(slots=True)
class UrimDeliverableService:
    studies: StudyRepository
    livrables: DeliverableRepository
    versets: VerseTextReader
    access: PreacherAuthorization
    index: CorpusIndex
    clock: object  # callable[[], datetime]
    _lecteur: IndexedCorpusReader | None = field(default=None, init=False, repr=False)

    async def soumettre(
        self,
        *,
        actor_account_id: UUID,
        study_id: UUID,
        kind: str = DECK,
        diapositives: list[DiapositiveSoumise] | None = None,
    ) -> LivrableDTO:
        record = await self.studies.get(study_id)
        if record is None:
            raise PreparationIntrouvableError("Cette préparation n'existe pas.")
        await ensure_may_read(self.access, actor_account_id, record)

        plan = await self._plan(study_id)
        if not point_central_renseigne(plan):
            # Le refus **oriente** — un refus qui n'oriente pas est une porte fermée (S2).
            raise LivrableSansPlanError(
                "Il n'y a pas encore de plan à imprimer. Le document met en page ce que vous "
                "avez écrit ; le moteur ne l'écrit pas à votre place."
            )

        controles = [
            await self._controler(rang, diapo, record.version_id)
            for rang, diapo in enumerate(diapositives or (), start=1)
        ]
        maintenant: datetime = self.clock()  # type: ignore[operator]
        conforme = all(c.verdict != ALTERE for c in controles)

        livrable = LivrableRecord(
            id=uuid4(),
            preparation_id=study_id,
            kind=kind,
            format=FORMAT_NATIF.get(kind, "pptx"),
            generated_at=maintenant,
            validation="conforme" if conforme else "rejete",
            # ⚠️ **Signé par celui qui valide, pas par l'auteur de la préparation.** Deux
            # pasteurs d'une même église se relisent ; celui qui monte en chaire répond de ce
            # qui sortira, et l'écran doit pouvoir le nommer.
            validated_by=actor_account_id if conforme else None,
            validated_at=maintenant if conforme else None,
            corpus_snapshot=self.index.snapshot,
            content_fingerprint=_empreinte(plan, controles),
        )
        await self.livrables.add(livrable, controles)
        return LivrableDTO(record=livrable, controles=controles)

    async def relire(
        self, *, actor_account_id: UUID, deliverable_id: UUID
    ) -> LivrableDTO:
        livrable = await self.livrables.get(deliverable_id)
        if livrable is None:
            raise PreparationIntrouvableError("Ce livrable n'existe pas.")
        # La garde est celle de la préparation : le livrable n'a pas de propriétaire propre,
        # il est une vue d'un travail qui, lui, en a un.
        record = await self.studies.get(livrable.preparation_id)
        if record is None:
            raise PreparationIntrouvableError("Ce livrable n'existe pas.")
        await ensure_may_read(self.access, actor_account_id, record)
        return LivrableDTO(
            record=livrable, controles=await self.livrables.controles(deliverable_id)
        )

    # -- le contrôle ------------------------------------------------------------

    async def _controler(
        self, rang: int, diapo: DiapositiveSoumise, version_id: UUID | None
    ) -> ControleRecord:
        lu = lire(diapo.reference, self.index)
        candidats = [
            ref for ref in lu.references if self._corpus().check_reference(ref).exists
        ]
        if not candidats:
            # ⚠️ **Le motif dit ce qui manque au CORPUS** (S19) : « Hébreux 2 compte 18
            # versets », jamais « référence invalide ». Et la diapositive est refusée sans
            # bloquer la lecture des autres — on rend le dossier entier, pas la première faute.
            motif = lu.motif or self._corpus().check_reference(
                lu.references[0]
            ).rationale
            return ControleRecord(
                slide_no=rang,
                reference=diapo.reference,
                projected_text=diapo.texte_projete,
                verdict=ALTERE,
                rationale=motif or "Cette référence n'est pas lisible.",
            )

        reference = candidats[0]
        servis = await self.versets.textes(
            book_id=self.index.book_by_label[reference.book],
            chapter=reference.chapter or 1,
            verse_start=reference.verse_start,
            verse_end=reference.verse_end,
            prefer_version_id=version_id,
        )
        verdict = juger_parmi(
            diapo.texte_projete, [(t.label, t.texte) for t in servis]
        )
        reconnue = next((t for t in servis if t.label == verdict.version), None)
        return ControleRecord(
            slide_no=rang,
            reference=diapo.reference,
            projected_text=diapo.texte_projete,
            verdict=verdict.verdict,
            rationale=verdict.rationale,
            version_id=reconnue.version_id if reconnue is not None else None,
        )

    # -- outils -----------------------------------------------------------------

    async def _plan(self, study_id: UUID) -> dict[str, str | None]:
        """Le squelette **replié par code** — `divisions` arrive en plusieurs lignes.

        On garde la première non vide : on cherche l'existence de ce qu'il a écrit, jamais le
        nombre de points de son plan."""
        plan: dict[str, str | None] = {}
        for element in await self.studies.list_elements(study_id):
            if (element.body or "").strip() and not (plan.get(element.element_code) or ""):
                plan[element.element_code] = element.body
        return plan

    def _corpus(self) -> IndexedCorpusReader:
        if self._lecteur is None:
            self._lecteur = IndexedCorpusReader(self.index)
        return self._lecteur


def _empreinte(plan: dict[str, str | None], controles: list[ControleRecord]) -> str:
    """Ce qui a été imprimé, réduit à trente-deux caractères.

    Deux documents de la même préparation à deux semaines d'écart ne sont pas le même document.
    L'empreinte couvre **le plan et ce qui monte à l'écran** — le reste (pesées, mises en garde)
    est du corpus, et `corpus_snapshot` en répond déjà."""
    matiere = "|".join(
        f"{code}={corps}" for code, corps in sorted(plan.items()) if corps
    ) + "||" + "|".join(
        f"{c.slide_no}:{c.reference}:{c.projected_text}" for c in controles
    )
    return hashlib.sha256(matiere.encode()).hexdigest()[:32]
