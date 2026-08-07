"""Étage 1-bis — **le chemin inversé** : d'une intention vers un texte (Architecture §7).

Les autres étages partent d'un passage et cherchent ce qu'il porte. Celui-ci part de ce que
le pasteur veut dire et cherche quel texte le porte — d'où *inversé*. Il n'existait pas, et
`bound_pericope` le disait lui-même : *« tant que ce chemin n'existe pas, une conviction
n'atteint simplement pas cet étage »*.

Deux temps, deux `AWAIT`, et la même règle aux deux : **le moteur nomme, le pasteur choisit.**

## 1. Quel axe ?

Les **dix loci**, toujours les dix. C'est l'écran de base, pas un écran de secours (S12) :
le pasteur peut désigner son axe lui-même, et c'est ce qui rend Urim livrable **sans aucun
modèle branché** — terrain tablette, connexion irrégulière (Architecture v2 §10).

Quand un modèle est branché, il **annote et n'écarte jamais**. La conséquence n'est pas
cosmétique : c'est elle qui maintient la propriété de sûreté de S37. Un port qui pourrait
retirer une option pourrait nuire en se trompant ; un port qui ne peut qu'ajouter une phrase
ne le peut pas.

Une conviction est souvent une **plainte, pas un thème** (S10) : « trop de malades malgré
les prières » touche la guérison *et* la prière sans réponse. Les dix restent donc au même
rang — ordonner serait interpréter le for intérieur de celui qui écrit.

## 2. Quel texte ?

Les unités qui **disent quelque chose** de l'axe retenu — portantes **et résistantes, au
même rang** (§7, S20). C'est ici que vit toute la protection du mode conviction, et elle a
une propriété rare : *elle ne dépend pas de la justesse de l'axe choisi*. Un pasteur qui
retient « guérison » verra quand même les textes qui compliquent la guérison ; un pasteur
qui accuse son assemblée verra quand même ceux qui se retournent vers le prédicateur.

## Le risque, et pourquoi il ne se lève qu'ici

`risk_flags` ne **choisit aucun texte** — il élargit les résistants et relève le
`proof_text_risk` que l'étage 6 affichera. Et il ne se lève que sur ce chemin : une saisie
qui nomme sa référence n'a pas de charge à peser, le pasteur a déjà dit sur quoi il prêche.

⚠️ **Le motif nomme l'effet, jamais l'état de celui qui écrit.** « Formulation à forte
charge — davantage de textes qui résistent sont affichés » se vérifie et se conteste ;
« vous êtes dans la plainte » est un diagnostic, et S10 l'interdit.
"""

from __future__ import annotations

from app.contexts.urim.engine.deps import BearingSite, EngineDeps
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.state import EntryMode, StudyState

#: Ce que chaque force dit du texte, en une clause lisible à l'écran. `absent` n'y figure
#: pas : une unité qui ne dit rien d'un axe n'est pas un candidat, et le port l'a déjà
#: écartée.
_CE_QUE_LE_TEXTE_FAIT = {
    "dominant": "ce texte en fait son sujet",
    "porte": "ce texte le soutient",
    "resiste": "⚠ ce texte le complique ou le contredit",
}


class WeighConviction:
    """Le chemin inversé. Il ne trouve pas un texte : il en propose, et il en explique."""

    code = "weigh_conviction"

    def applies(self, state: StudyState) -> bool:
        """Seulement la conviction, et seulement tant qu'aucun texte n'est retenu.

        Dès que `resolved` est posé, l'étage s'efface et le pipeline reprend son cours
        ordinaire au bornage — sans qu'aucun étage aval n'ait à savoir par où c'est entré."""
        return state.entry_mode is EntryMode.CONVICTION and state.resolved is None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.axis is None:
            return self._proposer_les_axes(state, deps)
        return self._proposer_les_textes(state, deps)

    # -- 1. l'axe ---------------------------------------------------------------

    def _proposer_les_axes(self, state: StudyState, deps: EngineDeps) -> StageResult:
        axes = deps.doctrine.axes()
        if not axes:
            return StageResult(
                outcome=Outcome.REFUSE,
                rationale=(
                    "Aucun axe doctrinal n'est curé dans ce corpus — il n'y a rien à quoi "
                    "rattacher une intention."
                ),
                state=state,
            )

        # Le modèle **annote**, il n'écarte pas : les dix sortent toujours.
        suggeres = frozenset(deps.conviction.candidate_axes(state.raw_input))
        options = tuple(
            Option(
                code=f"axe:{axe.code}",
                label=axe.label,
                rationale=(
                    "Votre formulation touche cet axe."
                    if axe.code in suggeres
                    else "Disponible — c'est vous qui savez ce que vous prêchez."
                ),
            )
            for axe in axes
        )
        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=_motif_des_axes(state, suggeres),
            state=state,
            options=options,
        )

    # -- 2. le texte ------------------------------------------------------------

    def _proposer_les_textes(self, state: StudyState, deps: EngineDeps) -> StageResult:
        sites = deps.doctrine.sites_for_axis(state.axis or "")
        if not sites:
            # Le plafond dur du corpus curé, **dit franchement** (S2, S3). Ce n'est pas une
            # panne : c'est une limite, et la taire laisserait croire que le texte n'existe
            # pas alors que c'est la relecture qui manque.
            return StageResult(
                outcome=Outcome.REFUSE,
                rationale=(
                    "Aucune unité littéraire relue ne porte cet axe dans ce corpus. Ce n'est "
                    "pas que l'Écriture n'en dise rien — c'est que la curation ne couvre pas "
                    "encore ce terrain. Entrez une référence si vous savez déjà où aller."
                ),
                state=state,
            )

        options = tuple(
            Option(
                code=f"texte:{site.pericope_id}",
                label=f"{site.label} — {_CE_QUE_LE_TEXTE_FAIT.get(site.strength, site.strength)}",
                rationale=site.rationale,
            )
            for site in sites
        )
        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=_motif_des_textes(sites, state),
            state=state,
            options=options,
        )


def _motif_des_axes(state: StudyState, suggeres: frozenset[str]) -> str:
    debut = (
        "Une intention peut porter plusieurs doctrines, et c'est souvent le cas. "
        "Laquelle prêchez-vous ?"
    )
    if suggeres:
        debut += (
            " Les axes que votre formulation touche sont signalés — les autres restent "
            "ouverts."
        )
    return debut + _clause_de_risque(state)


def _motif_des_textes(sites: tuple[BearingSite, ...], state: StudyState) -> str:
    resistants = sum(1 for s in sites if s.strength == "resiste")
    motif = f"{len(sites)} unité(s) relue(s) disent quelque chose de cet axe."
    if resistants:
        # Annoncé, jamais glissé en bas de liste : c'est la partie qu'un pasteur pressé
        # sauterait, et c'est celle qui le protège.
        motif += (
            f" Dont {resistants} qui le **compliquent ou le contredisent** — elles sont "
            "affichées au même rang, exprès."
        )
    return motif + _clause_de_risque(state)


def _clause_de_risque(state: StudyState) -> str:
    """Nomme **l'effet** du drapeau, jamais l'état de celui qui écrit (S10, S37)."""
    if not state.risk_flags:
        return ""
    return (
        " Formulation à forte charge : davantage de textes qui résistent sont affichés, "
        "et le risque de proof-texting sera relevé sur la mise en forme."
    )
