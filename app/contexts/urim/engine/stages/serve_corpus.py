"""Étage 3 — **servir le texte** : quelle version, et ce qui se passe quand elle coûte.

C'est ici que le plafond mord, et nulle part ailleurs. Deux règles, et la seconde est la promesse
du produit.

## Réserver n'est pas consommer (S6)

Le plafond ne se vérifie **ni à l'ouverture** — on ne sait pas encore si la préparation touchera
une ressource facturée — **ni à chaque appel**. Il se vérifie au **premier service d'une version
comptée**, c'est-à-dire ici. Après quoi le droit est **acquis pour la durée de la réservation** :
une préparation commencée va jusqu'au bout, même si un autre pasteur fait tomber le plafond
entre-temps.

Ancré à l'ouverture, le plafond faisait mentir §13 — *« un pasteur qui travaille sur Segond 1910
ne rencontre jamais aucune limite »*. Ancré ici, l'intention est préservée.

## Le filet ne peut pas céder

Quand le plafond est atteint, on retombe sur le domaine public. Et ce repli est **increvable par
construction** : la contrainte `licence_coherente` interdit qu'une version du domaine public soit
`metered`. Il n'existe aucun état de la base où le texte de secours serait lui-même bloqué.

C'est une règle produit écrite dans un `CHECK`, pas une intention de code — la différence entre un
filet et une promesse.

## Aucun mur, et aucun compteur

`DEGRADE` ne coupe jamais le pipeline. Et rien ne s'affiche **avant** la dégradation : un compteur
visible ferait rationner, le pasteur hésiterait avant d'ouvrir un texte — l'inverse exact du but.
La dégradation s'explique en une ligne, sans reproche.
"""

from __future__ import annotations

from app.contexts.urim.engine.deps import EngineDeps
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.outcomes import Outcome, StageResult
from app.contexts.urim.engine.state import StudyState


class ServeCorpus:
    """Le quatrième étage. Il sert un texte, et il n'en refuse jamais un."""

    code = "serve_corpus"

    def applies(self, state: StudyState) -> bool:
        """Il faut des bornes — on ne sert pas un texte dont on ignore l'étendue."""
        return state.bounds is not None and state.version_id is None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.bounds is None:
            raise StagePrerequisiteError("servir le texte exige un passage borné")

        repli = deps.versions.public_domain_fallback()
        souhaitee = state.version_id or repli

        if not deps.versions.is_metered(souhaitee):
            # Domaine public : le plafond ne la voit même pas. C'est le chemin de la grande
            # majorité des préparations, et il ne coûte rien.
            return StageResult(
                outcome=Outcome.CONTINUE,
                rationale="Texte servi depuis une version du domaine public.",
                state=state.with_(version_id=souhaitee),
            )

        if deps.versions.ceiling_reached():
            # **Le seul repli du moteur.** Il ne coupe pas, il ne reproche rien, et il dit ce
            # qu'il fait — une ligne, pas un écran de limite.
            return StageResult(
                outcome=Outcome.DEGRADE,
                rationale=(
                    "La version demandée n'est pas disponible ce mois-ci — texte servi depuis "
                    "la version du domaine public. La préparation continue."
                ),
                state=state.with_(version_id=repli),
            )

        # Première consommation d'une version comptée : le droit est acquis à partir d'ici, pour
        # la durée de la réservation.
        return StageResult(
            outcome=Outcome.CONTINUE,
            rationale="Texte servi depuis la version demandée.",
            state=state.with_(version_id=souhaitee),
        )
