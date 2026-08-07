"""Le service d'étude — la **bordure d'ouverture** du moteur.

Le moteur est pur : il ne réserve rien, n'écrit rien, ne sait pas l'heure. Tout ce qui
l'entoure vit ici — l'autorisation, la réservation, la persistance des décisions, et le
rejeu.

**Le rejeu est le choix structurant.** On ne stocke pas la trace : on stocke les
décisions, et on refait tourner les huit étages pour la reconstituer. Deux vérités qui
peuvent diverger valent moins qu'une seule qu'on recalcule — et le déterminisme du moteur
est précisément ce qui rend ce calcul légitime. Sa contrepartie est `corpus_snapshot` :
si le corpus a bougé, la trace rejouée n'est plus celle du jour, et on le **dit**.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID, uuid4

from app.contexts.urim.application.ports import (
    ElementRecord,
    PreacherAuthorization,
    PreparationRecord,
    ReservationPort,
    StudyDTO,
    StudyRepository,
)
from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.domain.errors import (
    OptionInconnueError,
    PreparationIntrouvableError,
)
from app.contexts.urim.engine.deps import (
    ConvictionReader,
    EngineDeps,
    NullConvictionReader,
)
from app.contexts.urim.engine.normalizer import normalize
from app.contexts.urim.engine.pipeline import UrimEngine
from app.contexts.urim.engine.state import (
    Bounds,
    EntryMode,
    EntryOrigin,
    Reference,
    StudyState,
)
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex
from app.contexts.urim.infrastructure.corpus.readers import (
    IndexedCorpusReader,
    IndexedDoctrineReader,
    IndexedHomileticsReader,
    IndexedVersionResolver,
    RequestScope,
)

#: Fenêtre de lecture de l'archive personnelle pour l'étage du thème (E1).
_HORIZON_PRECHE = timedelta(days=180)


def _serialiser(ref: Reference | None) -> str | None:
    if ref is None:
        return None
    return "|".join((
        ref.book,
        str(ref.chapter or ""),
        str(ref.verse_start or ""),
        str(ref.verse_end or ""),
    ))


def _deserialiser(brut: str | None) -> Reference | None:
    if not brut:
        return None
    livre, ch, vs, ve = brut.split("|")
    return Reference(
        livre,
        int(ch) if ch else None,
        int(vs) if vs else None,
        int(ve) if ve else None,
    )


def _cle_provisoire(raw_input: str) -> str:
    """La clé de réservation **avant** de savoir sur quel texte on travaille.

    Dérivée de la saisie normalisée, donc stable : c'est elle qui permet de retrouver la
    réservation plus tard, quand la péricope sera enfin connue. Deux formulations du même
    passage en produisent deux différentes — c'est précisément le problème que le re-clage
    (S9) vient corriger, une fois le texte identifié."""
    return f"brut:{hashlib.sha256(normalize(raw_input).encode()).hexdigest()[:24]}"


def _afficher(ref: Reference | None) -> str | None:
    if ref is None:
        return None
    if ref.chapter is None:
        return ref.book
    if ref.verse_start is None:
        return f"{ref.book} {ref.chapter}"
    if ref.verse_end and ref.verse_end != ref.verse_start:
        return f"{ref.book} {ref.chapter}:{ref.verse_start}-{ref.verse_end}"
    return f"{ref.book} {ref.chapter}:{ref.verse_start}"


@dataclass(slots=True)
class UrimStudyService:
    studies: StudyRepository
    reservations: ReservationPort
    access: PreacherAuthorization
    index: CorpusIndex
    clock: object  # callable[[], datetime]
    #: Model-optional (S12, S37) : le défaut ne lit aucun modèle et ne casse rien.
    conviction: ConvictionReader = field(default_factory=NullConvictionReader)

    # -- ouverture -------------------------------------------------------------

    async def open(
        self,
        *,
        actor_account_id: UUID,
        church_id: UUID,
        raw_input: str,
        entry_mode: EntryMode,
        entry_origin: EntryOrigin = EntryOrigin.TYPED,
        service_date: date | None = None,
    ) -> StudyDTO:
        await self._ensure_preacher(actor_account_id, church_id)
        maintenant = self.clock()

        record = PreparationRecord(
            id=uuid4(),
            church_id=church_id,
            author_id=actor_account_id,
            raw_input=raw_input,
            entry_mode=entry_mode.value,
            entry_origin=entry_origin.value,
            corpus_snapshot=self.index.snapshot,
            service_date=service_date,
            opened_at=maintenant,
        )
        await self.studies.add(record)

        # Clé **provisoire** : la saisie normalisée. On ne sait pas encore sur quel texte
        # on travaille, et prétendre le contraire fausserait le décompte dès l'ouverture.
        # Le re-clage (S9) se fait dans `_rejouer`, dès que la péricope apparaît.
        await self.reservations.reserve(
            church_id=church_id,
            author_id=actor_account_id,
            pericope_key=_cle_provisoire(raw_input),
            at=maintenant,
        )
        return await self._rejouer(record, chosen_by="moteur")

    # -- lecture ---------------------------------------------------------------

    async def get(self, *, actor_account_id: UUID, study_id: UUID) -> StudyDTO:
        record = await self._charger(study_id)
        await self._ensure_preacher(actor_account_id, record.church_id)
        return await self._rejouer(record, persist=False)

    # -- décision --------------------------------------------------------------

    async def decide(
        self,
        *,
        actor_account_id: UUID,
        study_id: UUID,
        stage_code: str,
        option_code: str,
    ) -> StudyDTO:
        record = await self._charger(study_id)
        await self._ensure_preacher(actor_account_id, record.church_id)

        # La décision est **appliquée à l'enregistrement**, puis le pipeline est rejoué
        # depuis le début. C'est plus simple qu'une reprise à l'étage N, et c'est surtout
        # plus honnête : un choix amont peut changer ce que les étages avals proposent.
        self._appliquer(record, stage_code, option_code)
        await self.studies.save(record)
        return await self._rejouer(record, chosen_by="pasteur")

    def _appliquer(self, record: PreparationRecord, stage: str, option: str) -> None:
        if stage == "route_entry":
            if option not in {m.value for m in EntryMode}:
                raise OptionInconnueError(f"« {option} » n'est pas un mode d'entrée.")
            record.entry_mode = option
            return

        if stage == "resolve_passage":
            ref = self._reference_depuis_libelle(option)
            if ref is None:
                raise OptionInconnueError(f"« {option} » ne désigne aucun passage connu.")
            record.resolved_ref = _serialiser(ref)
            return

        if stage == "bound_pericope":
            if option == "tel_quel":
                # Le pasteur force ses bornes. `pericope_id` retombe à None, et **tout ce
                # qui est curé devient illisible** pour les étages avals — pesées, mises
                # en garde, faisabilité. S22 est mécanique, pas déclaratif.
                record.pericope_id = None
                record.bounds_overridden = True
                return
            try:
                record.pericope_id = UUID(option)
            except ValueError as exc:
                raise OptionInconnueError(
                    f"« {option} » n'est pas une unité littéraire connue."
                ) from exc
            record.bounds_overridden = False
            return

        if stage == "shape_homiletic":
            if ":" not in option:
                raise OptionInconnueError(f"« {option} » n'est pas un couple plan x matière.")
            record.plan_source, record.subject_matter = option.split(":", 1)
            return

        if stage == "weigh_conviction":
            # Deux décisions distinctes sortent du même étage — d'où le préfixe explicite.
            # Le déduire de la forme (« ça ressemble à un UUID donc c'est un texte ») aurait
            # marché et se serait cassé au premier axe nommé comme un identifiant.
            if option.startswith("axe:"):
                record.axis_code = option.removeprefix("axe:")
                return
            if option.startswith("texte:"):
                try:
                    unite = UUID(option.removeprefix("texte:"))
                except ValueError as exc:
                    raise OptionInconnueError(
                        f"« {option} » n'est pas une unité littéraire connue."
                    ) from exc
                # On pose la **référence**, pas la péricope : l'étage 2 refait son travail,
                # constate que les bornes coïncident et continue sans interrompre (D-E). Le
                # chemin inversé rejoint ainsi le pipeline sans qu'aucun étage aval n'ait de
                # cas particulier à connaître.
                cible = next(
                    (p for p in self.index.pericopes if p.id == unite), None
                )
                if cible is None:
                    raise OptionInconnueError(
                        f"« {option} » n'est pas une unité littéraire connue."
                    )
                livre = self.index.label_by_book.get(cible.book_id, "")
                record.resolved_ref = _serialiser(
                    Reference(livre, cible.start_ch, cible.start_v, cible.end_v)
                )
                return
            raise OptionInconnueError(f"« {option} » n'est pas une option de cet étage.")

        if stage == "bear_axes":
            record.axis_code = option
            return

        if stage == "propose_theme":
            record.theme = option
            return

        raise OptionInconnueError(f"L'étage « {stage} » n'attend aucune décision.")

    def _reference_depuis_libelle(self, texte: str) -> Reference | None:
        """« 1 Jean 3:16 » → Reference. Le libellé le plus long gagne.

        On ne devine pas où finit le nom du livre : on le **cherche** dans l'ensemble des
        libellés connus, du plus long au plus court. « Jean » est un préfixe de « 1 Jean »
        seulement si on lit à l'envers ; en partant des libellés, l'ambiguïté disparaît."""
        for libelle in sorted(self.index.book_by_label, key=len, reverse=True):
            if texte == libelle:
                return Reference(libelle)
            if texte.startswith(libelle + " "):
                reste = texte[len(libelle) + 1:].strip()
                if ":" not in reste:
                    return Reference(libelle, int(reste)) if reste.isdigit() else None
                ch, versets = reste.split(":", 1)
                if not ch.isdigit():
                    return None
                if "-" in versets:
                    a, b = versets.split("-", 1)
                    if a.isdigit() and b.isdigit():
                        return Reference(libelle, int(ch), int(a), int(b))
                    return None
                return Reference(libelle, int(ch), int(versets)) if versets.isdigit() else None
        return None

    # -- squelette homilétique -------------------------------------------------

    async def set_elements(
        self, *, actor_account_id: UUID, study_id: UUID, elements: Sequence[ElementRecord]
    ) -> StudyDTO:
        record = await self._charger(study_id)
        await self._ensure_preacher(actor_account_id, record.church_id)
        # Champs **libres**. Le squelette (Braga ou autre) propose un ordre ; il n'impose
        # aucun contenu, et un élément vide reste un état normal.
        await self.studies.set_elements(study_id, list(elements))
        return await self._rejouer(record, persist=False)

    # -- rejeu ------------------------------------------------------------------

    async def _rejouer(
        self, record: PreparationRecord, *, persist: bool = True, chosen_by: str | None = None
    ) -> StudyDTO:
        maintenant = self.clock()
        usage = await self.reservations.usage(record.church_id, maintenant)
        axes = await self.studies.recently_preached_axes(
            record.author_id, (maintenant - _HORIZON_PRECHE).date()
        )
        portee = RequestScope(
            preached_axes=tuple(axes), ceiling_reached=usage.ceiling_reached
        )
        deps = EngineDeps(
            corpus=IndexedCorpusReader(self.index),
            doctrine=IndexedDoctrineReader(self.index),
            homiletics=IndexedHomileticsReader(self.index, portee),
            # ⚠ AFFICHAGE SEUL — transmis à la présentation, jamais lu par un étage.
            context=NullEcclesialContext(),
            versions=IndexedVersionResolver(self.index, portee),
            clock=lambda: maintenant,
            conviction=self.conviction,
        )

        # Le risque est une propriété de la **saisie**, pas une étape du raisonnement : il se
        # lève ici, une fois, et il survit au rejeu sans colonne dédiée puisqu'il se recalcule
        # à l'identique depuis `raw_input`. L'étage qui le lira dira son effet ; celui-ci ne
        # fait que le porter.
        drapeaux = tuple(self.conviction.risk_flags(record.raw_input))

        resolu = _deserialiser(record.resolved_ref)
        etat = StudyState(
            session_id=record.id,
            church_id=record.church_id,
            author_id=record.author_id,
            corpus_snapshot=record.corpus_snapshot or self.index.snapshot,
            entry_mode=EntryMode(record.entry_mode or EntryMode.REFERENCE.value),
            raw_input=record.raw_input,
            entry_origin=EntryOrigin(record.entry_origin or EntryOrigin.TYPED.value),
            risk_flags=drapeaux,
            resolved=resolu,
            bounds=self._bornes(record),
            pericope_id=record.pericope_id,
            bounds_overridden=record.bounds_overridden,
            version_id=record.version_id,
            axis=record.axis_code,
            plan_source=record.plan_source,
            subject_matter=record.subject_matter,
            theme=record.theme,
        )

        run = UrimEngine(deps).run(etat)
        final = run.state
        dernier = run.results[-1] if run.results else None

        if persist:
            avant_ref = record.resolved_ref

            # Ce que le moteur a établi de lui-même redescend dans l'enregistrement :
            # c'est ce qui permet au rejeu suivant de repartir du même point.
            record.resolved_ref = _serialiser(final.resolved)
            record.pericope_id = final.pericope_id
            record.bounds_overridden = final.bounds_overridden
            record.version_id = final.version_id
            record.axis_code = final.axis
            record.plan_source = final.plan_source
            record.subject_matter = final.subject_matter
            record.theme = final.theme
            await self.studies.save(record)

            # ⚠️ **Seulement quand la résolution change.** Un rejeu n'est pas une
            # tentative : rejouer dix fois la même préparation ne veut pas dire que le
            # passage a été cherché dix fois. Écrire à chaque passage noierait la
            # provenance — qui a tranché, et quand — sous des milliers de doublons.
            if final.resolved is not None and record.resolved_ref != avant_ref:
                await self.studies.record_attempt(
                    study_id=record.id,
                    input_hash=hashlib.sha256(
                        normalize(record.raw_input).encode()
                    ).hexdigest()[:32],
                    candidates=[_afficher(final.resolved) or ""],
                    chosen_ref=record.resolved_ref,
                    chosen_by=chosen_by or "moteur",
                    at=maintenant,
                )

            # S9 — le re-clage se joue **ici**, pas à l'ouverture. Au moment d'ouvrir, la
            # péricope n'est presque jamais connue : le moteur rend justement la main pour
            # la faire choisir. La réservation ne peut donc se caler sur le texte qu'au
            # premier rejeu où `pericope_id` apparaît.
            #
            # Appelé **à chaque rejeu**, sans garde sur le changement : la décision vient
            # justement d'écrire `pericope_id`, donc comparer à l'état d'avant ne dirait
            # jamais rien. C'est `rekey_for` qui est idempotent — il cherche la clé
            # provisoire, et ne la trouve plus une fois le re-clage fait.
            if final.pericope_id is not None:
                await self.reservations.rekey_for(
                    church_id=record.church_id,
                    provisional_key=_cle_provisoire(record.raw_input),
                    pericope_key=f"pericope:{final.pericope_id}",
                    at=maintenant,
                )

        return StudyDTO(
            record=record,
            outcome=str(dernier.outcome) if dernier else "continue",
            rationale=dernier.rationale if dernier else "",
            trace=tuple((e.stage_code, e.rationale) for e in final.trace),
            options=tuple(
                (o.code, o.label, o.rationale) for o in (dernier.options if dernier else ())
            ),
            elements=tuple(await self.studies.list_elements(record.id)),
            resolved_label=_afficher(final.resolved),
            corpus_drifted=(
                record.corpus_snapshot is not None
                and record.corpus_snapshot != self.index.snapshot
            ),
        )

    def _bornes(self, record: PreparationRecord) -> Bounds | None:
        """Reconstituer les bornes d'une décision déjà prise — **les deux cas**.

        ⚠️ C'est `bounds` — pas `pericope_id` — qui dit à l'étage 2 qu'il a fini
        (`applies` : `resolved is not None and bounds is None`). Ne le poser que pour le
        bornage forcé faisait reposer indéfiniment la même question au pasteur qui avait
        pourtant choisi son unité : sa décision était enregistrée, et invisible pour le
        seul étage qui la lisait.

        Les bornes d'une unité curée se relisent donc dans le corpus, à l'identique de ce
        que l'étage aurait posé. Le corpus étant immuable, les deux ne peuvent pas
        diverger."""
        if record.pericope_id is not None:
            unite = next(
                (p for p in self.index.pericopes if p.id == record.pericope_id), None
            )
            if unite is not None:
                livre = self.index.label_by_book.get(unite.book_id, "")
                return Bounds(
                    start=Reference(livre, unite.start_ch, unite.start_v),
                    end=Reference(livre, unite.end_ch, unite.end_v),
                )

        if record.bounds_overridden:
            # Le pasteur garde sa demande telle quelle : elle **est** ses bornes.
            resolu = _deserialiser(record.resolved_ref)
            return Bounds(start=resolu, end=resolu) if resolu is not None else None

        return None

    # -- garde -----------------------------------------------------------------

    async def _charger(self, study_id: UUID) -> PreparationRecord:
        record = await self.studies.get(study_id)
        if record is None:
            raise PreparationIntrouvableError("Cette préparation n'existe pas.")
        return record

    async def _ensure_preacher(self, actor_account_id: UUID, church_id: UUID) -> None:
        # **Quelle** permission cela recouvre est décidé par l'adaptateur, pas ici. Le
        # service pose une question de droit ; il n'a pas à connaître le vocabulaire des
        # rôles d'un autre contexte.
        await self.access.ensure_may_prepare(
            account_id=actor_account_id, church_id=church_id
        )
