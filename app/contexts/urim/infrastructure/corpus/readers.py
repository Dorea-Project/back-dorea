"""Les cinq lecteurs — **purs, synchrones, sans connexion**.

Ils ne font que consulter un `CorpusIndex` déjà gelé. Aucun ne décide : le corpus répond
à des questions de fait, l'étage tranche. C'est la ligne que ces classes doivent tenir, et
la tentation permanente est de la franchir — rendre « le bon candidat » plutôt que tous
les candidats, taire un refus plutôt que le motiver.

`RequestScope` porte le peu qui n'est **pas** du corpus : les axes qu'un auteur a prêchés
récemment, et le plafond d'usage de son église. Ces deux-là dépendent de qui demande,
donc ils se chargent par requête et ne peuvent pas entrer dans l'index.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.contexts.urim.engine.deps import (
    AxisBearing,
    BearingSite,
    CitationCandidate,
    ContextNote,
    DoctrinalAxis,
    Feasibility,
    PericopeView,
    ReferenceCheck,
    ReferenceSpan,
)
from app.contexts.urim.engine.state import Bounds, Reference
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex

#: Au-delà, un verset n'est plus un candidat mais du bruit. Sert uniquement à borner la
#: liste rendue — jamais à décider qu'un candidat est *le* bon.
_CANDIDATS_MAX = 5

#: Borne haute conventionnelle pour « jusqu'à la fin du chapitre ».
_FIN_DE_CHAPITRE = 10**6

#: Combien de versets présélectionnés subissent la comparaison de séquences.
#:
#: La contiguïté est quadratique en la longueur des deux suites — négligeable sur un verset,
#: prohibitif sur 31 000. Le score lexical sert donc de premier tamis : un verset qui ne
#: partage pas même le vocabulaire ne peut pas en partager l'ordre.
_ANCRAGE_MAX = 25


def _plus_longue_suite(saisie: tuple[str, ...], verset: tuple[str, ...]) -> int:
    """Le plus long segment de mots **consécutifs** commun aux deux suites.

    Programmation dynamique ordinaire, sur deux suites courtes. On garde la longueur et non
    les positions : ce qui se mesure ici est *à quel point la saisie suit le texte*, pas où.
    """
    precedent = [0] * (len(verset) + 1)
    meilleur = 0
    for mot in saisie:
        courant = [0] * (len(verset) + 1)
        for rang, autre in enumerate(verset, start=1):
            if mot == autre:
                courant[rang] = precedent[rang - 1] + 1
                if courant[rang] > meilleur:
                    meilleur = courant[rang]
        precedent = courant
    return meilleur


@dataclass(frozen=True, slots=True)
class RequestScope:
    """Ce qui dépend de **qui demande** — donc jamais du corpus.

    Chargé par requête et gelé de la même façon : les étages restent purs."""

    preached_axes: tuple[str, ...] = ()
    ceiling_reached: bool = False


# ---------------------------------------------------------------------------
# CorpusReader
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndexedCorpusReader:
    index: CorpusIndex

    def snapshot(self) -> str:
        return self.index.snapshot

    # -- reconnaissance d'un nom de livre --------------------------------------

    def _empan(self, tokens: Sequence[str]) -> tuple[tuple[str, ...], int, int] | None:
        """La forme la plus longue reconnue, au plus tôt dans la saisie.

        La longueur prime sur la position : « 2 cor » doit gagner contre « cor », sans quoi
        toute référence à une épître numérotée deviendrait ambiguë à tort."""
        mots = tuple(tokens)
        for debut in range(len(mots)):
            for forme in self.index.forms_by_length:
                fin = debut + len(forme)
                if fin <= len(mots) and mots[debut:fin] == forme:
                    return forme, debut, fin
        return None

    def find_reference_span(self, tokens: Sequence[str]) -> ReferenceSpan | None:
        trouve = self._empan(tokens)
        if trouve is None:
            return None
        forme, debut, fin = trouve
        livres = self.index.books_by_form[forme]
        # Le port ne rend qu'un nom — l'ambiguïté se traite dans
        # `parse_reference_candidates`, dont c'est le travail. Ici, seule la position
        # compte : c'est elle qui dit à l'étage si le nom occupe toute la saisie ou s'il
        # y flotte comme un mot français ordinaire (S35).
        return ReferenceSpan(
            book=self.index.label_by_book[livres[0]], start=debut, stop=fin
        )

    # -- proximité au texte ----------------------------------------------------

    def _ancres(self, tokens: Sequence[str]) -> dict[str, float]:
        """Les mots de la saisie que **le texte** connaît, avec leur poids.

        `idf > 0.0` est le prédicat « ce mot est dans le corpus » : le lissage appliqué au
        semis garantit qu'aucun mot du texte ne tombe à zéro, et que zéro signifie donc
        « mot de la langue, absent de l'Écriture »."""
        return {
            mot: self.index.idf[mot]
            for mot in set(tokens)
            if self.index.idf.get(mot, 0.0) > 0.0
        }

    def _meilleurs_versets(
        self, ancres: dict[str, float]
    ) -> list[tuple[float, object]]:
        total = sum(ancres.values())
        if total <= 0:
            return []

        # **Trouver** avec les mots rares, **noter** avec tous. Un mot présent dans un
        # verset sur deux ne désigne aucun passage, mais il compte encore dans le score :
        # séparer les deux rôles est ce qui permet de traverser 31 000 versets sans les
        # parcourir. Aucune ancre indexée ⇒ aucun candidat, et c'est la bonne réponse —
        # une phrase faite de mots courants ne cite rien.
        candidats: set[int] = set()
        for mot in ancres:
            rangs = self.index.postings.get(mot)
            if rangs:
                candidats.update(rangs)
        if not candidats:
            return []

        cles = ancres.keys()
        scores = []
        for rang in candidats:
            verset = self.index.verses[rang]
            partages = verset.tokens & cles
            if not partages:
                continue
            commun = sum(ancres[m] for m in partages)
            # **Deux mesures, et il faut les deux.**
            #
            #   rappel    — quelle part de la SAISIE se trouve dans ce verset
            #   precision — quelle part du VERSET est dans la saisie
            #
            # Le rappel seul se laisse berner par la longueur : sur « Et Jésus pleura »,
            # Matthieu 26:75 contient les trois mots au milieu de vingt autres et sortait
            # devant Jean 11:35, qui **est** cette phrase. La moyenne harmonique corrige
            # sans arbitrer : un verset ne gagne qu'en ressemblant à la saisie *et* en s'y
            # réduisant.
            rappel = commun / total
            precision = commun / verset.weight if verset.weight > 0 else 0.0
            f = (
                2 * rappel * precision / (rappel + precision)
                if rappel + precision > 0
                else 0.0
            )
            scores.append((f, rappel, verset))
        scores.sort(key=lambda t: (-t[0], t[2].book_id, t[2].chapter, t[2].verse))
        return scores

    def scripture_affinity(self, tokens: Sequence[str]) -> float:
        """⚠️ **La contiguïté** — pas le rappel, pas le classement. Une troisième question.

        *« Cette saisie cite-t-elle l'Écriture ? »* Ni le rappel ni le F1 n'y répondent, et
        c'est mesuré, pas supposé :

        | saisie | rappel | F1 |
        | :-- | --: | --: |
        | « car dieu a tant aime le monde » — vraie citation | 1.000 | **0.396** ✗ |
        | « lamour fraternel nexiiste plus dans leglise » — conviction | **0.640** ✗ | 0.641 |

        Le rappel se laisse berner par le **vocabulaire** : sur 31 000 versets, presque toute
        phrase religieuse trouve un verset qui partage ses mots rares. Le F1 se laisse berner
        par la **longueur** : citer sept mots d'un long verset le fait chuter.

        Ce qui sépare les deux est ce que la spec nommait depuis le début — *« trigrammes et
        ancres rares »* — et que je n'avais pas implémenté : **citer, c'est reprendre des mots
        qui se suivent.** On mesure donc la plus longue suite contiguë commune, rapportée à la
        longueur de la saisie.

        Une suite d'**un seul mot n'est pas une contiguïté** : sans ce plancher, toute saisie
        d'un mot présent dans la Bible passerait pour une citation. En cas de doute, on route
        vers la conviction — jamais l'inverse (S33)."""
        mots = tuple(tokens)
        ancres = self._ancres(mots)
        if not ancres or len(mots) < 2:
            return 0.0

        # Le sac de mots **présélectionne**, la contiguïté **tranche**. Comparer les
        # séquences est quadratique : on ne le fait que sur une courte liste, celle que le
        # score lexical a déjà retenue.
        meilleur = 0
        for _, _, verset in self._meilleurs_versets(ancres)[:_ANCRAGE_MAX]:
            suite = _plus_longue_suite(mots, verset.sequence)
            if suite > meilleur:
                meilleur = suite
        return meilleur / len(mots) if meilleur >= 2 else 0.0

    def resolve_citation(self, tokens: Sequence[str]) -> Sequence[CitationCandidate]:
        ancres = self._ancres(tokens)
        if not ancres:
            return ()
        candidats = []
        for score, _rappel, verset in self._meilleurs_versets(ancres)[:_CANDIDATS_MAX]:
            livre = self.index.label_by_book[verset.book_id]
            candidats.append(CitationCandidate(
                reference=Reference(livre, verset.chapter, verset.verse, verset.verse),
                score=score,
                # Le motif dit **ce qui a été reconnu**, pas « ce verset ressemble ». Un
                # score médiocre partout n'est pas un échec : c'est le diagnostic d'une
                # mémoire qui fusionne deux passages, et le pasteur doit pouvoir le lire.
                rationale=(
                    f"{livre} {verset.chapter}:{verset.verse} partage "
                    f"{len(verset.tokens & ancres.keys())} des mots rares de la saisie."
                ),
            ))
        return tuple(candidats)

    # -- références ------------------------------------------------------------

    def parse_reference_candidates(self, tokens: Sequence[str]) -> Sequence[Reference]:
        trouve = self._empan(tokens)
        if trouve is None:
            return ()
        forme, _, fin = trouve
        livres = self.index.books_by_form[forme]

        chiffres: list[int] = []
        for mot in tokens[fin:]:
            if not mot.isdigit():
                break
            chiffres.append(int(mot))

        # Tous les livres que la forme peut désigner, dans l'ordre du canon. « Roi » en
        # rend deux, « Jean » en rend quatre : le port ne choisit pas, l'étage rendra la
        # main si plusieurs survivent à `check_reference` (S24).
        #
        # ⚠️ L'interprétation des nombres est **propre à chaque livre** — elle ne peut pas
        # se faire une fois pour toutes avant la boucle : « Jean 3 » est un chapitre,
        # « Jude 3 » est un verset.
        return tuple(self._reference(livre, chiffres) for livre in livres)

    def _reference(self, livre: int, chiffres: list[int]) -> Reference:
        """Les nombres d'une saisie, lus **selon le livre qu'ils suivent**.

        ⚠️ **Cinq livres n'ont qu'un chapitre** — Abdias, Philémon, 2 Jean, 3 Jean, Jude —
        et pour eux un nombre seul désigne un **verset**, jamais un chapitre. « Jude 25 »
        est une référence courante et parfaitement valide ; la lire comme un chapitre la
        faisait refuser avec un motif juste sur la forme et faux sur le fond : *« Jude
        compte 1 chapitre »* — le pasteur n'avait pas demandé de chapitre.

        Le cas ambigu, assumé : sur ces livres, « Jude 1 5 » (deux nombres commençant par
        1) se lit **1:5**, la forme de loin la plus fréquente, et non « versets 1 à 5 »."""
        libelle = self.index.label_by_book[livre]
        nombres = list(chiffres)

        if self.index.chapter_count(livre) == 1:
            if len(nombres) > 1 and nombres[0] == 1:
                nombres = nombres[1:]  # le « 1 » était le chapitre : « Jude 1:25 »
            if not nombres:
                return Reference(libelle)
            return Reference(
                libelle, 1, nombres[0], nombres[1] if len(nombres) > 1 else None
            )

        return Reference(
            libelle,
            nombres[0] if nombres else None,
            nombres[1] if len(nombres) > 1 else None,
            nombres[2] if len(nombres) > 2 else None,
        )

    def check_reference(self, reference: Reference) -> ReferenceCheck:
        livre = self.index.book_by_label.get(reference.book)
        if livre is None:
            return ReferenceCheck(False, f"« {reference.book} » n'est pas un livre connu.")

        if reference.chapter is None:
            return ReferenceCheck(True)

        n_chapitres = self.index.chapter_count(livre)
        if n_chapitres is not None and reference.chapter > n_chapitres:
            return ReferenceCheck(
                False,
                f"{reference.book} compte {n_chapitres} chapitre"
                f"{'s' if n_chapitres > 1 else ''} — il n'y a pas de chapitre "
                f"{reference.chapter}.",
            )

        if reference.verse_start is None:
            return ReferenceCheck(True)

        n_versets = self.index.verse_count(livre, reference.chapter)
        if n_versets is None:
            # Le corpus ne tient pas ce chapitre et le canon ne le compte pas : on ne
            # sait pas. **Ne pas savoir n'est pas un motif d'écarter** — le moteur ne
            # rejette que ce qu'il sait faux.
            return ReferenceCheck(True)

        dernier = reference.verse_end or reference.verse_start
        if dernier > n_versets:
            # Sur un livre à chapitre unique, on ne nomme pas le chapitre : le pasteur n'en
            # a pas demandé, et le lui renvoyer donnerait un motif exact et déroutant.
            ou = (
                reference.book
                if n_chapitres == 1
                else f"{reference.book} {reference.chapter}"
            )
            return ReferenceCheck(
                False,
                f"{ou} compte {n_versets} versets — il n'y a pas de verset {dernier}.",
            )
        return ReferenceCheck(True)

    # -- unités littéraires ----------------------------------------------------

    def pericopes_for(self, reference: Reference) -> Sequence[PericopeView]:
        livre = self.index.book_by_label.get(reference.book)
        if livre is None:
            return ()

        if reference.chapter is None:
            demande = ((0, 0), (_FIN_DE_CHAPITRE, _FIN_DE_CHAPITRE))
        elif reference.verse_start is None:
            demande = ((reference.chapter, 0), (reference.chapter, _FIN_DE_CHAPITRE))
        else:
            fin = reference.verse_end or reference.verse_start
            demande = ((reference.chapter, reference.verse_start), (reference.chapter, fin))

        vues = []
        for p in self.index.pericopes:
            if p.book_id != livre:
                continue
            # Rendues dès qu'elles **rencontrent** la demande, même partiellement : c'est
            # la relation entre la demande et l'unité qui fera l'arbitrage, et cette
            # décision appartient à l'étage 2, pas au corpus.
            if (p.start_ch, p.start_v) > demande[1] or (p.end_ch, p.end_v) < demande[0]:
                continue
            vues.append(PericopeView(
                id=p.id,
                bounds=Bounds(
                    start=Reference(reference.book, p.start_ch, p.start_v),
                    end=Reference(reference.book, p.end_ch, p.end_v),
                ),
                label=p.label,
                rationale=p.rationale,
            ))
        return tuple(vues)

    def context_for(self, pericope_id: UUID) -> Sequence[ContextNote]:
        return self.index.notes.get(pericope_id, ())

    def known_words(self, tokens: Sequence[str]) -> int:
        # Le lexique de la **langue** : tout ce qui est dans la table, y compris à idf
        # nul. Un décompte, jamais une proportion — un token pourri sur neuf ne doit rien
        # peser (S34).
        return sum(1 for mot in tokens if mot in self.index.idf)


# ---------------------------------------------------------------------------
# DoctrineReader
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndexedDoctrineReader:
    index: CorpusIndex

    def bearings(self, pericope_id: UUID) -> Sequence[AxisBearing]:
        # Toutes, y compris celles qui résistent. Les ranger est le travail de l'étage 5 ;
        # ici on ne pondère rien.
        return self.index.bearings.get(pericope_id, ())

    def caveats(self, pericope_id: UUID) -> Sequence[str]:
        return self.index.caveats.get(pericope_id, ())

    def axes(self) -> Sequence[DoctrinalAxis]:
        return self.index.axes

    def sites_for_axis(self, axis_code: str) -> Sequence[BearingSite]:
        return self.index.sites_by_axis.get(axis_code, ())

    def dominant_axis(self, pericope_id: UUID) -> str | None:
        # `None` hors péricopes curées : les options sortent alors sans ordre, **jamais en
        # erreur** — c'est la dégradation silencieuse voulue par S18.
        return self.index.dominant.get(pericope_id)


# ---------------------------------------------------------------------------
# HomileticsReader
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndexedHomileticsReader:
    index: CorpusIndex
    scope: RequestScope = field(default_factory=RequestScope)

    def couples_for(self, pericope_id: UUID) -> Sequence[Feasibility]:
        # Les faisables **et** les refusés : une combinaison impossible est signalée,
        # jamais fabriquée, et jamais cachée.
        return self.index.couples.get(pericope_id, ())

    def recently_preached_axes(self, author_id: UUID) -> Sequence[str]:
        # Lu dans **son** archive, préchargé par requête. `preached` est une donnée
        # d'Urim clée sur l'auteur : elle ne franchit aucun mur (E1).
        return self.scope.preached_axes


# ---------------------------------------------------------------------------
# VersionResolver
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndexedVersionResolver:
    index: CorpusIndex
    scope: RequestScope = field(default_factory=RequestScope)

    def ceiling_reached(self) -> bool:
        return self.scope.ceiling_reached

    def is_metered(self, version_id: UUID) -> bool:
        return version_id in self.index.metered_versions

    def public_domain_fallback(self) -> UUID:
        # `licence_coherente` interdit qu'une version du domaine public soit plafonnée :
        # le filet ne peut pas céder, et ce n'est pas une intention de code.
        return self.index.fallback_version_id
