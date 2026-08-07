"""Étage 0 — **le détecteur d'entrée** (S33 · S34 · S35 · S36).

Trois portes existaient, et le moteur croyait celle que le pasteur avait cochée. Or les entrées
réelles ne respectent aucun onglet : « l'histoire de Jézabel » saisi en *référence* (S23),
« 1 Roi ou 2 Roi, il s'agit de Jézabel la femme du Roi » (S24), « nexiiste » (S21), ou
`Rom 8:1` **accompagné de sa citation** (S16). Une conviction tapée dans le champ *référence*
fausse tout le pipeline en aval, et rien ne le rattrapait.

---

## Ce que cet étage ne fait pas

**Il ne reclasse pas en silence.** Le pasteur qui saisit dans *référence* et recevrait le
pipeline de la conviction sans comprendre — c'est la machine qui décide à sa place, et S10
l'interdit : *le moteur ne diagnostique jamais celui qui écrit*. Mais exiger qu'il ait choisi le
bon onglet, c'est refuser le terrain. La sortie est celle du dépôt entier :

> **Le calcul propose, la personne dispose.**

**Il n'appelle aucun modèle.** S'il était une étape modèle il serait `metered` : au plafond, la
porte d'entrée elle-même disparaîtrait, et « aucun mur » deviendrait faux au **premier** étage —
pire que le problème réglé par S12.

## Trois corrections nées d'une simulation à blanc

La porte 16 — *« Ma voiture 406, a besoin de reparation , jefgf Paradis »* — a cassé trois
hypothèses de la première version :

**S35 · un nom de livre ne suffit pas.** `Job`, `Nombres`, `Juges`, `Actes`, `Rois` sont des mots
français courants. Et exiger un chiffre ne sauve rien — « Ma voiture **406** » en contient un. Ce
qui distingue une référence, c'est la **contiguïté** : `Romains 8:10` forme un bloc, « ma … 406 …
paradis » n'en forme aucun.

**S34 · le lexique de la langue, et un décompte.** Le ratio se calculait sur `idf`, bâti sur
l'Écriture — donc *voiture*, *réseaux*, *chômage* en étaient absents, et une conviction sur
l'église d'aujourd'hui se faisait déclarer illisible. On compte désormais **au moins un mot
reconnu**, dans le lexique de la **langue** : un token pourri sur neuf ne pèse plus rien.

**S36 · la provenance plutôt que la divination.** Le vrai défaut n'était pas la détection : c'était
qu'un micro resté ouvert produise une saisie que le moteur devait *deviner*. Le système sait d'où
vient la chaîne — une dictée qui ne donne pas un signal univoque **se fait confirmer**.

## L'asymétrie du doute

> **En cas de doute, on route vers `conviction` — jamais vers charabia.**

Dire à un pasteur que sa phrase est incompréhensible alors qu'elle ne l'est pas est la pire
erreur possible à la porte d'entrée. Mieux vaut accepter une conviction faible : le plafond du
corpus curé produira plus loin un refus franc (S3). C'est l'asymétrie de S2 — *un candidat faible
reste un candidat.*

Et le motif du refus ne renvoie **jamais** le verdict du corpus : un clavier malheureux n'est pas
« aucune péricope ne porte cet axe ». Il attire à la correction, sans reproche.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contexts.urim.engine.deps import EngineDeps, ReferenceSpan
from app.contexts.urim.engine.normalizer import tokens as decouper
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.state import EntryMode, EntryOrigin, StudyState

#: Recouvrement avec le texte biblique au-delà duquel on lit une **citation**. Un pari, comme
#: tous les seuils du produit — à revoir sur des saisies réelles, pas à graver.
CITATION_AFFINITY = 0.45

#: Combien de mots la langue doit reconnaître pour qu'une saisie soit une **phrase**. Un seul
#: suffit, et c'est délibéré (S34) : on ne refuse que ce qui n'a *rien* de reconnaissable.
MOTS_RECONNUS_MINIMUM = 1

_LIBELLES: dict[EntryMode, str] = {
    EntryMode.REFERENCE: "une référence",
    EntryMode.CITATION: "une phrase des Écritures",
    EntryMode.CONVICTION: "une intention",
}

#: Le code de l'option « ce n'est pas ça » — le seul qui ne pose pas de mode, mais rouvre la
#: saisie. C'est lui qui referme un micro ouvert en un tap.
REFORMULER = "reformuler"

_CHARABIA = (
    "Je n'arrive pas à lire ceci — ni une référence, ni une phrase des Écritures, "
    "ni une intention. Vous vouliez peut-être dire… ?"
)

_CHARABIA_DICTE = (
    "Je n'arrive pas à lire ce qui a été dicté — ni une référence, ni une phrase des "
    "Écritures, ni une intention. Le micro s'est peut-être déclenché tout seul."
)


class RouteEntry:
    """Le premier étage. Il route, ou il rend la main — jamais il ne devine à la place."""

    code = "route_entry"

    def applies(self, state: StudyState) -> bool:
        """Une seule fois par préparation.

        Sans ce garde, la reprise après `AWAIT` re-détecterait, re-diviserait, et redemanderait
        indéfiniment la même chose : le pasteur tranche, le moteur repart, l'étage 0 s'applique à
        nouveau. La `trace` porte déjà la mémoire de ce qui s'est exécuté — on la lit."""
        return not any(passage.stage_code == self.code for passage in state.trace)

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        mots = decouper(state.raw_input)
        if not mots:
            return self._refuser(state)

        bloc = _bloc_de_reference(deps.corpus.find_reference_span(mots), mots)
        cite = deps.corpus.scripture_affinity(mots) >= CITATION_AFFINITY

        # **L'entrée hybride se résout ici** (S16). Deux sources qui se corroborent sont un
        # cadeau, pas un conflit : on résout sur la référence, la citation servira à vérifier —
        # c'est elle qui attrape « vous citez Rm 8:1 mais votre texte est Rm 8:34 ». Le mode
        # saisi ne peut pas la contredire, donc aucune main rendue.
        if bloc is not None and cite:
            return self._router(
                state,
                EntryMode.REFERENCE,
                f"Référence ({bloc.book}) **et** citation : on résout sur la référence, "
                "la citation vérifiera.",
                force=True,
            )

        if bloc is not None:
            return self._router(
                state, EntryMode.REFERENCE, f"Nom de livre en bloc contigu : {bloc.book}."
            )

        if cite:
            return self._router(
                state, EntryMode.CITATION, "Recouvrement fort avec le texte biblique."
            )

        # Ni livre, ni texte biblique : reste à savoir si c'est une phrase ou un clavier. Le
        # décompte suffit — **un seul mot reconnu** ouvre la porte de la conviction (S34).
        if deps.corpus.known_words(mots) >= MOTS_RECONNUS_MINIMUM:
            return self._router(
                state, EntryMode.CONVICTION, "Ni référence ni citation, mais une phrase lisible."
            )

        return self._refuser(state)

    # --- Les trois sorties ------------------------------------------------------------------

    def _refuser(self, state: StudyState) -> StageResult:
        dicte = state.entry_origin is EntryOrigin.DICTATED
        return StageResult(
            outcome=Outcome.REFUSE,
            rationale=_CHARABIA_DICTE if dicte else _CHARABIA,
            state=state,
        )

    def _router(
        self, state: StudyState, detecte: EntryMode, motif: str, *, force: bool = False
    ) -> StageResult:
        """Continue si le signal confirme le mode saisi ; rend la main s'il le contredit.

        **Sauf pour une dictée non univoque** (S36) : une conviction sortie d'un micro se fait
        confirmer même quand elle est cohérente avec l'onglet, parce que le doute ne porte alors
        pas sur la lecture — il porte sur le fait que le pasteur ait voulu saisir quoi que ce
        soit."""
        dicte = state.entry_origin is EntryOrigin.DICTATED
        a_confirmer = dicte and detecte is EntryMode.CONVICTION

        if (force or detecte is state.entry_mode) and not a_confirmer:
            return StageResult(
                outcome=Outcome.CONTINUE,
                rationale=f"Lu comme {_LIBELLES[detecte]}. {motif}",
                state=state.with_(entry_mode=detecte),
            )

        if a_confirmer:
            return StageResult(
                outcome=Outcome.AWAIT,
                rationale=(
                    f"J'ai entendu : « {state.raw_input} ». C'est bien ce que vous vouliez ?"
                ),
                state=state,
                options=(_reformuler(), *_deux_lectures(detecte, state.entry_mode, motif)),
            )

        # Le signal contredit l'onglet. On ne tranche pas : on montre les deux lectures, chacune
        # motivée, et le pasteur choisit. L'option porte le code du mode — la décision se
        # contente de poser `entry_mode`.
        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=(
                f"Saisi comme {_LIBELLES[state.entry_mode]}, mais lu comme "
                f"{_LIBELLES[detecte]}. {motif}"
            ),
            state=state,
            options=_deux_lectures(detecte, state.entry_mode, motif),
        )


# --- Le bloc de référence (S35) ------------------------------------------------------------


def _bloc_de_reference(
    span: ReferenceSpan | None, mots: Sequence[str]
) -> ReferenceSpan | None:
    """Un nom de livre **fait référence** s'il forme un bloc, pas s'il traîne dans une phrase.

    Deux formes acceptées, et une seule question à chaque fois — *le nom et les chiffres
    tiennent-ils ensemble ?* :

    - **le nom suivi de chiffres contigus** — `Romains 8 10 15`, `Job 38` ;
    - **le nom qui couvre toute la saisie** — `1 Rois`, le livre entier de S23.

    Tout le reste est un mot français qui se trouve être un nom de livre : « mon job me prend
    tout mon temps », « il y a trop de juges dans cette assemblée » — cette dernière étant, pour
    couronner le tout, l'accusation de S20."""
    if span is None:
        return None

    fin = span.stop
    while fin < len(mots) and mots[fin].isdigit():
        fin += 1

    porte_des_chiffres = fin > span.stop
    couvre_toute_la_saisie = span.start == 0 and fin == len(mots)

    if porte_des_chiffres or couvre_toute_la_saisie:
        return ReferenceSpan(book=span.book, start=span.start, stop=fin)
    return None


# --- Les options -----------------------------------------------------------------------------


def _reformuler() -> Option:
    return Option(
        code=REFORMULER,
        label="Ce n'est pas ça",
        rationale="Rouvre la saisie sans rien conserver de ce qui a été entendu.",
    )


def _deux_lectures(
    detecte: EntryMode, saisi: EntryMode, motif: str
) -> tuple[Option, ...]:
    """Le détecté d'abord — c'est celui que les faits soutiennent, pas celui qu'on impose.

    Si les deux coïncident (cas d'une dictée cohérente), une seule lecture est proposée : on ne
    fabrique pas un choix là où il n'y en a pas."""
    lectures = [
        Option(code=detecte.value, label=_LIBELLES[detecte].capitalize(), rationale=motif)
    ]
    if saisi is not detecte:
        lectures.append(
            Option(
                code=saisi.value,
                label=_LIBELLES[saisi].capitalize(),
                rationale="Ce que vous aviez indiqué — gardez-le si c'était bien votre intention.",
            )
        )
    return tuple(lectures)


def modes_proposes(options: Sequence[Option]) -> tuple[EntryMode, ...]:
    """Les modes derrière une liste d'options — `reformuler` n'en est pas un, il rouvre."""
    return tuple(EntryMode(o.code) for o in options if o.code != REFORMULER)
