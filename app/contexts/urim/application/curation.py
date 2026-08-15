"""La curation — **le seul endroit du produit où un humain signe**.

Tout ce que le moteur affiche au pasteur comme *relu* vient d'ici : les bornes d'une unité
littéraire et leur motif, les pesées sur les dix loci, les mises en garde, le contexte, la
faisabilité homilétique. `reviewed_by NOT NULL` est en base sur ces six tables, et il n'y est
pas pour la traçabilité : il y est pour empêcher qu'une machine remplisse ce qu'un homme
doit avoir pesé.

## Pourquoi c'est une surface **Plateforme** et non de tenant

Aucune table `urim_corpus_*` ne porte de `church_id` : le corpus est **global**. Une
curation change ce que *toutes* les églises lisent. Un pasteur ne peut donc pas curer — pas
par défiance, mais parce que le geste n'a pas la bonne portée.

## Trois règles que la surface tient, et que la base ne peut pas tenir seule

1. **Les dix loci se saisissent d'un coup, `absent` compris** (S38). Une unité qui ne porte
   aucune pesée sur un axe n'est pas une unité où *« on a regardé et il n'y a rien »* — c'est
   une unité où **personne n'a regardé**. Les deux ne se distinguent que si le relecteur est
   obligé de passer sur les dix.
2. **On ne signe pas d'un nom de semis.** `semis-demo` est refusé explicitement : c'est la
   marque d'un jeu de démonstration, et la laisser passer rendrait le garde décoratif.
3. **Les bornes doivent exister dans le texte.** Curer Jean 3:99 produirait une unité que
   personne ne peut lire.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.contexts.urim.domain.errors import CurationInvalideError
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex

#: Signatures interdites — celles qui ne désignent personne.
_SIGNATURES_REFUSEES = frozenset({"semis-demo", "demo", "test", "machine", "ia", "auto"})

#: ⚠️ **La seule signature non humaine admise**, et c'en est une décision, pas une faille.
#:
#: Le garde ci-dessus refuse « ia » — mais `ia-mistral` passait par simple différence de chaîne,
#: ce qui est exactement la façon dont une règle se contourne sans que personne ne l'ait voulu.
#: Elle est donc nommée ici.
#:
#: Ce qu'elle autorise est étroit : le **découpage littéraire**, produit en masse par le modèle
#: pour que le moteur cesse de dégrader sur 99,77 % de l'Écriture. Une péricope dit où un récit
#: se referme ; elle ne dit pas ce que le texte enseigne. Les pesées doctrinales, les mises en
#: garde et la faisabilité restent à quelqu'un qui répond de ce qu'il affirme.
#:
#: Et elle ne vaut que parce qu'elle **se voit** : `StudyView.curation_reviewed_by` la porte
#: jusqu'à l'écran du pasteur, et `PATCH /pericopes/{id}` permet à un relecteur de la remplacer
#: par la sienne. Sans ces deux-là, ce serait une signature qui ment.
SIGNATAIRE_IA = "ia-mistral"

#: Longueur minimale d'un motif. Un `rationale` vide passerait le `NOT NULL` de la base et
#: ne dirait rien au pasteur — or c'est *la* phrase qu'il lit pour comprendre ces bornes-là.
_MOTIF_MINIMUM = 20

#: Les verdicts qu'un relecteur peut poser sur un écart signalé.
#:
#: ⚠️ **`accepte` n'est pas « c'est bien », c'est « l'écart est réel et la curation est juste
#: quand même ».** Apocalypse 5 porte réellement huit loci ; le détecteur a raison de la
#: trouver inhabituelle et tort d'en faire un défaut. Sans ce verdict, elle reviendrait en tête
#: de file à chaque passage, éternellement — et une file qui ne décroît pas n'est pas une file,
#: c'est un reproche permanent.
VERDICTS = frozenset({"accepte", "corrige", "a_reprendre"})

#: Le signalement qui porte sur l'unité entière plutôt que sur un détecteur — c'est par lui
#: qu'on saura un jour quelle part du corpus un humain a vraiment relue.
PORTEE_ENSEMBLE = "ensemble"


#: Les noms des deux couches qui entrent dans une empreinte.
#:
#: ⚠️ **Des constantes, et pas des littéraux, parce qu'une empreinte ne pardonne pas.** Trois
#: endroits calculent celle d'une unité — le détecteur d'écarts, l'outil en ligne de commande et
#: la surface du relecteur. Un « mise en garde » écrit ailleurs « caveat » produirait une
#: empreinte différente sur la même curation : tous les verdicts posés paraîtraient périmés, et
#: la file remonterait sans que rien n'ait changé dans le corpus.
COUCHE_PESEE = "pesée"
COUCHE_MISE_EN_GARDE = "mise en garde"


def empreinte_de_curation(lignes: Iterable[tuple[str, str, str]]) -> str:
    """Ce sur quoi le verdict a porté — `(couche, axe, corps)`, trié puis condensé.

    ⚠️ **Un verdict doit se périmer quand ce qu'il jugeait a changé.** Un relecteur qui accepte
    les huit loci d'Apocalypse 5 juge *ces* pesées-là ; si une régénération les réécrit, son
    accord ne vaut plus et l'unité doit revenir en file. Sans empreinte, un verdict posé une
    fois protégerait indéfiniment une curation qu'il n'a jamais vue.

    C'est le troisième endroit du produit où ce patron sert — `corpus_snapshot` pour le corpus,
    `input_hash` pour les suggestions du modèle, celui-ci pour la relecture. Chaque fois pour la
    même raison : *une décision ne vaut que sur l'objet qu'elle a regardé.*"""
    empilees = "\n".join(sorted(f"{couche}|{axe}|{corps}" for couche, axe, corps in lignes))
    return hashlib.sha256(empilees.encode()).hexdigest()[:32]


def verdict_couvre(
    verdicts: Mapping[str, str], empreinte_courante: str, detecteur: str
) -> bool:
    """Ce signalement-là est-il **déjà tranché**, sur cette curation-là ?

    Deux portées couvrent : celle du détecteur (`D4`) et celle de l'unité entière (`ensemble`) —
    un relecteur qui a relu tout le passage n'a pas à revenir sur chaque signalement.

    ⚠️ **Ici parce que deux lecteurs en dépendent** : le détecteur d'écarts, qui décide ce qu'il
    remet en file, et la surface du relecteur, qui décide ce qu'elle affiche. Recopiée, la règle
    aurait divergé le jour où l'une des deux est corrigée — et les deux moitiés du produit
    n'auraient plus dit la même chose sur *ce qui reste à faire*."""
    return (
        verdicts.get(detecteur) == empreinte_courante
        or verdicts.get(PORTEE_ENSEMBLE) == empreinte_courante
    )


#: ⚠️ **Les deux seules formes qu'une machine n'a jamais le droit d'écrire.**
#:
#: Elles sont ici, et non dans un script, parce qu'elles doivent valoir aux deux endroits qui
#: écrivent du corpus : les lots de curation et la route Plateforme. Recopiées, elles auraient
#: divergé — et le détecteur d'écarts les importe d'ici pour la même raison.
#:
#: **Ce sont des règles de la MACHINE, pas du corpus.** Un relecteur humain qui cite l'apparat
#: de NA28 sur Romains 8:1 fait exactement son travail : il peut consulter l'apparat et en
#: répondre. Le modèle, non — il inventera la variante, et personne ne le verra. Le détecteur a
#: mis cette mise en garde-là en tête de sa file le premier jour, faute de ce distinguo.
_FORMES_REFUSEES_A_LA_MACHINE = (
    (
        "manuscrit",
        r"manuscrit|apparat|codex|texte re[çc]u|le[çc]on variante",
        "Les variantes textuelles ont leur table, alimentée par un apparat critique. Un "
        "modèle qui en parle les invente.",
    ),
    (
        "autorité",
        r"selon (saint |la tradition|les p[èe]res)|commentateur|concile de |NA28|Nestle|"
        r"Augsbourg|La Rochelle|Westminster|Helv[ée]tique|Belgica|cat[ée]chisme de ",
        "Le seul appui d'une ligne générée est le passage lui-même — une autorité extérieure "
        "ne peut pas être vérifiée par celui qui la lit.",
    ),
)


def verifier_forme_machine(corps: str, signataire: str) -> None:
    """Ce qu'une ligne **générée** n'a pas le droit de dire.

    🔴 Ces deux règles seules, et pas la troisième. Le détecteur signalait aussi la *négation de
    doctrine* — « ne constitue pas une doctrine générale du salut » — et j'allais la déplacer
    ici avec les autres. La lecture des neuf lignes prises l'a démenti : **huit étaient justes**,
    et parmi les meilleures du corpus. Avertir que la rétribution de Bildad n'est pas une
    doctrine, ou que « ne pardonne pas leur iniquité » est une supplication et non un énoncé sur
    le pardon divin, est précisément ce que ce produit doit dire à un prédicateur.

    La neuvième était fausse — Jean 14:2-3 restreint aux disciples du premier siècle — et aucune
    expression régulière ne l'aurait distinguée des huit autres : la différence est théologique.
    Elle reste donc un signal de relecture. **Un refus l'aurait payée de huit bonnes lignes.**
    """
    if signataire != SIGNATAIRE_IA:
        return
    for nom, motif, pourquoi in _FORMES_REFUSEES_A_LA_MACHINE:
        if re.search(motif, corps, re.I):
            raise CurationInvalideError(f"Forme refusée à une ligne générée ({nom}). {pourquoi}")


def verifier_verdict(verdict: str, portee: str, relu_par: str) -> None:
    """Un verdict est **humain, ou il n'est pas**.

    Le garde des signatures vaut ici comme ailleurs, et `SIGNATAIRE_IA` s'y ajoute : toute la
    valeur de cette table tient à ce qu'une machine n'y écrive jamais. Une file d'attente que
    le modèle pourrait vider lui-même ne mesurerait plus rien."""
    if verdict not in VERDICTS:
        raise CurationInvalideError(f"« {verdict} » n'est pas un verdict.")
    if not portee.strip():
        raise CurationInvalideError("Un verdict porte sur un détecteur, ou sur l'ensemble.")
    nom = relu_par.strip()
    if not nom or nom.lower() in _SIGNATURES_REFUSEES or nom == SIGNATAIRE_IA:
        raise CurationInvalideError(
            "Un verdict se signe d'un nom qui désigne quelqu'un — jamais d'une machine."
        )


@dataclass(slots=True)
class PericopeDraft:
    book: str
    start_ch: int
    start_v: int
    end_ch: int
    end_v: int
    rationale: str
    source_ref: str
    reviewed_by: str
    label: str | None = None


@dataclass(slots=True)
class BearingDraft:
    axis_code: str
    strength: str
    rationale: str
    source_ref: str


@dataclass(slots=True)
class CaveatDraft:
    axis_code: str
    caveat_kind: str
    body: str
    source_ref: str
    tradition_scope: list[str] | None = None


@dataclass(slots=True)
class ContextDraft:
    context_kind: str
    body: str
    ordinal: int
    source_ref: str


@dataclass(slots=True)
class FeasibilityDraft:
    plan_source: str
    subject_matter: str
    feasible: bool
    proof_text_risk: str
    refusal_reason: str | None = None


@dataclass(slots=True)
class PericopeSummary:
    id: UUID
    book: str
    start_ch: int
    start_v: int
    end_ch: int
    end_v: int
    label: str | None
    reviewed_by: str
    n_bearings: int
    n_caveats: int
    n_context: int
    n_feasibility: int

    @property
    def complete(self) -> bool:
        """Les dix loci pesés — le seul sens défendable de « relue » (S38)."""
        return self.n_bearings >= 10


@dataclass(slots=True)
class CoverageReport:
    """L'état de la curation, **sans complaisance**.

    Le chiffre qui compte est `verses_covered / verses_total` : c'est la part de l'Écriture
    sur laquelle Urim a réellement quelque chose de relu à dire. Tout le reste du moteur peut
    être parfait, il dégradera partout ailleurs."""

    verses_total: int
    verses_covered: int
    pericopes: int
    pericopes_completes: int
    par_locus: dict[str, int] = field(default_factory=dict)
    par_livre: dict[str, int] = field(default_factory=dict)

    @property
    def part_couverte(self) -> float:
        return self.verses_covered / self.verses_total if self.verses_total else 0.0


class CurationRepository(Protocol):
    async def add_pericope(self, draft: PericopeDraft, book_id: int) -> UUID: ...

    async def get_book_id(self, pericope_id: UUID) -> int | None: ...

    async def replace_bearings(
        self, pericope_id: UUID, drafts: list[BearingDraft], reviewed_by: str
    ) -> None: ...

    async def add_caveat(
        self, pericope_id: UUID, draft: CaveatDraft, reviewed_by: str
    ) -> UUID: ...

    async def add_context(
        self, pericope_id: UUID, draft: ContextDraft, reviewed_by: str
    ) -> UUID: ...

    async def replace_feasibility(
        self, pericope_id: UUID, drafts: list[FeasibilityDraft], reviewed_by: str
    ) -> None: ...

    async def resign_pericope(
        self, pericope_id: UUID, *, reviewed_by: str,
        label: str | None, rationale: str | None,
    ) -> bool: ...

    async def delete_pericope(self, pericope_id: UUID) -> bool: ...

    async def list_pericopes(self, book_id: int | None) -> list[PericopeSummary]: ...

    async def coverage(self) -> CoverageReport: ...


@dataclass(slots=True)
class UrimCuration:
    repo: CurationRepository
    index: CorpusIndex
    #: Appelé après **toute** écriture. L'index est gelé par processus : sans cette purge, une
    #: curation tout juste signée resterait invisible jusqu'au prochain redémarrage. Elle
    #: change aussi `snapshot`, donc les préparations ouvertes signalent `corpus_drifted` —
    #: c'est voulu : leur trace n'est plus celle du jour.
    invalidate: object

    # -- l'unité littéraire -----------------------------------------------------

    async def create_pericope(self, draft: PericopeDraft) -> UUID:
        self._verifier_signature(draft.reviewed_by)
        if len(draft.rationale.strip()) < _MOTIF_MINIMUM:
            raise CurationInvalideError(
                "Le motif des bornes doit dire pourquoi celles-ci — c'est la phrase que le "
                "pasteur lira pour vous suivre, ou vous contredire."
            )
        if not draft.source_ref.strip():
            raise CurationInvalideError("Une source est requise : d'où vient ce découpage ?")

        livre = self.index.book_by_label.get(draft.book)
        if livre is None:
            raise CurationInvalideError(f"« {draft.book} » n'est pas un livre connu.")
        if (draft.start_ch, draft.start_v) > (draft.end_ch, draft.end_v):
            raise CurationInvalideError("Les bornes sont inversées.")
        self._verifier_borne(livre, draft.book, draft.start_ch, draft.start_v)
        self._verifier_borne(livre, draft.book, draft.end_ch, draft.end_v)

        nouvelle = await self.repo.add_pericope(draft, livre)
        self.invalidate()
        return nouvelle

    def _verifier_borne(self, livre: int, libelle: str, chapitre: int, verset: int) -> None:
        dernier = self.index.verse_count(livre, chapitre)
        if dernier is None:
            raise CurationInvalideError(f"{libelle} n'a pas de chapitre {chapitre}.")
        if verset > dernier:
            raise CurationInvalideError(
                f"{libelle} {chapitre} compte {dernier} versets — pas de verset {verset}."
            )

    # -- les dix loci -----------------------------------------------------------

    async def set_bearings(
        self, pericope_id: UUID, drafts: list[BearingDraft], reviewed_by: str
    ) -> None:
        """⚠️ **Les dix, d'un coup.** C'est S38 rendu structurel plutôt que recommandé.

        Une unité sans ligne sur un axe et une unité marquée `absent` sur cet axe ne disent
        pas la même chose : la première signifie *« personne n'a regardé »*, la seconde
        *« quelqu'un a regardé et le texte n'en dit rien »*. Le moteur les distingue déjà ;
        si la surface acceptait une saisie partielle, une curation à moitié faite
        ressemblerait à une curation finie."""
        self._verifier_signature(reviewed_by)
        await self._exiger_pericope(pericope_id)

        attendus = {axe.code for axe in self.index.axes}
        fournis = {d.axis_code for d in drafts}
        if len(drafts) != len(fournis):
            raise CurationInvalideError("Un même axe est pesé deux fois.")
        if fournis != attendus:
            manquants = sorted(attendus - fournis)
            intrus = sorted(fournis - attendus)
            raise CurationInvalideError(
                "Les dix loci se pèsent ensemble, `absent` compris — "
                f"manquants : {manquants or '-'} ; inconnus : {intrus or '-'}."
            )
        for d in drafts:
            if not d.rationale.strip():
                raise CurationInvalideError(
                    f"L'axe « {d.axis_code} » est pesé sans motif. Dire *pourquoi* un texte "
                    "ne porte pas un axe est aussi utile que de dire qu'il le porte."
                )

        await self.repo.replace_bearings(pericope_id, drafts, reviewed_by)
        self.invalidate()

    # -- le reste ---------------------------------------------------------------

    async def add_caveat(
        self, pericope_id: UUID, draft: CaveatDraft, reviewed_by: str
    ) -> UUID:
        self._verifier_signature(reviewed_by)
        verifier_forme_machine(draft.body, reviewed_by)
        await self._exiger_pericope(pericope_id)
        if draft.caveat_kind == "confessionnel" and not draft.tradition_scope:
            # La base l'interdit aussi (`confessionnel_borne`) — ici le message dit quoi faire.
            raise CurationInvalideError(
                "Un caveat confessionnel nomme les traditions qui divergent. La formulation "
                "reste « ici les traditions divergent », jamais « votre tradition dit X »."
            )
        nouveau = await self.repo.add_caveat(pericope_id, draft, reviewed_by)
        self.invalidate()
        return nouveau

    async def add_context(
        self, pericope_id: UUID, draft: ContextDraft, reviewed_by: str
    ) -> UUID:
        self._verifier_signature(reviewed_by)
        # Le lot des notes de contexte vient ensuite, et posera la même question : une realia
        # « selon les Pères » générée par le modèle est une source qui n'en est pas une.
        verifier_forme_machine(draft.body, reviewed_by)
        await self._exiger_pericope(pericope_id)
        if not draft.source_ref.strip():
            raise CurationInvalideError(
                "Le contexte est **sourcé, ou absent** — il n'y a pas de troisième possibilité."
            )
        nouveau = await self.repo.add_context(pericope_id, draft, reviewed_by)
        self.invalidate()
        return nouveau

    async def set_feasibility(
        self, pericope_id: UUID, drafts: list[FeasibilityDraft], reviewed_by: str
    ) -> None:
        self._verifier_signature(reviewed_by)
        await self._exiger_pericope(pericope_id)
        for d in drafts:
            if not d.feasible and not (d.refusal_reason or "").strip():
                raise CurationInvalideError(
                    f"« {d.plan_source} x {d.subject_matter} » est refusé sans motif. Un refus "
                    "muet est un refus qu'on ne peut pas contester."
                )
        await self.repo.replace_feasibility(pericope_id, drafts, reviewed_by)
        self.invalidate()

    async def resign_pericope(
        self, pericope_id: UUID, *, reviewed_by: str,
        label: str | None = None, rationale: str | None = None,
    ) -> bool:
        """**Un relecteur reprend à son compte une unité découpée par le modèle.**

        C'est ce qui rend `ia-mistral` acceptable : la signature du modèle est un point de
        départ, pas un état définitif. Sans cette route, le découpage généré aurait été une
        porte à sens unique — un relecteur n'aurait pu qu'effacer et retaper, en perdant au
        passage les pesées déjà accrochées à l'unité.

        L'intitulé et le motif se corrigent au passage, parce qu'on ne signe pas une phrase
        qu'on n'a pas le droit d'amender : re-signer sans pouvoir rectifier reviendrait à
        approuver en bloc, et c'est le contraire d'une relecture."""
        self._verifier_signature(reviewed_by)
        if rationale is not None and len(rationale.strip()) < _MOTIF_MINIMUM:
            raise CurationInvalideError(
                "Le motif doit dire pourquoi ces bornes-là — c'est la phrase que le pasteur lit."
            )
        repris = await self.repo.resign_pericope(
            pericope_id,
            reviewed_by=reviewed_by.strip(),
            label=label,
            rationale=rationale.strip() if rationale else None,
        )
        if repris:
            self.invalidate()
        return repris

    async def delete_pericope(self, pericope_id: UUID) -> bool:
        """Retirer une curation fautive. Sans cela, une erreur de relecture serait définitive."""
        retire = await self.repo.delete_pericope(pericope_id)
        if retire:
            self.invalidate()
        return retire

    # -- lecture ----------------------------------------------------------------

    async def list_pericopes(self, book: str | None = None) -> list[PericopeSummary]:
        livre = self.index.book_by_label.get(book) if book else None
        if book and livre is None:
            raise CurationInvalideError(f"« {book} » n'est pas un livre connu.")
        return await self.repo.list_pericopes(livre)

    async def coverage(self) -> CoverageReport:
        return await self.repo.coverage()

    # -- gardes -----------------------------------------------------------------

    def _verifier_signature(self, reviewed_by: str) -> None:
        nom = reviewed_by.strip()
        if nom.lower() == SIGNATAIRE_IA:
            return
        if len(nom) < 3 or nom.lower() in _SIGNATURES_REFUSEES:
            raise CurationInvalideError(
                "Signez d'un nom qui désigne quelqu'un. Ce champ dit au pasteur qui a pesé "
                "ce texte ; « semis-demo » ou « auto » ne désignent personne."
            )

    async def _exiger_pericope(self, pericope_id: UUID) -> None:
        if await self.repo.get_book_id(pericope_id) is None:
            raise CurationInvalideError("Cette unité littéraire n'existe pas.")
