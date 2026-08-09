"""Étage 1 — **la résolution** : identifier le passage, jamais la version.

Le texte sera resservi depuis les versions du corpus ; la version d'origine est une information
affichée, jamais bloquante. Cet étage ne répond qu'à une question : *de quel passage parle-t-on ?*

Il ne s'applique **pas** à la conviction : elle entre par le chemin inversé (Architecture §7) et
rejoint le pipeline à l'étage 2.

---

## La règle qui gouverne tout : un fait n'interrompt pas

**S19.** Livre inconnu, chapitre hors du livre, verset hors du chapitre — ce sont des **faits**,
pas des ambiguïtés. Le candidat est écarté **avec son motif**, et le moteur continue s'il en reste
un. On ne rend la main que devant un vrai choix.

    « 1 Corinthiens 5 compte 13 versets » apprend quelque chose au pasteur.
    « Référence invalide » le laisse chercher.

Zéro candidat valide → `REFUSE` motivé, et le motif dit ce qui a été écarté et pourquoi.

## Le plus beau mécanisme de la spec, et il faut le protéger

**S2.** Sur une citation, `REFUSE` **seulement si l'ensemble des candidats est vide**. Un candidat
faible **reste un candidat**.

Quand deux versets ont fusionné dans la mémoire du pasteur, aucun ne ressort nettement — tous
obtiennent un score médiocre. La tentation est de répondre « introuvable ». La bonne réponse est :

> *« Votre mémoire a fusionné deux textes. Les voici. »*

**Le mode de défaillance EST le diagnostic.** Confondre l'ensemble vide et l'ensemble médiocre
ferait perdre exactement ce mécanisme.

## L'entrée hybride vérifie au lieu de conclure

**S16.** Le détecteur a routé sur la référence quand les deux signaux concordaient. Ici, la
citation sert à **vérifier** : si elle désigne un autre passage que la référence saisie, on rend la
main. C'est la seule façon d'attraper *« vous citez Rm 8:1 mais votre texte est Rm 8:34 »* — une
erreur de mémoire fréquente que ni la référence seule ni la citation seule ne détectent.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contexts.urim.engine.deps import CitationCandidate, EngineDeps
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.normalizer import tokens as decouper
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.state import EntryMode, Reference, StudyState

#: Écart de score au-delà duquel le premier candidat l'emporte seul. En deçà, les candidats se
#: valent — et deux textes qui se valent sur une citation, c'est une mémoire qui a fusionné.
ECART_NET = 0.25

_MODES_RESOLUS = (EntryMode.REFERENCE, EntryMode.CITATION)


class ResolvePassage:
    """Le deuxième étage. Il écarte des faits, il ne tranche que devant un vrai choix."""

    code = "resolve_passage"

    def applies(self, state: StudyState) -> bool:
        """La conviction ne passe pas par ici — elle rejoint le pipeline à l'étage 2 (§7)."""
        return state.entry_mode in _MODES_RESOLUS and state.resolved is None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.entry_mode not in _MODES_RESOLUS:
            raise StagePrerequisiteError(
                "la résolution ne s'applique qu'à une référence ou une citation"
            )

        mots = decouper(state.raw_input)
        if state.entry_mode is EntryMode.CITATION:
            return self._depuis_une_citation(state, deps, mots)
        return self._depuis_une_reference(state, deps, mots)

    # --- Le chemin de la référence -----------------------------------------------------------

    def _depuis_une_reference(
        self, state: StudyState, deps: EngineDeps, mots: Sequence[str]
    ) -> StageResult:
        retenus: list[Reference] = []
        ecartes: list[str] = []

        for candidat in deps.corpus.parse_reference_candidates(mots):
            verdict = deps.corpus.check_reference(candidat)
            if verdict.exists:
                retenus.append(candidat)
            else:
                ecartes.append(verdict.rationale)

        if not retenus:
            # **Un refus, pas une ambiguïté.** Et le motif porte ce qui a été écarté : sans lui,
            # le pasteur cherche un verset qui n'a jamais existé.
            return StageResult(
                outcome=Outcome.REFUSE,
                rationale=_refus_de_reference(ecartes),
                state=state,
            )

        if len(retenus) > 1:
            # S24 — « 1 Roi ou 2 Roi ». L'hésitation du pasteur est une question mal posée, pas
            # une faute : on lui rend les livres possibles plutôt que d'en choisir un.
            return StageResult(
                outcome=Outcome.AWAIT,
                rationale=_plusieurs_livres(retenus, ecartes),
                state=state,
                options=tuple(_option_de(reference) for reference in retenus),
            )

        (seule,) = retenus
        divergence = _citation_divergente(deps, mots, seule)
        if divergence is not None:
            # S16 — les deux signaux concordaient à l'entrée, ils divergent à la résolution.
            return StageResult(
                outcome=Outcome.AWAIT,
                rationale=(
                    f"Vous citez {_dire(seule)}, mais le texte cité est "
                    f"{_dire(divergence.reference)}."
                ),
                state=state,
                options=(_option_de(seule), _option_de(divergence.reference)),
            )

        return StageResult(
            outcome=Outcome.CONTINUE,
            rationale=_resolution_nette(seule, ecartes),
            state=state.with_(resolved=seule),
        )

    # --- Le chemin de la citation ------------------------------------------------------------

    def _depuis_une_citation(
        self, state: StudyState, deps: EngineDeps, mots: Sequence[str]
    ) -> StageResult:
        candidats = list(deps.corpus.resolve_citation(mots))

        if not candidats:
            # S2 — le seul cas de refus, et le motif fait tout le travail.
            return StageResult(
                outcome=Outcome.REFUSE,
                rationale=(
                    "Aucun texte du corpus ne porte cette formulation. Vérifiez la citation, "
                    "ou entrez une référence."
                ),
                state=state,
            )

        if _un_vainqueur_net(candidats):
            gagnant = candidats[0]
            return StageResult(
                outcome=Outcome.CONTINUE,
                rationale=f"Citation reconnue : {_dire(gagnant.reference)}. {gagnant.rationale}",
                state=state.with_(resolved=gagnant.reference),
            )

        # ⚠️ **Le motif dit ce que le MOTEUR a trouvé, jamais ce que la mémoire du pasteur
        # aurait fait.**
        #
        # Il disait : *« votre mémoire a probablement fusionné plusieurs passages »*. Sur une
        # vraie conflation, c'est juste et utile. Mais « l'amour du prochain » est un thème
        # écrit en trois mots bibliques, et le pasteur s'entendait reprocher un défaut de
        # mémoire qu'il n'avait pas commis — pendant que le moteur, lui, avait mal lu la
        # saisie. Le moteur ne peut pas distinguer les deux cas ; il ne doit donc affirmer
        # que ce qu'il voit : plusieurs textes à égalité.
        #
        # Et il faut une **sortie**. Cinq candidats sans porte de secours enferment dans le
        # chemin citation quelqu'un qui n'a jamais cité : `entry:conviction` rouvre les dix
        # loci, et c'est la seule option de cette liste qui ne prétend pas connaître son
        # intention.
        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=(
                "Plusieurs textes portent cette formulation à égalité — aucun ne se détache. "
                "Lequel visiez-vous ? Si c'est votre sujet et non une citation, dites-le."
            ),
            state=state,
            options=(
                *(
                    _option_de(candidat.reference, candidat.rationale)
                    for candidat in candidats
                ),
                _pas_une_citation(),
            ),
        )


# --- Ce que le pasteur lit --------------------------------------------------------------------


def _dire(reference: Reference) -> str:
    """La référence en clair — au degré de précision qu'elle porte (S7, S23)."""
    if reference.is_whole_book:
        return reference.book
    if reference.is_whole_chapter:
        return f"{reference.book} {reference.chapter}"
    if reference.verse_end and reference.verse_end != reference.verse_start:
        return (
            f"{reference.book} {reference.chapter}:"
            f"{reference.verse_start}-{reference.verse_end}"
        )
    return f"{reference.book} {reference.chapter}:{reference.verse_start}"


def _et_les_ecartes(ecartes: Sequence[str]) -> str:
    """Ce qui a été écarté voyage toujours avec le résultat — jamais en silence."""
    return f" Écarté : {' · '.join(ecartes)}." if ecartes else ""


def _resolution_nette(reference: Reference, ecartes: Sequence[str]) -> str:
    return f"Passage identifié : {_dire(reference)}.{_et_les_ecartes(ecartes)}"


def _plusieurs_livres(retenus: Sequence[Reference], ecartes: Sequence[str]) -> str:
    livres = ", ".join(_dire(reference) for reference in retenus)
    return f"Plusieurs passages portent ce nom : {livres}.{_et_les_ecartes(ecartes)}"


def _refus_de_reference(ecartes: Sequence[str]) -> str:
    if not ecartes:
        return "Aucun passage ne correspond à cette référence."
    return f"Aucun passage ne correspond.{_et_les_ecartes(ecartes)}"


def _option_de(reference: Reference, motif: str = "") -> Option:
    dit = _dire(reference)
    return Option(code=dit, label=dit, rationale=motif or f"Résoudre sur {dit}.")


#: Le code qui **rouvre les dix loci** depuis le chemin citation.
#:
#: Il porte le préfixe `entry:` parce qu'il ne désigne pas un passage : c'est une correction du
#: mode d'entrée, appliquée à l'étage 0. Sans lui, une saisie thématique faite de mots bibliques
#: — « l'amour du prochain », « la crainte de Dieu » — partait en citation et n'en revenait pas.
PAS_UNE_CITATION = "entry:conviction"


def _pas_une_citation() -> Option:
    return Option(
        code=PAS_UNE_CITATION,
        label="Ce n'est pas une citation, c'est mon sujet",
        rationale="Rouvre les dix loci — vous désignez l'angle, le moteur cherche les textes.",
    )


# --- Les deux comparaisons --------------------------------------------------------------------


def _un_vainqueur_net(candidats: Sequence[CitationCandidate]) -> bool:
    """Un seul candidat, ou un premier qui creuse un écart franc sur le second."""
    if len(candidats) == 1:
        return True
    return candidats[0].score - candidats[1].score >= ECART_NET


def _citation_divergente(
    deps: EngineDeps, mots: Sequence[str], reference: Reference
) -> CitationCandidate | None:
    """S16 — la citation vérifie la référence, et ne parle que si elle la contredit.

    Silencieuse quand elle concorde, silencieuse quand elle ne reconnaît rien : une entrée
    hybride est un cadeau, pas une occasion supplémentaire d'interrompre."""
    candidats = list(deps.corpus.resolve_citation(mots))
    if not candidats or not _un_vainqueur_net(candidats):
        return None
    premier = candidats[0]
    return None if premier.reference == reference else premier
