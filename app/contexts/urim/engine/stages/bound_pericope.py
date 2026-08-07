"""Étage 2 — **le bornage** : l'unité littéraire, et pourquoi elle déborde parfois la demande.

C'est l'étage le plus finement spécifié du moteur, parce que c'est celui où le moteur peut le plus
facilement devenir pénible. Toute la règle tient dans **une seule question**, posée à chaque fois :

> **Y a-t-il quelque chose à arbitrer ?**

Trois relations possibles entre ce que le pasteur a demandé et ce que le corpus a curé, et une
réponse pour chacune (D-E, S8) :

| Relation | Exemple | Issue |
| :-- | :-- | :-- |
| **coïncide** | `Rom 1:16-17` = la péricope | `CONTINUE` — rien à arbitrer |
| **coupe** ⊂ | `Rom 1:16` dans `Rom 1.16-17` | `AWAIT` **2 options** |
| **englobe** ⊃ | `Galates 5` = trois unités | `AWAIT` **N+1 options** |

Le premier cas est le plus important à tenir : *on ne fatigue pas quelqu'un qui a visé juste.*

Le cas d'école de la coupe mérite d'être relu : `Rom 1:16` seul coupe l'unité, parce que le
*γάρ* du verset 17 **fonde** le verset 16. Prêcher « je n'ai point honte de l'Évangile » sans « car
en lui est révélée la justice de Dieu », c'est prêcher la moitié d'une phrase.

---

## Ce que cet étage ne fait pas

**Il ne refuse jamais.** Un passage hors du corpus curé n'est pas une faute : c'est un `DEGRADE`,
et la préparation continue. *Aucun mur un vendredi soir.*

**Il ne décide pas à la place du pasteur.** L'option « ma demande telle quelle » existe toujours,
et elle **dit ce qu'elle coûte** — parce qu'accorder une liberté sans nommer la zone hors
garde-fous qu'elle ouvre, c'est la lui faire découvrir trop tard (S22).

**Il n'interprète pas les axes.** Il en lit un — l'axe dominant — pour **ordonner** des options
quand le pasteur a refusé quelque chose (S18). Interpréter reste le travail de l'étage 5.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contexts.urim.engine.deps import EngineDeps, PericopeView
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.state import Bounds, Reference, StudyState

#: Le code de l'option « gardez mes bornes » — la seule qui pose `bounds_overridden`.
TEL_QUEL = "tel_quel"

#: Le code de l'option « tout, en un sermon expositif » quand la demande couvre plusieurs unités.
EN_UN_SEUL = "en_un_seul"

#: Ce que le pasteur perd en forçant ses bornes, dit **au moment où il choisit** et pas trois
#: étages plus loin (S22) : `homiletic_feasibility` est clée sur la péricope, donc hors d'elle il
#: n'y a ni faisabilité relue, ni alerte de proof-texting.
_COUT_DU_TEL_QUEL = (
    "Vos bornes exactes — mais hors unité curée : plus d'alerte de risque de proof-texting "
    "sur ce bornage."
)

_INFINI = 10**9


class BoundPericope:
    """Le troisième étage. Il propose une unité, il n'en impose aucune."""

    code = "bound_pericope"

    def applies(self, state: StudyState) -> bool:
        """Il faut un passage résolu, et pas encore de bornes.

        La conviction rejoint le pipeline **ici** (§7) — mais avec un texte déjà sélectionné par
        le chemin inversé, donc avec `resolved` posé. Tant que ce chemin n'existe pas, une
        conviction n'atteint simplement pas cet étage."""
        return state.resolved is not None and state.bounds is None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.resolved is None:
            raise StagePrerequisiteError("le bornage exige un passage résolu")

        demande = state.resolved
        unites = list(deps.corpus.pericopes_for(demande))

        if not unites:
            return self._hors_corpus_cure(state, demande)

        if len(unites) == 1:
            seule = unites[0]
            if _meme_empan(demande, seule.bounds):
                # **Coïncide.** Le pasteur a visé l'unité : on ne l'interrompt pas pour le lui
                # apprendre. Le motif trace que la coïncidence a été vérifiée.
                return StageResult(
                    outcome=Outcome.CONTINUE,
                    rationale=(
                        f"Bornes conformes à l'unité littéraire « {seule.label} ». "
                        f"{seule.rationale}"
                    ),
                    # L'identité voyage avec les bornes : sans elle, plus rien en aval ne peut
                    # lire ce qui a été curé sur cette unité.
                    state=state.with_(bounds=seule.bounds, pericope_id=seule.id),
                )
            return self._la_demande_coupe(state, deps, seule)

        return self._la_demande_englobe(state, deps, unites)

    # --- Les trois relations -----------------------------------------------------------------

    def _hors_corpus_cure(self, state: StudyState, demande: Reference) -> StageResult:
        """Aucune unité curée ne rencontre ce passage — et ce n'est pas une faute.

        `DEGRADE` plutôt que `REFUSE` : le pasteur garde ses bornes et travaille. Mais le motif
        dit ce qui manque, parce que la suite du pipeline y perdra la faisabilité homilétique."""
        return StageResult(
            outcome=Outcome.DEGRADE,
            rationale=(
                "Aucune unité littéraire curée ne couvre ce passage — vos bornes sont "
                "conservées. Ni faisabilité relue, ni alerte de proof-texting sur ce bornage."
            ),
            state=state.with_(bounds=_bornes_de(demande), bounds_overridden=True),
        )

    def _la_demande_coupe(
        self, state: StudyState, deps: EngineDeps, unite: PericopeView
    ) -> StageResult:
        """La demande est **strictement incluse** dans l'unité : il y a un vrai choix."""
        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=(
                f"Votre demande coupe l'unité littéraire « {unite.label} ». {unite.rationale}"
            ),
            state=state,
            options=(
                _option_unite(unite),
                Option(code=TEL_QUEL, label="Mes bornes", rationale=_COUT_DU_TEL_QUEL),
            ),
        )

    def _la_demande_englobe(
        self, state: StudyState, deps: EngineDeps, unites: Sequence[PericopeView]
    ) -> StageResult:
        """La demande couvre plusieurs unités : **N + 1** options (S8).

        Les N unités, chacune motivée — puis « le tout, en un sermon expositif », qui est un choix
        légitime et non un repli. Cas d'école : `Galates 5` = 5:1-12 · 5:13-15 · 5:16-26."""
        ordonnees = _ordonner(unites, deps, state.refused_axes)
        libelles = " · ".join(unite.label for unite in ordonnees)
        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=f"Votre demande couvre {len(unites)} unités littéraires : {libelles}.",
            state=state,
            options=(
                *(_option_unite(unite) for unite in ordonnees),
                Option(
                    code=EN_UN_SEUL,
                    label="Le tout, en un seul sermon",
                    rationale=(
                        "Un sermon expositif sur l'ensemble — les unités restent distinctes "
                        "dans le texte, c'est le plan qui les tient."
                    ),
                ),
            ),
        )


# --- S18 : la contrainte négative ordonne, elle ne refuse pas -----------------------------------


def _ordonner(
    unites: Sequence[PericopeView], deps: EngineDeps, refuses: Sequence[str]
) -> tuple[PericopeView, ...]:
    """Les unités dont l'axe dominant est refusé passent **en dernier**, jamais à la trappe.

    S18 — « 1 Cor 5:17 ou 2 Cor 5:17, mais je ne veux pas d'une créature en Christ ». Refuser le
    texte, c'est décider à sa place ; l'ignorer, c'est lui donner le sermon dont il ne veut pas.
    La bonne issue est de **borner ailleurs dans la même péricope**, et ça commence par montrer
    d'abord les bornes qui ne portent pas l'axe refusé.

    **Hors péricopes curées, aucun ordre — et jamais une erreur.** `dominant_axis` rend `None`,
    tout garde sa place : la dégradation est silencieuse, exactement comme S18 l'exige."""
    if not refuses:
        return tuple(unites)

    interdits = set(refuses)

    def _rang(unite: PericopeView) -> int:
        axe = deps.doctrine.dominant_axis(unite.id)
        return 1 if axe is not None and axe in interdits else 0

    # `sorted` est **stable** : à rang égal, l'ordre du canon est conservé. Deux unités qui se
    # valent ne doivent pas changer de place d'une exécution à l'autre — le déterminisme du
    # moteur en dépend.
    return tuple(sorted(unites, key=_rang))


# --- Comparer une demande à une unité ----------------------------------------------------------


def _empan(reference: Reference) -> tuple[tuple[int, int], tuple[int, int]]:
    """Le passage réduit à deux positions comparables — `(chapitre, verset)` de début et de fin.

    Les degrés de précision de `Reference` (S7, S23) se traduisent en bornes ouvertes : un livre
    entier va de tout en bas à tout en haut, un chapitre entier couvre tous ses versets."""
    if reference.is_whole_book:
        return (0, 0), (_INFINI, _INFINI)
    chapitre = reference.chapter or 0
    if reference.is_whole_chapter:
        return (chapitre, 0), (chapitre, _INFINI)
    debut = reference.verse_start or 0
    return (chapitre, debut), (chapitre, reference.verse_end or debut)


def _meme_empan(demande: Reference, bornes: Bounds) -> bool:
    """La demande **coïncide** avec l'unité — même début, même fin."""
    debut_demande, fin_demande = _empan(demande)
    debut_unite, _ = _empan(bornes.start)
    _, fin_unite = _empan(bornes.end)
    return debut_demande == debut_unite and fin_demande == fin_unite


def _bornes_de(reference: Reference) -> Bounds:
    """Les bornes du pasteur, telles quelles — quand aucune unité curée ne les encadre."""
    return Bounds(start=reference, end=reference)


def _option_unite(unite: PericopeView) -> Option:
    return Option(code=str(unite.id), label=unite.label, rationale=unite.rationale)
