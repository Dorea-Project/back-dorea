"""L'archive du prédicateur — **le geste qui dit « j'ai prêché ceci »**.

`urim_preached` était lue par l'étage du thème et écrite par personne : la phrase *« vous avez
déjà prêché cet axe récemment »* n'a jamais atteint quiconque. Ce service est l'écrivain qui
manquait.

## Trois règles, et elles se voient dans le code plutôt que dans un commentaire

**Rien ne s'archive parce qu'une date est passée.** Il n'y a pas de tâche planifiée ici, pas de
lecture de `service_date` : seul un appel explicite écrit une ligne. Le Pasteur X a préparé
autour de six passages et prêché le Psaume 125 — une archive remplie par le calendrier aurait
enregistré un sermon qui n'a jamais eu lieu.

**L'archive est celle de qui archive.** `author_id` est toujours l'acteur, jamais l'auteur de
la préparation lue. Deux pasteurs d'une même église se relisent (la garde le permet) ; si le
second prêche à partir du travail du premier, c'est **sa** prédication à lui. Rien ne peut donc
salir l'archive de quelqu'un d'autre — et c'est ce qui rend l'écran de couverture digne de foi.

**On ne range que ce que le pasteur a retenu.** `axis_code` vient de sa décision
(`preparation.axis_code`), jamais du dominant calculé : classer son travail d'après une curation
qu'aucun humain n'a relue serait ranger sous une signature `ia-mistral`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID, uuid4

from app.contexts.urim.application.access import ensure_may_prepare, ensure_may_read
from app.contexts.urim.application.ports import (
    ArchiveRepository,
    AxisTally,
    BookCoverage,
    PreachedRecord,
    PreacherAuthorization,
    PreparationRecord,
    StudyRepository,
)
from app.contexts.urim.application.reference_libre import lire
from app.contexts.urim.domain.errors import ArchiveIllisibleError
from app.contexts.urim.engine.state import Reference
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex
from app.contexts.urim.infrastructure.corpus.readers import IndexedCorpusReader

#: Les trois origines que le schéma connaît. `saisie` = « j'ai prêché ceci » depuis une
#: préparation ou à la main ; `dictee` viendra de la capture ; `import` = un sermon d'avant
#: Dorea. La liste est **fermée** — la base porte le même `CHECK`.
ORIGINES = frozenset({"saisie", "dictee", "import"})

#: Combien d'entrées on rend par défaut. L'archive d'un pasteur grandit d'une ligne par
#: semaine : cinq ans tiennent sous ce plafond.
_PAR_DEFAUT = 300


@dataclass(slots=True)
class ArchiveEntryDTO:
    record: PreachedRecord
    #: « Actes 1:1-14 » — la référence lisible, reconstruite depuis les bornes.
    reference: str
    #: Le libellé de l'unité littéraire, si l'archive en porte une.
    pericope_label: str | None = None


@dataclass(slots=True)
class CoverageDTO:
    """Ce que le pasteur lit de son propre parcours — **des faits, aucune consigne**.

    ⚠️ **Rien ici ne propose de sermon.** L'étage du thème le dit déjà à sa façon (« l'archive
    informe, elle n'interdit rien ») et c'est la règle de tout l'écran : un rayon vide se
    montre, il ne se comble pas. Un moteur qui déduirait d'un tableau ce qu'il faut prêcher
    dimanche déciderait de la chaire — *le signal informe l'homme, l'homme commande la
    machine*."""

    books: tuple[tuple[str, BookCoverage], ...] = ()
    axes: tuple[AxisTally, ...] = ()
    #: Nombre de livres du corpus où **rien** n'a été prêché. Un fait, pas un reproche.
    books_untouched: int = 0


@dataclass(slots=True)
class UrimArchiveService:
    archive: ArchiveRepository
    studies: StudyRepository
    access: PreacherAuthorization
    index: CorpusIndex
    clock: object  # callable[[], datetime]
    _lecteur: IndexedCorpusReader | None = field(default=None, init=False, repr=False)

    # -- écrire ----------------------------------------------------------------

    async def record_from_study(
        self,
        *,
        actor_account_id: UUID,
        study_id: UUID,
        preached_on: date | None = None,
        capture_kind: str = "saisie",
    ) -> ArchiveEntryDTO:
        """« J'ai prêché cette préparation. »

        La date par défaut est **aujourd'hui**, pas `service_date` : une préparation datée du
        dimanche prochain n'a pas été prêchée pour autant, et prendre sa date ferait entrer
        dans l'archive une prédication à venir."""
        record = await self.studies.get(study_id)
        if record is None:
            raise ArchiveIllisibleError("Cette préparation n'existe pas.")
        await ensure_may_read(self.access, actor_account_id, record)

        reference = self._passage(record)
        return await self._ecrire(
            PreachedRecord(
                id=uuid4(),
                author_id=actor_account_id,
                # ⚠️ **L'archive est celle de qui archive**, pas celle de l'auteur de la
                # préparation : c'est lui qui est monté en chaire.
                preached_on=preached_on or self._aujourdhui(),
                church_id=record.church_id,
                preparation_id=record.id,
                pericope_id=record.pericope_id,
                axis_code=record.axis_code,
                theme=record.theme,
                capture_kind=_origine(capture_kind),
                **_bornes(reference, self.index),
            )
        )

    async def record_manually(
        self,
        *,
        actor_account_id: UUID,
        reference: str,
        preached_on: date,
        church_id: UUID | None = None,
        axis_code: str | None = None,
        theme: str | None = None,
        capture_kind: str = "import",
    ) -> ArchiveEntryDTO:
        """Un sermon sans préparation — prêché ailleurs, ou avant Dorea.

        La référence est lue **dans la notation du pasteur** (`Hb 2v29`, `Jn14v28`) et
        vérifiée contre le corpus : une référence qui n'existe pas est refusée **avec le motif
        du corpus** — *« Hébreux 2 compte 18 versets »* — jamais avec « saisie invalide »."""
        await ensure_may_prepare(self.access, actor_account_id, church_id)

        lu = lire(reference, self.index)
        if not lu.references:
            raise ArchiveIllisibleError(lu.motif or "Référence illisible.")
        # Le **premier candidat qui existe** — `Jn 14:28` désigne quatre livres, un seul a un
        # chapitre 14. Là où plusieurs tiennent, l'ordre du canon décide (S24).
        verdicts = [(ref, self._corpus().check_reference(ref)) for ref in lu.references]
        retenue = next((ref for ref, v in verdicts if v.exists), None)
        if retenue is None:
            raise ArchiveIllisibleError(verdicts[0][1].rationale)

        return await self._ecrire(
            PreachedRecord(
                id=uuid4(),
                author_id=actor_account_id,
                preached_on=preached_on,
                church_id=church_id,
                pericope_id=self._unite(retenue),
                axis_code=axis_code,
                theme=theme,
                capture_kind=_origine(capture_kind),
                **_bornes(retenue, self.index),
            )
        )

    async def _ecrire(self, record: PreachedRecord) -> ArchiveEntryDTO:
        # ⚠️ **Aucune déduplication.** Prêcher deux fois le même texte, dans deux annexes ou
        # deux dimanches, ce sont **deux faits datés** — les fondre perdrait que le second a
        # eu lieu. C'est la lecture qui compte des passages distincts, pas la table (A-Q1).
        await self.archive.add(record)
        return self._presenter(record)

    # -- lire ------------------------------------------------------------------

    async def list_mine(
        self, *, actor_account_id: UUID, limit: int = _PAR_DEFAUT
    ) -> list[ArchiveEntryDTO]:
        rows = await self.archive.list_for(actor_account_id, limit=limit)
        return [self._presenter(r) for r in rows]

    async def coverage(self, *, actor_account_id: UUID) -> CoverageDTO:
        livres = await self.archive.coverage(actor_account_id)
        axes = await self.archive.distribution(actor_account_id)
        touches = {c.book_id for c in livres}
        return CoverageDTO(
            books=tuple(
                (self.index.label_by_book.get(c.book_id, str(c.book_id)), c)
                for c in livres
            ),
            axes=tuple(sorted(axes, key=lambda a: -a.preachings)),
            books_untouched=sum(
                1 for livre in self.index.label_by_book if livre not in touches
            ),
        )

    # -- outils ----------------------------------------------------------------

    def _aujourdhui(self) -> date:
        maintenant: datetime = self.clock()  # type: ignore[operator]
        return maintenant.date()

    def _corpus(self) -> IndexedCorpusReader:
        if self._lecteur is None:
            self._lecteur = IndexedCorpusReader(self.index)
        return self._lecteur

    def _passage(self, record: PreparationRecord) -> Reference | None:
        """Le texte prêché : la référence retenue, sinon les bornes de l'unité.

        Les deux vivent dans des colonnes différentes (`resolved_ref` n'existe pas en base —
        la référence se déduit de l'unité ou des bornes forcées). L'ordre compte : ce que le
        pasteur a **retenu** prime sur ce que l'unité **couvre**."""
        if record.resolved_ref:
            livre, ch, vs, ve = record.resolved_ref.split("|")
            return Reference(
                livre,
                int(ch) if ch else None,
                int(vs) if vs else None,
                int(ve) if ve else None,
            )
        if record.pericope_id is None:
            return None
        unite = next(
            (p for p in self.index.pericopes if p.id == record.pericope_id), None
        )
        if unite is None:
            return None
        return Reference(
            self.index.label_by_book.get(unite.book_id, ""),
            unite.start_ch,
            unite.start_v,
            unite.end_v if unite.end_ch == unite.start_ch else None,
        )

    def _unite(self, reference: Reference) -> UUID | None:
        """L'unité curée qui couvre ce passage — **la première seulement s'il n'y en a qu'une**.

        Un passage qui en chevauche plusieurs n'est rangé sous aucune : choisir à sa place
        serait décider du rangement doctrinal d'un sermon sur un chevauchement."""
        unites = list(self._corpus().pericopes_for(reference))
        return unites[0].id if len(unites) == 1 else None

    def _presenter(self, record: PreachedRecord) -> ArchiveEntryDTO:
        unite = (
            next((p for p in self.index.pericopes if p.id == record.pericope_id), None)
            if record.pericope_id is not None
            else None
        )
        return ArchiveEntryDTO(
            record=record,
            reference=_afficher(record, self.index),
            pericope_label=unite.label if unite is not None else None,
        )


def _origine(kind: str) -> str:
    if kind not in ORIGINES:
        raise ArchiveIllisibleError(
            f"Origine inconnue : « {kind} ». Attendu : {', '.join(sorted(ORIGINES))}."
        )
    return kind


def _bornes(reference: Reference | None, index: CorpusIndex) -> dict[str, int | None]:
    """Les quatre colonnes de bornes, depuis une référence — **ou quatre `None`**.

    Une préparation qui n'a jamais résolu de passage s'archive quand même : le fait « j'ai
    prêché ce dimanche » est vrai même si le moteur n'a pas su dire sur quoi. Refuser
    l'archive ferait perdre la date pour sauver une colonne."""
    if reference is None:
        return {"book_id": None, "start_ch": None, "start_v": None,
                "end_ch": None, "end_v": None}
    return {
        "book_id": index.book_by_label.get(reference.book),
        "start_ch": reference.chapter,
        "start_v": reference.verse_start,
        "end_ch": reference.chapter,
        "end_v": reference.verse_end or reference.verse_start,
    }


def _afficher(record: PreachedRecord, index: CorpusIndex) -> str:
    if record.book_id is None:
        return ""
    livre = index.label_by_book.get(record.book_id, str(record.book_id))
    if record.start_ch is None:
        return livre
    if record.start_v is None:
        return f"{livre} {record.start_ch}"
    if record.end_v and record.end_v != record.start_v:
        return f"{livre} {record.start_ch}:{record.start_v}-{record.end_v}"
    return f"{livre} {record.start_ch}:{record.start_v}"
