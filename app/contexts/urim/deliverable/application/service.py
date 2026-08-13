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
from dataclasses import dataclass, field, replace
from datetime import datetime
from uuid import UUID, uuid4

from app.contexts.urim.application.access import ensure_may_read
from app.contexts.urim.application.ports import PreacherAuthorization, StudyRepository
from app.contexts.urim.application.reference_libre import lire
from app.contexts.urim.deliverable.application.ports import (
    ControleRecord,
    DeliverableRepository,
    DiapositiveSoumise,
    EtudeReader,
    LivrableRecord,
    VerseTextReader,
)
from app.contexts.urim.deliverable.domain.citation import ALTERE, juger_parmi
from app.contexts.urim.deliverable.domain.documents import (
    Deck,
    Diapositive,
    Note,
    point_central_renseigne,
)
from app.contexts.urim.deliverable.infrastructure.renderers import (
    rendre_deck,
    rendre_note,
)
from app.contexts.urim.domain.errors import (
    LivrableNonValideError,
    LivrableSansPlanError,
    PreparationIntrouvableError,
)
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex, verses_between
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
    #: Le dossier complet d'une préparation — la seule source qui porte les pesées, les
    #: mises en garde et les motifs. C'est `UrimStudyService.get`, passé en port pour que
    #: la note n'ait pas à refaire un rejeu qui existe déjà.
    etude: EtudeReader
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

    async def rendre(
        self, *, actor_account_id: UUID, deliverable_id: UUID
    ) -> tuple[str, bytes]:
        """Les octets — **et seulement pour ce qui porte déjà `conforme`**.

        C'est ici que le verrou du produit devient un `if` d'une ligne, et il ne doit jamais en
        devenir un de deux : un chemin qui rendrait un fichier sans repasser par cette garde
        serait la porte dérobée que tout ce module existe pour fermer.

        ⚠️ **Générer ne consomme rien.** La note relit la préparation par `get`, qui rejoue le
        pipeline **sans persister** — et tout ce qui compte (`mark_assisted`, la re-clé, la
        trace de résolution) vit derrière `if persist:`. Un test tient cette propriété, parce
        qu'elle mourrait à la première refonte du rejeu."""
        dossier = await self.relire(
            actor_account_id=actor_account_id, deliverable_id=deliverable_id
        )
        if not dossier.conforme:
            raise LivrableNonValideError(
                "Ce livrable porte une citation qui n'est pas celle du corpus. "
                "Corrigez la diapositive, puis soumettez-la de nouveau."
            )

        if dossier.record.kind == NOTE:
            etude = await self.etude.get(
                actor_account_id=actor_account_id,
                study_id=dossier.record.preparation_id,
            )
            note = _note_depuis(etude)
            return FORMAT_NATIF[NOTE], rendre_note(self._developper(note))
        return FORMAT_NATIF[DECK], rendre_deck(_deck_depuis(dossier))

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

    def _developper(self, note: Note) -> Note:
        """Servir, sous chaque point, **les textes que le pasteur y a lui-même écrits**.

        C'est la seule façon de développer un point sans l'écrire. Les notes réelles portent
        leurs appuis dans la ligne même du point — *« il est couronné de gloire et d'honneur
        Hb 2v29 »* — et ces références n'avaient jusqu'ici aucune surface où être servies.

        ⚠️ **Ce qui ne résout pas s'imprime avec le motif du corpus**, jamais en silence :
        `Hb 2v29` et `Ph 28v9` sont deux vraies fautes des notes du Pasteur X, et c'est
        exactement là qu'Urim a quelque chose à dire."""
        lecteur = self._corpus()
        plan: list[tuple[str, str, tuple[tuple[str, str], ...]]] = []
        for code, corps, _ in note.plan:
            appuis: list[tuple[str, str]] = []
            for reference in _references_dans(corps, self.index):
                verdict = lecteur.check_reference(reference)
                libelle = _lisible_reference(reference)
                if not verdict.exists:
                    appuis.append((libelle, verdict.rationale))
                    continue
                livre = self.index.book_by_label[reference.book]
                debut = (reference.chapter or 1, reference.verse_start or 1)
                fin = (
                    reference.chapter or 1,
                    reference.verse_end or reference.verse_start or 999,
                )
                servi = " ".join(
                    v.body for v in verses_between(self.index, livre, debut, fin)
                )
                appuis.append((libelle, servi or verdict.rationale))
            plan.append((code, corps, tuple(appuis)))
        return replace(note, plan=tuple(plan))

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


def _deck_depuis(dossier: LivrableDTO) -> Deck:
    """Le deck se rebâtit depuis les **contrôles**, pas depuis une saisie neuve.

    C'est ce qui garantit que le fichier porte exactement ce qui a été jugé : redemander les
    diapositives au moment du rendu ouvrirait une seconde entrée, non contrôlée."""
    return Deck(
        titre=dossier.controles[0].reference if dossier.controles else "",
        diapositives=tuple(
            Diapositive(
                titre="", reference=c.reference, texte_projete=c.projected_text
            )
            for c in dossier.controles
        ),
    )


def _note_depuis(etude) -> Note:
    """La note se bâtit depuis le **dossier d'étude rejoué** — la seule source qui porte tout.

    ⚠️ Les mots de l'original n'y sont pas (`StudyDTO` ne les rend pas ; ils vivent dans la vue
    « en savoir plus sur un passage »). La section reste donc **vide et nommée** plutôt
    qu'inventée : une section muette se lit comme « ce passage n'a rien à montrer », ce qui est
    faux."""
    return Note(
        titre=etude.record.theme or "",
        reference=etude.resolved_label or "",
        unite=etude.pericope_label or "",
        motif_unite=next(
            (motif for code, motif in etude.trace if code == "bound_pericope"), ""
        ),
        plan=tuple(
            (element.element_code, element.body or "", ())
            for element in etude.elements
            if (element.body or "").strip()
        ),
        versets=tuple((verset.reference, verset.text) for verset in etude.verses),
        pesees=tuple(
            (pesee.label or pesee.axis_code, pesee.strength, pesee.rationale)
            for pesee in etude.bearings
        ),
        axe_retenu=etude.record.axis_code,
        mises_en_garde=tuple(etude.caveats),
        faisabilites=tuple(
            (
                f"{couple.plan_source} x {couple.subject_matter}",
                couple.feasible,
                couple.refusal_reason,
                couple.proof_text_risk,
            )
            for couple in etude.couples
        ),
        resistances=tuple(
            (resistant.label, resistant.rationale)
            for resistant in etude.resisting_elsewhere
        ),
        appuis=tuple(
            (reference, texte, verdict)
            for _brut, reference, texte, verdict in etude.supports
        ),
        original=(),
        ecartees=tuple(
            (libelle, motif)
            for _code, libelle, motif, _origine, ecartee in etude.options
            if ecartee
        ),
        signature=etude.pericope_reviewed_by,
        corpus_snapshot=etude.record.corpus_snapshot,
    )


def _references_dans(texte: str, index: CorpusIndex) -> list:
    """Les références écrites **dans une ligne de plan**, pas dans un champ dédié.

    Les notes réelles ne séparent pas les appuis du propos : « - il est couronné de gloire et
    d'honneur Hb 2v29 ». On balaie donc la ligne par empans — un nom de livre suivi de ses
    chiffres — avec la même lecture permissive que la chaîne de textes (`Hb 2v29`, `Jn14v28`).

    ⚠️ **On ne retient que le premier candidat de chaque empan.** `Jn` désigne quatre livres ;
    trancher ici serait décider à sa place, mais afficher les quatre noierait son point. Le
    corpus tranche par l'ordre du canon, et le contrôle de référence dira si c'est faux."""
    trouvees = []
    mots = texte.split()
    for debut in range(len(mots)):
        for taille in (4, 3, 2, 1):
            fenetre = mots[debut:debut + taille]
            if not fenetre or not _contigu(fenetre):
                continue
            # Un seul mot ne vaut que s'il **colle** lettres et chiffres — `Jn14v28`, la
            # notation réelle des notes. Sans cette exception on perd la forme la plus
            # fréquente ; sans la condition, « Jean » seul rouvrirait le piège S35.
            if len(fenetre) == 1 and not (
                any(c.isdigit() for c in fenetre[0])
                and any(c.isalpha() for c in fenetre[0])
            ):
                continue
            lu = lire(" ".join(fenetre), index)
            if lu.references and lu.references[0].chapter is not None:
                trouvees.append(lu.references[0])
                break
    # Deux empans voisins peuvent rendre la même référence ; on garde l'ordre du pasteur.
    vues, uniques = set(), []
    for reference in trouvees:
        cle = (reference.book, reference.chapter, reference.verse_start)
        if cle not in vues:
            vues.add(cle)
            uniques.append(reference)
    return uniques


def _contigu(fenetre: list[str]) -> bool:
    """🐛 **S35, et je suis tombé dedans en écrivant ce balayage.**

    Sur *« il a reçu le nom au dessus de tout nom Ph 28v9 »*, la lecture permissive a rendu
    **« Nombres 28:9 »** : `nom` est un nom de livre autant qu'un mot français, et rien
    n'exigeait qu'il soit suivi de chiffres. Job, Juges, Actes, Rois tendent le même piège.

    La règle qui referme : **tout ce qui suit le nom de livre doit être un chiffre ou un
    séparateur de verset.** « nom au dessus » tombe ; « Ph 28v9 » passe."""
    return all(
        any(caractere.isdigit() for caractere in mot)
        or mot.strip(".,;:").lower() in {"v", "vs", "c", "ch"}
        for mot in fenetre[1:]
    )


def _lisible_reference(reference) -> str:
    if reference.verse_start is None:
        return f"{reference.book} {reference.chapter}"
    if reference.verse_end and reference.verse_end != reference.verse_start:
        return f"{reference.book} {reference.chapter}:{reference.verse_start}-{reference.verse_end}"
    return f"{reference.book} {reference.chapter}:{reference.verse_start}"


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
