"""Étage 6 — **la faisabilité homilétique** : un refus motivé, jamais un plan fabriqué.

E2 l'a établi contre la spec d'origine : la mise en forme homilétique **est un étage**, pas une
mise en page. Elle consomme les axes, elle rend un résultat motivé, et elle peut `REFUSE` —
`homiletic_feasibility.refusal_reason` existe en base précisément pour ça.

## La faisabilité est celle d'un triplet, pas d'un texte

`Romains 8:9-17` ne porte aucun personnage. Croisé avec **biographique**, il ne produit pas un
plan : il produit un refus, et le refus dit pourquoi.

> **Une combinaison impossible est signalée, jamais fabriquée.** Urim n'invente pas un personnage
> pour satisfaire une case.

Et les couples refusés voyagent avec les faisables — les cacher laisserait le pasteur croire qu'on
n'y a pas pensé.

## Le risque de proof-texting, et ce qui le relève

Il est **structurellement plus élevé en thématique** : les textes y sont convoqués pour confirmer.
Deux choses le relèvent encore, et elles ne choisissent jamais le texte (S26, S37) :

- une **intention déclarée** — « je veux motiver » n'ajoute aucun axe, ça change le risque ;
- la **charge d'une conviction** — même patron, même propriété de sûreté.

Un signal qui ne peut qu'**ajouter de la vigilance** ne peut pas nuire en se trompant. Et le motif
nomme l'effet, jamais l'état de celui qui écrit.

## Hors unité curée

`homiletic_feasibility` est clée sur la péricope : bornes forcées, aucune ligne. `DEGRADE`, jamais
`REFUSE` (S22) — *on ne punit pas une liberté qu'on a accordée, et on ne devine pas une
faisabilité que personne n'a relue.*
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contexts.urim.domain.libelles import RISQUES as RISQUES_EN_CLAIR
from app.contexts.urim.domain.libelles import en_clair, forme_en_clair
from app.contexts.urim.engine.deps import EngineDeps, Feasibility
from app.contexts.urim.engine.errors import StagePrerequisiteError
from app.contexts.urim.engine.outcomes import Outcome, StageResult
from app.contexts.urim.engine.state import StudyState

#: Du moins au plus risqué. L'ordre **est** l'échelle — il n'y a pas de score.
RISQUES: tuple[str, ...] = ("faible", "moyen", "eleve")


class ShapeHomiletic:
    """Le septième étage. Il refuse plutôt que de fabriquer."""

    code = "shape_homiletic"

    def applies(self, state: StudyState) -> bool:
        """Il faut un axe retenu — la forme se décide après le fond, jamais avant.

        🔴 **La condition exigeait aussi `subject_matter is None`, et elle se coupait
        elle-même.** La décision écrit les deux champs d'un coup ; l'étage ne se rejouait donc
        plus jamais, et sa propre branche `CONTINUE` — la seule qui relève le risque et qui
        dise la mise en forme retenue — était **injoignable depuis l'API**. La promesse faite
        à l'écran des axes (« le risque sera relevé sur la mise en forme ») n'était jamais
        tenue.

        L'étage est pur et déterministe : le rejouer ne coûte rien, et c'est ce qui permet à
        son motif d'être **dans la trace à chaque tour** plutôt qu'une seule fois, perdu."""
        return state.axis is not None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.axis is None:
            raise StagePrerequisiteError("la mise en forme exige un axe retenu")

        if state.pericope_id is None:
            return StageResult(
                outcome=Outcome.DEGRADE,
                rationale=(
                    "Bornes hors unité curée — aucune faisabilité relue, et donc aucune alerte "
                    "de risque de proof-texting. La préparation continue."
                ),
                state=state,
            )

        couples = list(deps.homiletics.couples_for(state.pericope_id))

        # ⚠️ **Aucune ligne n'est pas la même chose que « rien n'est faisable ».**
        #
        #     aucune ligne  →  personne n'a encore regardé
        #     que des refus →  quelqu'un a regardé, et rien ne tient sur ce texte
        #
        # `bear_axes` tient cette distinction depuis le début ; cet étage ne la tenait pas, et
        # le défaut n'apparaissait qu'une fois la curation *améliorée* : sans péricope il
        # dégradait et continuait, avec une péricope pesée mais sans faisabilité il refusait.
        # Ajouter du relu rendait la sortie pire, ce qui est le signe d'une confusion et non
        # d'une sévérité.
        if not couples:
            return StageResult(
                outcome=Outcome.DEGRADE,
                rationale=(
                    "Aucune faisabilité n'a encore été relue sur cette unité — ni mise en "
                    "forme proposée, ni alerte de proof-texting. La préparation continue."
                ),
                state=state,
            )

        faisables = [couple for couple in couples if couple.feasible]
        refuses = [couple for couple in couples if not couple.feasible]

        if not faisables:
            # Tous les couples relus sont refusés : c'est un fait curé, pas un échec du
            # moteur. Et chaque refus porte son motif.
            return StageResult(
                outcome=Outcome.REFUSE,
                rationale=_avec_refus(
                    "Aucune mise en forme n'est faisable sur cette unité.", refuses
                ),
                state=state,
            )

        # ⚠️ **Cette garde est celle de l'étage, pas celle du produit.**
        #
        # La bordure valide déjà le couple reçu (`UrimStudyService._appliquer`). On la garde :
        # un étage qui reçoit un état incohérent doit le dire, et trois tests la tiennent.
        # Mais elle n'est **pas** la protection du pasteur ; ne pas les confondre.
        sien = _trouver(couples, state.plan_source, state.subject_matter)
        if state.plan_source is not None and (sien is None or not sien.feasible):
            motif = sien.refusal_reason if sien else "Ce couple n'a pas été relu."
            return StageResult(outcome=Outcome.REFUSE, rationale=motif, state=state)

        # 🔴 **D55 — on tranche au lieu d'offrir.**
        #
        # L'étage proposait trois couples et, pour tout motif, un adjectif : « faible »,
        # « moyen », « élevé ». Trois défauts en un écran — du vocabulaire d'exégète là où un
        # pasteur veut un plan ; un adjectif sans motif, alors que les couples **écartés**,
        # eux, sont argumentés ; et le travail reporté sur lui au moment où il vient chercher
        # de l'aide. *« Il ne faut pas donner du boulot en supplément. »*
        #
        # ⚠️ Trancher **n'est pas** écrire à sa place : le couple retenu est une mise en forme,
        # pas une division. Le moteur ne rédige aucun point ici, et les autres restent à côté,
        # avec leur risque, pour qu'il en change d'un geste.
        choisi = sien or couple_propose(faisables)
        risque = _releve(choisi.proof_text_risk, state.risk_flags)
        return StageResult(
            outcome=Outcome.CONTINUE,
            rationale=_avec_refus(
                _motif_du_retenu(choisi, risque, faisables, state), refuses
            ),
            state=state.with_(
                plan_source=choisi.plan_source, subject_matter=choisi.subject_matter
            ),
        )


# --- Le risque -----------------------------------------------------------------------------------


def _releve(risque: str, drapeaux: Sequence[str]) -> str:
    """Une intention ou une charge **relève** le risque d'un cran — elle ne choisit aucun texte.

    Faux positif : de la vigilance en plus, inoffensif. Faux négatif : le comportement
    d'aujourd'hui. Aucun modèle : rien ne casse. C'est ce qui rend ce signal acceptable là où
    « détecter pour router » ne l'était pas."""
    if not drapeaux or risque not in RISQUES:
        return risque
    return RISQUES[min(RISQUES.index(risque) + 1, len(RISQUES) - 1)]


def couple_propose(faisables: Sequence[Feasibility]) -> Feasibility:
    """Le faisable qui **expose le moins**, et le même à chaque rejeu.

    ⚠️ **Déterministe comme `theme_propose`, et pour la même raison.** Comparer le couple
    enregistré à ce que cette fonction rendrait dit si le pasteur en a changé — sans la
    colonne qui aurait dit la même chose, et qui aurait pu la contredire. Le départage par
    nom n'est pas de la coquetterie : sans lui, deux couples au même risque rendraient
    l'ordre du corpus déterminant, et le motif deviendrait faux le jour d'un ressemis.

    🔴 **Les drapeaux de charge n'entrent pas ici.** Ils relèvent la vigilance d'un cran, et
    uniformément — les faire peser sur le choix leur donnerait le pouvoir de *choisir un
    texte*, c'est-à-dire exactement la propriété de sûreté que S26 et S37 refusent. Un signal
    qui ne peut qu'ajouter de la vigilance ne peut pas nuire en se trompant ; un signal qui
    choisit, si."""
    return min(
        faisables,
        key=lambda c: (_rang(c.proof_text_risk), c.plan_source, c.subject_matter),
    )


def _phrase(texte: str) -> str:
    """La glose du corpus, promue en phrase — sans toucher aux mots.

    Les libellés sont écrits pour être enchâssés (« peu de risque de… ») ; ici ils tiennent
    seuls. La majuscule se pose sur la première **lettre**, pas sur le premier caractère :
    « ⚠ risque réel… » commence par un pictogramme."""
    for i, caractere in enumerate(texte):
        if caractere.isalpha():
            return f"{texte[:i]}{caractere.upper()}{texte[i + 1:]}."
    return texte


def _rang(risque: str) -> int:
    """Un risque hors échelle passe **en dernier** — on ne classe pas ce qu'on ne comprend
    pas devant ce qu'on a relu."""
    return RISQUES.index(risque) if risque in RISQUES else len(RISQUES)


def _motif_du_retenu(
    choisi: Feasibility, risque: str, faisables: Sequence[Feasibility], state: StudyState
) -> str:
    """**Pourquoi celle-ci** — et jamais un adjectif seul.

    🔴 On expliquait pourquoi on refuse, jamais pourquoi on accepte : les couples écartés
    portaient leur motif relu, le couple retenu portait « faible ». *Un plan rédigé sans son
    motif est un oracle* — c'est le filet doré, et c'est ce qui sépare un atelier d'un oracle.

    Les mots sont ceux du prédicateur, pas ceux du schéma : « un plan collé au texte sur une
    doctrine », et le risque dit en clair plutôt que noté."""
    forme = forme_en_clair(choisi.plan_source, choisi.subject_matter)
    dit = f"Plan retenu : {forme}."

    if state.plan_source is not None and choisi is not couple_propose(faisables):
        # Sa décision se dit comme la sienne. Lui répéter qu'elle « expose le moins » serait
        # faux, et lui laisser croire que c'est nous qui l'avons choisie l'est autant.
        dit += " C'est celle que vous avez retenue."
    elif len(faisables) == 1:
        # Un comparatif sur un ensemble d'un seul serait une flatterie. C'est un fait.
        dit += " C'est la seule mise en forme que cette unité tient."
    else:
        dit += (
            f" Sur les {len(faisables)} mises en forme que cette unité tient, c'est celle "
            "qui expose le moins."
        )
        if aussi := [c for c in faisables if c is not choisi and _rang(
            c.proof_text_risk
        ) == _rang(choisi.proof_text_risk)]:
            # Ne pas le dire ferait passer un départage alphabétique pour un jugement.
            dit += (
                f" {len(aussi)} autre(s) exposent aussi peu — elles restent à côté, vous "
                "pouvez en prendre une."
            )

    # ⚠️ **Le risque se dit toujours, et il se dit en entier.**
    #
    # 🔴 Ma première version le glissait dans la branche comparative : sur une unité qui ne
    # tient qu'une seule mise en forme, le pasteur lisait « c'est la seule » et **rien sur le
    # risque** — puis, drapeau levé, « le risque est relevé d'un cran » sans avoir jamais su
    # depuis quoi. Le seul cas où l'information manquait était celui où il n'avait aucun choix.
    dit += " " + _phrase(en_clair(risque, RISQUES_EN_CLAIR))

    if state.risk_flags:
        # ⚠️ Le motif nomme **l'effet**, jamais l'état de celui qui écrit (S10, S37). La même
        # phrase qu'à l'écran des axes, et c'est voulu : elle y annonçait le relèvement, elle
        # le constate ici. Deux formulations auraient laissé croire à deux mécanismes.
        dit += (
            " Formulation à forte charge : le risque est relevé d'un cran, et davantage de "
            "textes qui résistent sont affichés."
        )
    return dit


# --- Les couples ---------------------------------------------------------------------------------


def _trouver(
    couples: Sequence[Feasibility], plan: str, matiere: str | None
) -> Feasibility | None:
    for couple in couples:
        if couple.plan_source == plan and (
            matiere is None or couple.subject_matter == matiere
        ):
            return couple
    return None


def _avec_refus(tete: str, refuses: Sequence[Feasibility]) -> str:
    """Les impossibles s'affichent **avec** les possibles — signalés, jamais fabriqués.

    🔴 **Illisible sur un téléphone, le 22/08/2026.** Quinze couples collés bout à bout, chacun
    traînant son motif entier, dans un seul paragraphe gris qui remplissait deux écrans. Et
    répétitif, ce qui est pire : *« ce passage ne porte aucun personnage nommé… »* revenait
    **trois fois**, une par forme de plan.

    La cause n'était pas la longueur, c'était la structure. **Le refus porte sur la matière,
    pas sur la forme du plan** : « biographique » est écarté pour la même raison qu'on
    l'aborde en textuel, en expositif ou en thématique. On groupe donc par motif, et on le dit
    une fois.

    ⚠️ **On ne touche pas au motif lui-même.** Il vient du relu — c'est la phrase d'un homme
    qui a lu ce passage. L'abréger serait réécrire son travail ; le regrouper ne fait que
    cesser de le répéter.

    Les retours à la ligne sont voulus : une liste se lit, un paragraphe de quinze parenthèses
    se saute."""
    if not refuses:
        return tete

    par_motif: dict[str, list[Feasibility]] = {}
    for couple in refuses:
        par_motif.setdefault(couple.refusal_reason, []).append(couple)

    lignes = []
    for motif in sorted(par_motif):
        groupe = par_motif[motif]
        matieres = sorted({c.subject_matter for c in groupe})
        plans = sorted({c.plan_source for c in groupe})

        # Une matière refusée sur **toutes** les formes ne se nomme qu'une fois : c'est la
        # matière qui ne tient pas, et le pasteur a besoin de le savoir comme ça.
        if len(matieres) == 1 and len(plans) > 1:
            cle = f"{matieres[0]} — quelle que soit la forme du plan"
        else:
            cle = " · ".join(f"{c.plan_source} x {c.subject_matter}" for c in groupe)
        lignes.append(f"• {cle} : {motif}")

    return tete + "\n\nÉcartées :\n" + "\n".join(lignes)
