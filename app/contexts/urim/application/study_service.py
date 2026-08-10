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

import asyncio
import hashlib
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID, uuid4

from app.contexts.urim.application.ports import (
    AssistedResolver,
    ConcordanceDTO,
    ElementRecord,
    NullVerseResolver,
    PassageDetailDTO,
    PreacherAuthorization,
    PreparationRecord,
    ReservationPort,
    StudyDTO,
    StudyRepository,
    SupportRecord,
    VariantSeen,
    VerseServed,
)
from app.contexts.urim.application.reference_libre import lire
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
from app.contexts.urim.engine.normalizer import tokens as decouper
from app.contexts.urim.engine.outcomes import Outcome
from app.contexts.urim.engine.pipeline import UrimEngine
from app.contexts.urim.engine.stages.resolve_passage import PAS_UNE_CITATION
from app.contexts.urim.engine.stages.route_entry import REFORMULER
from app.contexts.urim.engine.state import (
    Bounds,
    EntryMode,
    EntryOrigin,
    PassageSuggestion,
    Reference,
    StudyState,
)
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex, verses_between
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


#: Combien d'occurrences on rend au plus. `δοῦλος` en compte 126 — au-delà d'une cinquantaine,
#: la liste cesse d'être lue. Le compte réel voyage toujours à côté (`total`) : on écourte, on
#: ne dissimule pas.
_OCCURRENCES_MAX = 50

#: Combien de textes résistants on rapporte d'ailleurs. Trois : au-delà, la page devient une
#: bibliographie et le pasteur n'en lit aucun — ce qui revient exactement à n'en montrer aucun.
_RESISTANTS_MAX = 3


def _resistent_ailleurs(index: CorpusIndex, axe: str | None, unite: UUID | None):
    """Les **autres** unités qui compliquent l'axe retenu.

    ⚠️ Ce n'est pas un « voir aussi ». C'est la seule chose qui empêche Urim d'être un moteur
    de proof-texting sur le chemin référence : un pasteur qui tape « Romains 8 » a déjà son
    idée, et il doit rencontrer 2 Corinthiens 12:7-10 — une écharde non retirée, trois prières
    sans réponse, présentée comme une grâce.

    Le chemin intention l'affichait depuis toujours (`sites_by_axis`), le chemin référence non.
    Or c'est celui qui en a le plus besoin : l'intention cherche encore, la référence sait déjà.

    L'unité courante est exclue — ce qu'elle complique elle-même est déjà dans `bearings`, et
    l'y voir deux fois ferait douter de la première.

    ⚠️ **La sélection est étalée sur le canon, pas prise au début.** `sites_by_axis` est trié
    dans l'ordre canonique : prendre les trois premiers rendait 1 Chroniques 5, 9 et 10 — trois
    chapitres voisins portant la même objection, et une fois toute l'Écriture pesée ce sera
    toujours la Genèse. Un texte par livre, puis trois positions régulièrement espacées : le
    pasteur reçoit une objection de la Loi, une des Prophètes, une des Épîtres.

    Reste déterministe, donc rejouable — c'est la condition, et elle exclut tout tirage."""
    if not axe:
        return ()
    resistants: list = []
    livres: set[int] = set()
    for site in index.sites_by_axis.get(axe, ()):
        if site.strength != "resiste" or site.pericope_id == unite:
            continue
        # Un livre ne parle qu'une fois : trois chapitres voisins disent la même chose, et la
        # répétition prend la place d'un texte qui aurait dit autre chose.
        livre = _livre_de(index, site.pericope_id)
        if livre in livres:
            continue
        livres.add(livre)
        resistants.append(site)

    if len(resistants) <= _RESISTANTS_MAX:
        return tuple(resistants)
    pas = (len(resistants) - 1) / (_RESISTANTS_MAX - 1)
    return tuple(resistants[round(rang * pas)] for rang in range(_RESISTANTS_MAX))


def _livre_de(index: CorpusIndex, pericope_id: UUID) -> int:
    return next(
        (p.book_id for p in index.pericopes if p.id == pericope_id), -1
    )


#: Les deux étages dont le refus signifie « je n'ai pas trouvé », et non « voici un fait ».
#:
#: `resolve_passage` sur une citation : la recherche par la lettre n'a rien rendu. Et
#: `weigh_conviction` : aucune unité relue ne porte l'axe. Les deux disent le même vide — celui
#: du corpus, pas celui de la saisie —, et c'est ce vide-là qu'une proposition comble.
_IMPASSES_DE_RECHERCHE = frozenset({"resolve_passage", "weigh_conviction"})


def _est_une_impasse_de_recherche(run) -> bool:
    """La recherche a-t-elle **échoué à trouver le sens**, ou rendu un fait sur la saisie ?

    ⚠️ **Ce n'est pas seulement le refus.** J'avais d'abord gardé les deux `REFUSE` — « aucun
    texte ne porte cette formulation » et « aucune unité relue ne porte cet axe ». Le second a
    disparu tout seul le jour où les dix loci ont été pesés sur toute l'Écriture, et le premier
    est presque inatteignable : une affinité assez forte pour router en citation implique
    qu'un verset a été trouvé. Je visais deux portes dont l'une est murée et l'autre rare.

    La vraie impasse est celle que le pasteur voit : **plusieurs candidats faibles**.
    « L'amour du prochain » rendait cinq versets — dont Jean 5:42 — trouvés sur des mots
    partagés et non sur le sens. Le moteur n'échouait pas bruyamment, il répondait à côté, ce
    qui est pire parce que ça ressemble à une réponse.

    Reste exclu : le chemin référence. « Je ne connais pas de livre nommé Zorobabel » est un
    fait sur l'orthographe, et y répondre par des passages thématiques noierait la seule
    information utile."""
    if not run.results:
        return False
    verdict = run.results[-1].outcome
    dernier = run.state.trace[-1].stage_code if run.state.trace else ""
    if dernier not in _IMPASSES_DE_RECHERCHE:
        return False
    if dernier == "weigh_conviction":
        # ⚠️ **L'écran des axes est une impasse de plus, et je ne la voyais pas.**
        #
        # « Je veux faire un culte sur l'adultère » rendait les dix loci et **rien d'autre** :
        # pas un verset, pas un texte. Formellement c'est un `AWAIT` — le moteur pose une
        # question, il n'échoue pas. Du côté du pasteur c'est un mur : il a nommé son sujet et
        # reçoit dix mots grecs.
        #
        # Les passages proposés s'ajoutent donc ici aussi, à côté des dix. Choisir un angle
        # reste le chemin qui donne les textes **pesés** ; aller droit à un texte reste
        # possible, et le pipeline entier tourne derrière ce choix-là comme derrière l'autre.
        return verdict in (Outcome.REFUSE, Outcome.AWAIT)
    # `resolve_passage` : la branche citation seulement, et **l'hésitation autant que le
    # refus**. Rien n'est retiré — les candidats lexicaux restent, les passages s'ajoutent.
    return run.state.entry_mode is EntryMode.CITATION and verdict in (
        Outcome.REFUSE, Outcome.AWAIT,
    )


def _chapitre_verset(reference: str) -> tuple[int, int]:
    """« Romains 8:1 » → `(8, 1)`. Le libellé vient d'être fabriqué par `_texte_servi`, donc
    sa forme est connue — c'est le seul endroit où l'on peut se permettre de le relire."""
    _, _, fin = reference.rpartition(" ")
    chapitre, _, verset = fin.partition(":")
    return int(chapitre), int(verset)


#: Les tournures dont le modèle préfixe un nom de livre. Le corpus, lui, dit « Jean »,
#: « Romains », « Joël » — le vocabulaire des biblistes, pas celui d'une table des matières.
_PREFIXES_DE_GENRE: tuple[tuple[str, ...], ...] = (
    ("evangile", "selon"), ("evangile", "de"),
    ("lettre", "aux"), ("lettre", "a"), ("lettre", "de"),
    ("epitre", "aux"), ("epitre", "a"), ("epitre", "de"),
    ("livre", "des"), ("livre", "de"), ("livre", "du"),
    ("actes", "des"),
    ("psaume",), ("apocalypse", "de"),
)


def _lisible(saisie: str) -> str:
    """La saisie **dé-stylisée**, telle qu'un modèle sait la lire.

    ⚠️ Un pasteur qui recopie son thème depuis WhatsApp l'envoie souvent en caractères
    mathématiques (« MATHEMATICAL ITALIC »). Le moteur, lui, s'en accommode : son
    normaliseur les replie déjà. Le **modèle** non : sur la version stylisée il a rendu Actes 2,
    Éphésiens 2, 1 Pierre 2 ; sur la même phrase en caractères ordinaires, **Actes 1:8 en
    premier** — le texte que le pasteur a effectivement prêché.

    NFKC replie les variantes typographiques sur leurs lettres, NFC recompose les accents
    décomposés (`e` + accent aigu → `é`). On ne passe **pas** par `normalize` du moteur : elle
    dépouille les accents et la casse, ce qui aide à comparer des tokens et nuit à un modèle de
    langue — il lit du français, pas des clés d'index."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFKC", saisie))


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
    #: L'IA de la bordure. Sans clé, `NullVerseResolver` — et Urim tourne entier.
    resolver: AssistedResolver = field(default_factory=NullVerseResolver)

    # -- ouverture -------------------------------------------------------------

    async def open(
        self,
        *,
        actor_account_id: UUID,
        church_id: UUID,
        raw_input: str,
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
            # `entry_mode` reste **vide** : personne n'a rien indiqué. L'étage 0 le posera,
            # et il ne descendra en base que si le pasteur corrige lui-même.
            entry_mode=None,
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
        if stage_code == "route_entry" and option_code == REFORMULER:
            # Le garde-fou du micro resté ouvert. L'étage 0 proposait ce bouton et l'API le
            # refusait en 422 : une porte offerte, puis claquée. Elle **rouvre la saisie sans
            # rien conserver** — la préparation est abandonnée, pas corrigée.
            record.status = "abandonnee"
            record.closed_at = self.clock()
            await self.studies.save(record)
            return await self._rejouer(record, persist=False)

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
            if option == PAS_UNE_CITATION:
                # ⚠️ **La sortie du chemin citation.** « L'amour du prochain » est un thème
                # écrit en mots bibliques : l'étage 0 y voit un recouvrement fort, l'étage 1
                # aligne cinq versets, et le pasteur n'avait aucun moyen de dire qu'il
                # n'avait jamais cité. Le mode est corrigé et le pipeline rejoué depuis le
                # début — c'est une correction d'entrée, pas une résolution de passage, d'où
                # l'écriture sur `entry_mode` et non sur `resolved_ref`.
                record.entry_mode = EntryMode.CONVICTION.value
                record.resolved_ref = None
                return
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
            # ⚠️ **Le passage proposé par le sens, désigné par son libellé.**
            #
            # Les deux préfixes couvraient tout tant que cet étage ne proposait que des axes
            # et des unités curées. En y ajoutant les passages du modèle — « Genèse 2:24-25 »,
            # sans préfixe, parce que le libellé EST la référence — j'ai fabriqué six options
            # que le service refusait au clic. Le défaut ne se voyait pas dans la réponse :
            # elle était juste, c'est le coup d'après qui tombait.
            #
            # Le libellé se relit ici comme à l'étage 1, et l'existence est **vérifiée** : un
            # code fabriqué à la main ne doit pas poser une référence que le corpus ignore.
            reference = self._reference_depuis_libelle(option)
            if reference is not None and IndexedCorpusReader(self.index).check_reference(
                reference
            ).exists:
                record.resolved_ref = _serialiser(reference)
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

    # -- la chaîne de textes ----------------------------------------------------

    async def set_supports(
        self, *, actor_account_id: UUID, study_id: UUID, saisies: Sequence[str]
    ) -> StudyDTO:
        """Les textes d'appui du sermon — **et le contrôle de référence enfin utile**.

        Un sermon convoque une chaîne : le Pasteur X en a aligné huit, puis douze. Le modèle
        n'en tenait qu'un, celui qu'on prêche, et le reste vivait dans ses notes — dont deux
        références inexistantes (`Hb 2v29`, `Ph 28v9`) qu'Urim savait détecter depuis toujours
        et n'avait jamais vues, faute d'une surface où il les soumette.

        ⚠️ **Une saisie illisible n'interrompt rien** (S19). Elle est conservée telle quelle,
        avec son motif à l'affichage ; refuser la liste entière ferait perdre onze textes
        justes pour une faute de frappe, et c'est le contraire du service rendu."""
        record = await self._charger(study_id)
        await self._ensure_preacher(actor_account_id, record.church_id)

        lecteur = IndexedCorpusReader(self.index)
        retenues: list[SupportRecord] = []
        for brut in saisies:
            lu = lire(brut, self.index)
            # Le **premier candidat qui existe** — `Jn 14:28` désigne quatre livres, et un
            # seul de ces quatre a un chapitre 14. Le corpus tranche là où il peut ; là où
            # plusieurs tiennent, l'ordre du canon décide, et le pasteur corrigera.
            valide = next(
                (r for r in lu.references if lecteur.check_reference(r).exists), None
            )
            livre = self.index.book_by_label.get(valide.book) if valide else None
            retenues.append(SupportRecord(
                raw=brut.strip(),
                book_id=livre,
                chapter=valide.chapter if valide else None,
                verse_start=valide.verse_start if valide else None,
                verse_end=valide.verse_end if valide else None,
            ))

        await self.studies.set_supports(study_id, retenues)
        return await self._rejouer(record, persist=False)

    def _appuis(self, supports: Sequence[SupportRecord]) -> tuple[tuple[str, ...], ...]:
        """Chaque appui → `(saisie, référence, texte, motif)`.

        Le motif se **recalcule** ici plutôt que de dormir en base : `hb` est entré au corpus
        cette semaine, et une référence refusée hier peut être lue aujourd'hui. Figer le refus
        aurait gelé une ignorance."""
        lecteur = IndexedCorpusReader(self.index)
        rendus: list[tuple[str, ...]] = []
        for support in supports:
            if support.book_id is not None:
                libelle = self.index.label_by_book.get(support.book_id, "")
                ref = Reference(
                    libelle, support.chapter, support.verse_start, support.verse_end
                )
                servis, _ = self._texte_servi(
                    StudyState(
                        session_id=uuid4(), church_id=uuid4(), author_id=uuid4(),
                        corpus_snapshot=self.index.snapshot,
                        entry_mode=EntryMode.REFERENCE, raw_input=support.raw,
                        resolved=ref, bounds=Bounds(start=ref, end=ref),
                    )
                )
                texte = " ".join(v.text for v in servis)
                rendus.append((support.raw, _afficher(ref) or "", texte, ""))
                continue

            # Non résolu : on redit **pourquoi**, avec les mots du corpus.
            lu = lire(support.raw, self.index)
            motif = lu.motif
            if not motif and lu.references:
                motif = next(
                    (
                        verdict.rationale
                        for r in lu.references
                        if not (verdict := lecteur.check_reference(r)).exists
                        and verdict.rationale
                    ),
                    "Référence introuvable dans ce corpus.",
                )
            rendus.append((support.raw, "", "", motif or "Référence illisible."))
        return tuple(rendus)

    # -- exploration ------------------------------------------------------------

    async def explorer(
        self, *, actor_account_id: UUID, church_id: UUID, reference: str
    ) -> PassageDetailDTO:
        """**En savoir plus sur un passage, sans s'engager dessus.**

        Le pasteur à qui l'on propose six passages veut les ouvrir avant de choisir : ce qu'ils
        portent, ce sur quoi les traditions divergent, ce que les manuscrits disent. Jusqu'ici
        il fallait *ouvrir une préparation* pour lire tout cela — donc réserver, écrire, et
        s'engager sur un texte qu'on voulait seulement regarder.

        ⚠️ **Lecture pure.** Aucune écriture, aucune réservation, aucun appel de modèle : tout
        est déjà dans l'index. C'est ce qui permet de l'appeler six fois de suite sans
        conséquence, et c'est la raison pour laquelle cette route ne passe pas par le moteur.

        ⚠️ **Les DIX pesées, `absent` compris.** L'écran de préparation n'affiche que ce qui
        porte ; ici on montre tout, parce qu'un locus marqué `absent` est une information — un
        relecteur a regardé et le texte n'en dit rien — et qu'un locus manquant en est une
        autre : personne n'a regardé. Les confondre est précisément ce que `reviewed_by`
        existe pour empêcher."""
        await self._ensure_preacher(actor_account_id, church_id)

        ref = self._reference_depuis_libelle(reference.strip())
        if ref is None:
            raise OptionInconnueError(f"« {reference} » ne désigne aucun passage connu.")
        if not IndexedCorpusReader(self.index).check_reference(ref).exists:
            raise OptionInconnueError(f"« {reference} » n'existe pas dans ce corpus.")

        # ⚠️ **Une seule unité, ou aucune curation attachée.**
        #
        # `pericopes_for` rend toutes les unités qui *chevauchent* la demande. Je prenais la
        # première : « Luc 10:25-37 » rendait alors les quatre versets du dialogue avec le
        # docteur de la loi, et les pesées de cette unité-là — sans le bon Samaritain, et sans
        # que rien ne le signale. Un écran d'étude qui montre silencieusement autre chose que
        # ce qu'on a demandé est pire qu'un écran vide.
        #
        # Quand plusieurs unités couvrent la demande, la curation ne s'attache donc à aucune :
        # elles sont **nommées**, et le pasteur ouvre celle qu'il veut lire.
        unites = list(IndexedCorpusReader(self.index).pericopes_for(ref))
        seule = unites[0] if len(unites) == 1 else None
        unite = next(
            (p for p in self.index.pericopes if seule and p.id == seule.id), None
        )
        pid = unite.id if unite else None

        etat = StudyState(
            session_id=uuid4(), church_id=church_id, author_id=actor_account_id,
            corpus_snapshot=self.index.snapshot, raw_input=reference,
            # `entry_mode` est requis par l'état mais n'a **aucun sens ici** : personne n'entre,
            # on regarde. `REFERENCE` est le plus proche du geste — un passage désigné — et
            # aucun étage ne le lira, puisque le moteur n'est pas appelé.
            entry_mode=EntryMode.REFERENCE,
            resolved=ref,
            # **Le texte demandé, pas celui de l'unité.** On regarde ce qu'on a désigné.
            bounds=Bounds(start=ref, end=ref),
            pericope_id=pid,
        )
        servis, variantes = self._texte_servi(etat)
        livre = self.index.book_by_label.get(ref.book)

        return PassageDetailDTO(
            reference=_afficher(ref) or reference,
            units=tuple(
                (str(u.id), u.label, _afficher(u.bounds.start) or "", u.rationale)
                for u in unites
            ),
            pericope_id=pid,
            pericope_label=(unite.label or None) if unite else None,
            pericope_rationale=unite.rationale if unite else None,
            reviewed_by=(unite.reviewed_by or None) if unite else None,
            verses=servis,
            variants=variantes,
            bearings=self.index.bearings.get(pid, ()),
            caveats=self.index.caveats.get(pid, ()),
            context=self.index.notes.get(pid, ()),
            couples=self.index.couples.get(pid, ()),
            resisting_elsewhere=_resistent_ailleurs(
                self.index, self.index.dominant.get(pid) if pid else None, pid
            ),
            # L'original **du texte servi**, pas de l'unité : on annote ce qu'on affiche.
            original=tuple(
                (v.reference, mot.position, mot.surface, mot.lemma, mot.pos, mot.parsing,
                 mot.language)
                for v in servis
                for mot in self.index.originals.get(
                    (livre, *_chapitre_verset(v.reference)), ()
                )
            ) if livre is not None else (),
        )

    async def concordance(
        self, *, actor_account_id: UUID, church_id: UUID, lemme: str
    ) -> ConcordanceDTO:
        """Toutes les occurrences d'un mot de l'original — **lecture pure, sans modèle**.

        C'est la première pierre du module de recherche, et la seule qui ne puisse rien
        inventer : elle montre le texte, elle ne dit rien sur le monde. `ὑπόδημα` répond à la
        question du fils prodigue sans qu'aucune note ait à affirmer que les esclaves allaient
        pieds nus — Jean-Baptiste dit lui-même que délier la sandale est au-dessous de lui.

        ⚠️ **Rien n'est tronqué en silence.** `δοῦλος` paraît 126 fois ; `total` porte le
        compte réel et `occurrences` ce qu'on en montre. Un extrait présenté comme un tout
        ferait conclure d'un échantillon."""
        await self._ensure_preacher(actor_account_id, church_id)

        lieux = self.index.occurrences_by_lemma.get(lemme.strip(), ())
        if not lieux:
            raise OptionInconnueError(
                f"« {lemme} » ne paraît dans aucun texte original de ce corpus."
            )

        langue = "grc"
        rendues: list[tuple[str, str, str, str]] = []
        for livre, chapitre, verset, rang in lieux[:_OCCURRENCES_MAX]:
            mots = self.index.originals.get((livre, chapitre, verset), ())
            if rang >= len(mots):
                continue
            mot = mots[rang]
            langue = mot.language
            libelle = self.index.label_by_book.get(livre, "")
            rendues.append((
                f"{libelle} {chapitre}:{verset}",
                self._texte_du_verset(livre, chapitre, verset),
                mot.surface,
                mot.parsing or mot.pos,
            ))

        return ConcordanceDTO(
            lemma=lemme.strip(), language=langue, total=len(lieux),
            occurrences=tuple(rendues),
        )

    def _texte_du_verset(self, livre: int, chapitre: int, verset: int) -> str:
        servis = verses_between(self.index, livre, (chapitre, verset), (chapitre, verset))
        return servis[0].body if servis else ""

    async def _passages_verifies(self, saisie: str) -> tuple[PassageSuggestion, ...]:
        """Les passages proposés par le sens, **vérifiés un par un contre les 31 170 versets**.

        ⚠️ M9-1, appliqué ici sans exception : *l'IA nomme la référence, la Segond donne le
        texte*. Un modèle qui se trompe de bornes — Job 41 fait 34 versets chez lui, 25 en
        Segond — proposerait un passage dont le texte n'existe pas, et le pasteur ne le
        découvrirait qu'en l'ouvrant.

        Une proposition qui tombe à un seul passage est **abandonnée** : elle aurait l'autorité
        d'une résolution sans en avoir passé les vérifications, et c'est précisément le
        proof-texting qu'on refuse."""
        proposes = await self.resolver.passages(saisie)
        lecteur = IndexedCorpusReader(self.index)
        retenus = tuple(
            recale for propose in proposes
            if (recale := self._recaler(propose)) is not None
            and lecteur.check_reference(recale.reference).exists
        )
        return retenus if len(retenus) > 1 else ()

    def _recaler(self, propose: PassageSuggestion) -> PassageSuggestion | None:
        """Le nom de livre du modèle, **ramené au vocabulaire du corpus**.

        ⚠️ **Sans cela, les meilleurs passages étaient jetés en silence.** Le modèle nomme les
        livres au long — « Actes des Apôtres », « Évangile selon Jean », « Lettre aux Romains »
        — là où `check_reference` compare au libellé exact du corpus, qui dit « Actes »,
        « Jean », « Romains ». La proposition était rejetée, et le pasteur recevait ce qui avait
        survécu par hasard : sur *« Par le Saint-Esprit… étant des témoins »*, le modèle avait
        bien proposé **Actes 1:8** — le texte que le pasteur a réellement prêché — et ma
        vérification l'a écarté.

        Le corpus savait pourtant : `books_by_form` porte 356 formes, dont « actes des
        apotres ». Elle sert à la porte d'entrée depuis le début et personne ne l'avait
        branchée ici. On l'interroge donc avec le même normaliseur que le moteur, et la
        référence repart avec le libellé canonique."""
        mots = decouper(propose.reference.book)
        livres = self.index.books_by_form.get(mots)
        if not livres:
            # Le modèle annonce souvent le **genre** avant le nom : « Évangile selon Jean »,
            # « Lettre aux Romains », « Livre de Joël ». On retire le préfixe plutôt que
            # d'ajouter deux cents formes au corpus : le vocabulaire du dépôt reste celui des
            # biblistes, et c'est l'adaptateur qui absorbe la verbosité du modèle.
            for prefixe in _PREFIXES_DE_GENRE:
                if mots[: len(prefixe)] == prefixe and len(mots) > len(prefixe):
                    livres = self.index.books_by_form.get(mots[len(prefixe):])
                    if livres:
                        break
        if not livres:
            return propose  # inconnue : `check_reference` tranchera, avec son motif
        libelle = self.index.label_by_book.get(livres[0])
        if libelle is None or libelle == propose.reference.book:
            return propose
        ref = propose.reference
        return PassageSuggestion(
            Reference(libelle, ref.chapter, ref.verse_start, ref.verse_end),
            propose.rationale,
        )

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

        resolu = _deserialiser(record.resolved_ref) or self._passage_de_l_unite(record)
        etat = StudyState(
            session_id=record.id,
            church_id=record.church_id,
            author_id=record.author_id,
            corpus_snapshot=record.corpus_snapshot or self.index.snapshot,
            entry_mode=EntryMode(record.entry_mode) if record.entry_mode else None,
            raw_input=record.raw_input,
            entry_origin=EntryOrigin(record.entry_origin or EntryOrigin.TYPED.value),
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

        moteur = UrimEngine(deps)
        run = moteur.run(etat)

        # ⚠️ **L'IA est consultée quand le moteur n'a RIEN résolu, et pas avant.**
        #
        # Le garde porte sur le **résultat**, jamais sur une pré-analyse de la saisie : j'avais
        # d'abord regardé si un nom de livre s'y trouvait, et « Miriam chantait le cantique »
        # contenait *Cantique des cantiques* — l'IA n'était jamais appelée. Ce que l'on veut
        # savoir n'est pas « y a-t-il un mot qui ressemble à un livre », c'est « le déterministe
        # a-t-il abouti ».
        #
        # Elle prend donc exactement le milieu difficile : citation de mémoire, paraphrase,
        # personnage nommé autrement que dans la traduction. « Jean 3:16 » se résout sans elle,
        # et ne coûte ni argent ni latence.
        #
        # L'IA **teinte la provenance**, elle n'ouvre pas un second point d'écriture. J'avais
        # d'abord posé ici un `record_attempt` à part : il dupliquait le calcul du condensat,
        # court-circuitait la garde « seulement quand la résolution change » — et il lui
        # manquait `chosen_ref`, ce qui a mis toutes les ouvertures en 500. Un seul évier, en
        # bas, qui écrit `ia` au lieu de `moteur` : ni le moteur ni le pasteur n'a tranché, et
        # confondre les trois effacerait la seule chose que cette colonne existe pour porter.
        provenance = chosen_by
        if persist and record.resolved_ref is None and run.state.resolved is None:
            trouve = await self.resolver.resolve(_lisible(record.raw_input))
            if trouve is not None and IndexedCorpusReader(self.index).check_reference(
                trouve
            ).exists:
                provenance = "ia"
                run = moteur.run(etat.with_(resolved=trouve))

        # ⚠️ **Le risque ne se lève qu'APRÈS le verdict, et seulement s'il n'y a pas de texte.**
        #
        # L'émotion ne classe rien : c'est le croisement sur les 31 170 versets qui a dit
        # « pas une citation », en ne trouvant aucune suite de mots. Elle sert ensuite, dans
        # le chemin conviction, à élargir les textes qui **résistent** et à relever le risque
        # de proof-texting.
        #
        # Si elle entrait dans le classement, elle déciderait de la lecture — et *une lecture
        # émotionnelle juste produit quand même un sermon qui blesse* (S10, S20, S37).
        #
        # Le second passage est **pur et déterministe**, donc sans conséquence ; et sans modèle
        # branché il n'a jamais lieu, puisque `NullConvictionReader` ne lève aucun drapeau.
        #
        # **Les deux lectures de l'intention partent ensemble**, et rejouent une seule fois.
        # Elles répondent à deux questions distinctes — *quels loci cette formulation
        # touche-t-elle ?* et *quelles marques de forme appellent un garde-fou ?* — mais elles
        # portent sur la même saisie et aboutissent au même étage. Deux rejeus successifs
        # auraient fait perdre au second les annotations du premier.
        if run.state.entry_mode is EntryMode.CONVICTION:
            # **Les trois lectures partent ensemble.** Enchaînées, elles coûtaient 44 s pour
            # une seule ouverture : les axes et le risque en parallèle, puis les passages une
            # fois le verdict connu. Or sur ce chemin le verdict est connu d'avance — une
            # intention aboutit toujours à l'écran des axes, et cet écran veut les passages.
            # Attendre de le constater ne rachetait rien qu'un aller-retour.
            lisible = _lisible(record.raw_input)
            loci, drapeaux, proposes = await asyncio.gather(
                self.resolver.axes(lisible),
                self.resolver.lever(lisible),
                self._passages_verifies(lisible),
            )
            if loci or drapeaux or proposes:
                etat = etat.with_(
                    suggested_axes=tuple(loci),
                    risk_flags=tuple(drapeaux),
                    suggested_passages=proposes,
                )
                run = moteur.run(etat)

        # ⚠️ **Le refus devient une proposition — mais seulement quand il y a refus.**
        #
        # Le moteur s'arrêtait sec dans deux cas : « aucun texte du corpus ne porte cette
        # formulation », et « aucune unité relue ne porte cet axe ». Le premier arrive dès
        # qu'on ne cite pas mot pour mot, le second sur presque tout l'Écriture. Dans les deux
        # cas le pasteur repartait les mains vides.
        #
        # Le garde est le **verdict**, pas la saisie : on ne dépense un appel que sur un
        # cul-de-sac avéré, et une préparation qui avance n'en déclenche jamais.
        #
        # ⚠️ **Deux étages seulement, et pas « tout refus ».** Ma première version prenait
        # n'importe quel `REFUSE`, donc aussi « je ne connais pas de livre nommé Zorobabel » —
        # à quoi elle aurait répondu par des passages thématiques. Or là, la bonne réponse est
        # bien celle qu'on donne : le moteur ne connaît pas ce livre, et proposer autre chose
        # noierait l'information au lieu de la servir. Un cul-de-sac de *recherche* appelle une
        # proposition ; un fait sur l'orthographe, non.
        # La conviction a déjà tout demandé plus haut ; il ne reste que le chemin citation.
        if not etat.suggested_passages and _est_une_impasse_de_recherche(run):
            proposes = await self._passages_verifies(_lisible(record.raw_input))
            if proposes:
                run = moteur.run(etat.with_(suggested_passages=proposes))

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
                    chosen_by=provenance or "moteur",
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
                    author_id=record.author_id,
                    provisional_key=_cle_provisoire(record.raw_input),
                    pericope_key=f"pericope:{final.pericope_id}",
                    at=maintenant,
                )

        servis, variantes = self._texte_servi(final)
        # L'unité retenue, cherchée par son identité — c'est elle qui porte la signature, et
        # c'est la seule chose de la curation que le pasteur ne pouvait pas voir jusqu'ici.
        unite = next(
            (p for p in self.index.pericopes if p.id == final.pericope_id),
            None,
        ) if final.pericope_id is not None else None
        return StudyDTO(
            record=record,
            verses=servis,
            variants=variantes,
            bearings=self.index.bearings.get(final.pericope_id, ()),
            caveats=self.index.caveats.get(final.pericope_id, ()),
            context=self.index.notes.get(final.pericope_id, ()),
            couples=self.index.couples.get(final.pericope_id, ()),
            pericope_label=unite.label or None if unite else None,
            pericope_reviewed_by=unite.reviewed_by or None if unite else None,
            resisting_elsewhere=_resistent_ailleurs(
                self.index, final.axis, final.pericope_id
            ),
            outcome=str(dernier.outcome) if dernier else "continue",
            rationale=dernier.rationale if dernier else "",
            trace=tuple((e.stage_code, e.rationale) for e in final.trace),
            options=tuple(
                (o.code, o.label, o.rationale, o.origin)
                for o in (dernier.options if dernier else ())
            ),
            elements=tuple(await self.studies.list_elements(record.id)),
            supports=self._appuis(await self.studies.list_supports(record.id)),
            # Le mode **retenu par le moteur**, pas la colonne : elle reste vide tant que le
            # pasteur n'a rien corrigé, et le pasteur veut voir comment il a été lu.
            entry_mode=final.entry_mode.value if final.entry_mode else None,
            resolved_label=_afficher(final.resolved),
            corpus_drifted=(
                record.corpus_snapshot is not None
                and record.corpus_snapshot != self.index.snapshot
            ),
        )

    def _texte_servi(
        self, etat: StudyState
    ) -> tuple[tuple[VerseServed, ...], tuple[VariantSeen, ...]]:
        """Les versets **et leurs variantes** — la présentation, jamais un étage.

        Les bornes retenues, exactement : ni un verset avant, ni un après. Élargir serait
        cadrer à la place du pasteur, et c'est précisément ce que l'étage 2 lui laisse décider.

        Le texte sort **même hors unité curée** : c'est la curation qui manque là, pas le
        texte. Un `degrade` ne prive pas de la Parole, il prive de ce qu'on en a relu."""
        etendue = etat.bounds or (
            Bounds(start=etat.resolved, end=etat.resolved) if etat.resolved else None
        )
        if etendue is None or etendue.start is None:
            return (), ()

        livre = self.index.book_by_label.get(etendue.start.book)
        if livre is None:
            return (), ()

        debut = (etendue.start.chapter or 1, etendue.start.verse_start or 1)
        fin_ref = etendue.end or etendue.start
        fin = (
            fin_ref.chapter or debut[0],
            fin_ref.verse_end or fin_ref.verse_start or debut[1],
        )

        servis, variantes = [], []
        for v in verses_between(self.index, livre, debut, fin):
            reference = f"{etendue.start.book} {v.chapter}:{v.verse}"
            servis.append(VerseServed(reference=reference, text=v.body))
            for var in self.index.variants.get((livre, v.chapter, v.verse), ()):
                variantes.append(VariantSeen(
                    reference=reference, body=var.body,
                    doctrinal_weight=var.doctrinal_weight, note=var.note,
                    families_with=var.families_with,
                    families_without=var.families_without,
                    source_ref=var.source_ref,
                ))
        return tuple(servis), tuple(variantes)

    def _passage_de_l_unite(self, record: PreparationRecord) -> Reference | None:
        """L'unité curée **est** le passage — sans quoi le chemin conviction boucle.

        ⚠️ Il n'existe pas de colonne `resolved_ref` : la référence n'est persistée que sous
        forme de bornes forcées (`override_*`), et le reste du temps elle est censée se
        **déduire** de la péricope. `_bornes` faisait cette déduction ; `resolved` ne la
        faisait pas.

        Le chemin référence masquait le trou en se réparant tout seul : `resolve_passage`
        reparse « Romains 8:1-11 » à chaque rejeu. Une intention ne se reparse pas — « je veux
        faire un culte sur l'adultère » ne redonnera jamais Hébreux 13. Le pasteur qui venait
        de choisir son unité retombait donc sur l'écran des axes, sa décision enregistrée et
        invisible pour l'étage qui la lisait.

        C'est le **même défaut que le bornage** (voir `_bornes`), au même endroit, et pour la
        même raison : une décision qui vit dans une colonne et se lit dans une autre."""
        if record.pericope_id is None:
            return None
        unite = next(
            (p for p in self.index.pericopes if p.id == record.pericope_id), None
        )
        if unite is None:
            return None
        livre = self.index.label_by_book.get(unite.book_id, "")
        return Reference(livre, unite.start_ch, unite.start_v, unite.end_v)

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

