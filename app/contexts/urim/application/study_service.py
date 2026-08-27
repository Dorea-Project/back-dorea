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
from datetime import date, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from app.contexts.urim.application.access import ensure_may_prepare, ensure_may_read
from app.contexts.urim.application.conversation import Ecran, conduire, lire_la_notation
from app.contexts.urim.application.ports import (
    AssistedResolver,
    AucuneSortie,
    CitationAilleursReader,
    CollisionSeen,
    ConcordanceDTO,
    ElementRecord,
    Maturite,
    NullCitationAilleurs,
    NullVerseResolver,
    ParoleDuFil,
    PassageDetailDTO,
    PlanSuggestion,
    PreacherAuthorization,
    PreparationRecord,
    ReferenceElsewhere,
    ReservationPort,
    StudyDTO,
    StudyRepository,
    SuggestionSnapshot,
    SupportRecord,
    UnlimitedTierPort,
    VariantSeen,
    VerseServed,
    WitnessRead,
)
from app.contexts.urim.application.reference_libre import (
    lire,
    lisible_reference,
    references_dans,
)
from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.domain.errors import (
    ElementInconnuError,
    OptionInconnueError,
    PreparationIntrouvableError,
    RangementImpossibleError,
    TitreIllisibleError,
)
from app.contexts.urim.domain.squelette import CODES, code_canonique
from app.contexts.urim.engine.deps import (
    ConvictionReader,
    EngineDeps,
    NullConvictionReader,
)
from app.contexts.urim.engine.liaison import rang_a_l_ecran, viser_un_point
from app.contexts.urim.engine.normalizer import normalize
from app.contexts.urim.engine.normalizer import tokens as decouper
from app.contexts.urim.engine.outcomes import Outcome
from app.contexts.urim.engine.pipeline import UrimEngine
from app.contexts.urim.engine.stages.bound_pericope import EN_UN_SEUL, TEL_QUEL
from app.contexts.urim.engine.stages.propose_theme import theme_propose
from app.contexts.urim.engine.stages.resolve_passage import PAS_UNE_CITATION
from app.contexts.urim.engine.stages.route_entry import CITATION_AFFINITY, REFORMULER
from app.contexts.urim.engine.stages.vestibule import (
    CHANGER,
    CONSENTIR,
    LIRE_SEULEMENT,
    RATTACHER,
)
from app.contexts.urim.engine.state import (
    AxisGloss,
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

#: Le haut de l'intervalle quand la référence ne le dit pas — un chapitre entier, un livre
#: entier. La même convention que `_INFINI` au bornage : on ne devine pas la fin, on la laisse
#: ouverte et c'est le corpus qui l'arrête.
_FIN_OUVERTE = 10**9

#: Combien de textes résistants on rapporte d'ailleurs. Trois : au-delà, la page devient une
#: bibliographie et le pasteur n'en lit aucun — ce qui revient exactement à n'en montrer aucun.
_RESISTANTS_MAX = 3


def _empreinte_de_la_demande(chemin: str, lisible: str) -> str:
    """Ce sur quoi le modèle a été interrogé — **le chemin autant que la saisie**.

    « citation » et « conviction » ne posent pas la même question au modèle. Ne condenser que
    la saisie ferait servir à un pasteur qui corrige son mode d'entrée la réponse à la question
    qu'il vient précisément d'abandonner."""
    return hashlib.sha256(f"{chemin}::{normalize(lisible)}".encode()).hexdigest()[:32]


def _marquer_les_ecartees(
    options, stage_code: str, ecartees: list[tuple[str, str]]
) -> tuple[tuple[str, str, str, str, bool, str | None, str | None], ...]:
    """Les options écartées **restent**, marquées et reléguées en fin de liste.

    Les retirer serait plus simple à écrire et faux à lire : le pasteur ne saurait plus ce
    qu'Urim lui avait proposé, ni qu'il l'avait repoussé, et il ne pourrait pas revenir dessus.
    C'est la règle des couples refusés — *les cacher laisserait croire qu'on n'y a pas pensé*.

    Le filtre porte sur `(étage, code)` et non sur le code seul : la même option peut être
    offerte par deux étages, et l'écarter à l'un ne dit rien de l'autre."""
    repoussees = {code for etage, code in ecartees if etage == stage_code}
    rendues = tuple(
        (
            o.code, o.label, o.rationale, o.origin, o.code in repoussees, o.strength,
            o.signature, o.reference,
        )
        for o in options
    )
    # Tri **stable** : l'ordre du moteur est une décision d'étage, on ne fait que descendre
    # ce qui a été repoussé sans toucher au reste.
    return tuple(sorted(rendues, key=lambda o: o[4]))


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


#: ⚠️ **Ce qu'une décision périme, par profondeur — et l'ordre du pipeline est la seule règle.**
#:
#: Quatre portées, pas une par étage : ce qui compte n'est pas *quel* étage a tranché, c'est
#: **jusqu'où** sa décision remonte le fil. Les nommer par ce qu'elles emportent plutôt que par
#: l'étage qui les déclenche évite d'avoir à réviser une liste à chaque étage nouveau.
#:
#: `bounds_overridden` retombe à `False` et non à `None` : c'est un booléen, et son absence de
#: valeur **est** `False`.
_TOUT_L_AVAL: Final = (
    "pericope_id", "bounds_overridden", "axis_code", "plan_source", "subject_matter", "theme",
)

#: Changer de **texte** garde l'angle : sur le chemin inversé, le pasteur a nommé son axe avant
#: qu'aucun texte n'existe, et c'est la seule chose qu'il ait dite.
_SOUS_LE_TEXTE: Final = ("pericope_id", "bounds_overridden", "plan_source", "subject_matter",
                         "theme")

#: Changer de **bornes** ne touche pas à l'angle non plus — mais la faisabilité est clée sur
#: l'unité, donc elle tombe avec elle (S22).
_SOUS_LES_BORNES: Final = ("plan_source", "subject_matter", "theme")

#: Sous l'angle comme sous la mise en forme, il n'y a que le thème — les deux le composent, et
#: rien d'autre n'en dépend. Nommé plutôt que répété : les portées se lisent alors comme une
#: table, et un étage nouveau se range dans l'une d'elles au lieu d'inventer sa liste.
_LE_THEME: Final = ("theme",)

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


def _a_etabli_un_fait(run) -> bool:
    """Le moteur a-t-il **dit quelque chose** sur ce que le pasteur a écrit ?

    C'est la même frontière que `_est_une_impasse_de_recherche`, prise par l'autre bout. Là-bas :
    *« je ne connais pas de livre nommé Zorobabel » est un fait sur l'orthographe, et y répondre
    par des passages thématiques noierait la seule information utile.* La règle valait pour les
    suggestions ; elle ne s'appliquait pas à la résolution assistée, qui **écrasait** le fait au
    lieu de le noyer.

        Hebreux 2:29  -> « Hebreux 2 compte 18 versets » puis, en silence, Hebreux 2:9
        Zorobabel 3:5 -> un refus AVEC `resolved = Esdras 3:5` enregistre derriere

    Un refus de l'étage 0 y entre aussi, et même quand il porte sur du charabia : la trouvaille
    devient alors une option qu'aucun étage n'offre, ce qui est strictement plus sûr que de la
    poser comme résolue.

    Ailleurs — citation de mémoire, paraphrase, personnage nommé autrement que dans la
    traduction — le moteur n'a **rien** à dire, et la résolution assistée garde tout son sens."""
    if not run.results or run.results[-1].outcome is not Outcome.REFUSE:
        return False
    dernier = run.state.trace[-1].stage_code if run.state.trace else ""
    if dernier == "route_entry":
        return True
    return dernier == "resolve_passage" and run.state.entry_mode is EntryMode.REFERENCE


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


def _travail_commence(record: PreparationRecord) -> bool:
    """Y a-t-il quelque chose à perdre ?

    Le même prédicat que l'étage, écrit sur l'enregistrement : sans travail engagé, un
    changement de sujet n'est pas une suspension — c'est simplement la suite de la
    conversation, et l'interrompre par une question serait du zèle."""
    return any((
        record.resolved_ref is not None,
        record.pericope_id is not None,
        record.axis_code is not None,
        record.theme is not None,
    ))


def _parole(lu) -> str | None:
    """La phrase de l'agent, et sa relance — **jamais deux fois la même chose**.

    Le modèle rend les deux séparément parce qu'elles n'ont pas le même rôle : l'une accueille,
    l'autre ouvre. À l'écran il n'y a qu'un motif, et c'est ici qu'elles se rejoignent."""
    if lu is None:
        return None
    morceaux = [lu.reply.strip(), (lu.question or "").strip()]
    return " ".join(m for m in morceaux if m) or None


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
    #: La seconde passe sur les versions que l'index ne charge pas. `NullCitationAilleurs`
    #: est un état de production : sans elle, on retrouve le comportement d'avant.
    ailleurs: CitationAilleursReader = field(default_factory=NullCitationAilleurs)
    #: La sortie du quota personnel. `AucuneSortie` **est** l'état de production tant que la
    #: facturation n'existe pas — voir `UnlimitedTierPort`.
    tier: UnlimitedTierPort = field(default_factory=AucuneSortie)

    # -- ouverture -------------------------------------------------------------

    async def open(
        self,
        *,
        actor_account_id: UUID,
        church_id: UUID | None = None,
        raw_input: str,
        entry_origin: EntryOrigin = EntryOrigin.TYPED,
        service_date: date | None = None,
    ) -> StudyDTO:
        await self._ensure_preacher(actor_account_id, church_id)
        maintenant = self.clock()

        # ── Le vestibule, **avant** que quoi que ce soit descende ────────────────────────
        #
        # 🔴 *Envoyer un texte n'est pas demander à le préparer.* Jusqu'au 22/08, les deux
        # étaient le même geste : le pasteur écrivait « bonjour Urim » et repartait avec une
        # préparation ouverte sur rien. La ligne se crée toujours — c'est elle qui porte la
        # conversation — mais le moteur ne descendra pas tant qu'il n'aura pas dit oui.
        lu = await self._lire_le_vestibule(
            church_id=church_id, author_id=actor_account_id,
            texte=raw_input, at=maintenant,
        )

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
            # **Sans lecture, le vestibule s'efface** — voir `_lire_le_vestibule`.
            maturity=lu.maturite if lu else Maturite.CONFIRME,
            carried_subject=lu.sujet if lu else None,
        )
        await self.studies.add(record)

        # Clé **provisoire** : la saisie normalisée. On ne sait pas encore sur quel texte
        # on travaille, et prétendre le contraire fausserait le décompte dès l'ouverture.
        # Le re-clage (S9) se fait dans `_rejouer`, dès que la péricope apparaît.
        #
        # ⚠️ **Avec ou sans église.** La réservation portait le décompte d'une église ; elle
        # porte aussi celui d'une personne, et c'est la même chose pour la même raison —
        # *rouvrir le même texte n'est pas un second travail*. Sans elle, le quota personnel
        # aurait compté les hésitations du samedi soir.
        await self.reservations.reserve(
            church_id=church_id,
            author_id=actor_account_id,
            pericope_key=_cle_provisoire(raw_input),
            at=maintenant,
        )
        dto = await self._rejouer(record, chosen_by="moteur", parole=_parole(lu))
        dto.relance = lu.question if lu else None

        # 🔴 **L'ouverture est le premier tour, pas un préambule.** Elle ne s'écrivait pas dans
        # le fil : la conversation ne commençait qu'au deuxième tour, et l'écran affichait la
        # phrase d'ouverture par un **repli** — qui disparaissait dès qu'une ligne existait.
        # Le pasteur voyait donc sa première phrase s'effacer en écrivant la deuxième.
        await self._garder_le_fil(record.id, raw_input, dto)
        return dto

    async def _lire_le_vestibule(
        self, *, church_id, author_id, texte: str, at, sujet_en_cours: str | None = None
    ):
        """Ce que le modèle comprend d'un tour **avant** qu'une préparation existe.

        ⚠️ **Sans modèle, le vestibule s'efface — il ne bloque pas.** Un modèle injoignable,
        un plafond atteint, aucune clé branchée : il n'y a alors personne pour conduire la
        conversation, et refuser d'ouvrir laisserait le pasteur devant une porte close avec
        rien pour la franchir. On rend `None`, l'appelant pose `confirme`, et le produit se
        comporte comme avant le 22/08.

        C'est la dégradation que la spec prévoit — *le pasteur perd de la finesse, jamais
        l'accès* — et c'est la même règle que partout ailleurs ici : les adaptateurs `Null*`
        sont des états de production, pas des modes dégradés."""
        usage = await self.reservations.usage(church_id, author_id, at)
        if usage.assistance_exhausted and not await self.tier.is_unlimited(author_id):
            return None
        return await self.resolver.vestibule(texte, sujet_en_cours=sujet_en_cours)

    # -- lecture ---------------------------------------------------------------

    async def list_mine(
        self, *, actor_account_id: UUID, limit: int = 50, rangees: bool = False
    ) -> list[PreparationRecord]:
        """Le fil d'accueil — **sans rejouer le moteur**.

        Rejouer est le mode normal de lecture d'une préparation ; le faire pour
        vingt lignes à l'ouverture de l'application coûterait vingt pipelines.
        La liste se contente donc de ce que l'enregistrement sait de lui-même,
        y compris la projection du dernier tour.

        Ce que le fil ne peut pas dire, et c'est assumé : la **phrase** du
        dernier tour. Elle vient du rejeu, et l'écran l'obtiendra en ouvrant la
        préparation. Le fil dit où l'on en est, pas ce qu'Urim a dit.
        """
        return await self.studies.list_for_author(
            actor_account_id, limit=limit, rangees=rangees
        )

    #: Ce qu'un titre écrit à la main peut faire au plus long. Au-delà, ce n'est plus un
    #: titre : c'est la première phrase, et elle a déjà sa place dans le fil.
    TITRE_MAX = 120

    async def rename(
        self, *, actor_account_id: UUID, study_id: UUID, title: str | None
    ) -> PreparationRecord:
        """Nommer sa préparation — **ou reprendre le nom qu'elle avait toute seule**.

        L'écran affichait `raw_input` tant que rien n'était résolu, puis l'étiquette de la
        péricope. Les deux sont justes, et aucun des deux n'est choisi : trois préparations
        ouvertes sur Romains se ressemblent dans un historique.

        Un titre **vide efface le titre** au lieu d'en poser un blanc. C'est le seul moyen
        de revenir à l'affichage automatique sans deviner une formule magique, et ça évite
        qu'un champ effacé par mégarde laisse une ligne sans nom.
        """
        record = await self._charger(study_id)
        await self._ensure_owner_or_preacher(actor_account_id, record)

        propre = (title or "").strip()
        if len(propre) > self.TITRE_MAX:
            raise TitreIllisibleError(limite=self.TITRE_MAX)

        record.title = propre or None
        await self.studies.save(record)
        return record

    async def ranger(
        self, *, actor_account_id: UUID, study_id: UUID, rangee: bool
    ) -> PreparationRecord:
        """Sortir une préparation du fil, ou l'y ramener.

        ⚠️ **Ce n'est pas `abandonnee`, et ce n'est pas une suppression.** « Abandonnée »
        est posé par « reformuler » : la saisie rouvre sans rien conserver, c'est un
        renoncement. Ranger est le contraire — on garde, on ne veut simplement plus le voir
        en tête de liste. Rien n'est effacé, et le chemin du retour existe.

        Une préparation close reste rangeable : « j'ai prêché celle-ci » n'oblige pas à la
        garder sous les yeux six mois de plus.
        """
        record = await self._charger(study_id)
        await self._ensure_owner_or_preacher(actor_account_id, record)

        if record.status == "abandonnee":
            # Ranger ce qui a été abandonné écraserait la trace du renoncement, et le
            # ramener le ressusciterait sans son contenu. On refuse plutôt que d'inventer.
            raise RangementImpossibleError()

        if rangee:
            record.status = "rangee"
        elif record.status == "rangee":
            # Le retour rend l'état d'avant, et rien de plus : `closed_at` dit déjà si
            # elle avait été prêchée.
            record.status = "close" if record.closed_at else "ouverte"

        await self.studies.save(record)
        return record

    async def get(self, *, actor_account_id: UUID, study_id: UUID) -> StudyDTO:
        record = await self._charger(study_id)
        await self._ensure_owner_or_preacher(actor_account_id, record)
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
        await self._ensure_owner_or_preacher(actor_account_id, record)

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
        # Choisir ce qu'on avait écarté dit assez qu'on le reprend. Exiger un geste de
        # restauration d'abord serait demander une formalité pour une intention déjà claire.
        await self.studies.restore(
            study_id=study_id, stage_code=stage_code, option_code=option_code
        )
        await self.studies.save(record)
        return await self._rejouer(record, chosen_by="pasteur")

    # -- le tour de parole ------------------------------------------------------

    async def dire(
        self,
        *,
        actor_account_id: UUID,
        study_id: UUID,
        raw_input: str,
        idempotency_key: str | None = None,
    ) -> StudyDTO:
        """**Du texte libre en cours de préparation** — le trou 2 du contrat (§6).

        `raw_input` n'existait qu'à l'ouverture ; après, il n'y avait que `POST /decisions`
        avec un code d'option. Le tour 5 de la maquette montre pourtant le pasteur qui tape
        *« Quel plan je peux tenir sur ce texte ? »*, et c'est le geste le plus naturel une
        fois le texte sous les yeux.

        L'orchestration vit dans `conversation.conduire`, qui n'a besoin ni de base ni de
        rejeu : ce qui est ici, c'est ce qu'elle ne peut pas savoir — l'état affiché, le
        plafond d'assistance, et l'exécution du geste qu'elle conclut.

        ⚠️ **Rien n'est écrit tant qu'aucun geste n'est conclu.** Le rejeu est en lecture pure ;
        un tour aiguillé rend l'état inchangé, avec la phrase du répondeur. C'est la même règle
        que le refus : *une intention ne déclenche jamais un acte irréversible, elle propose*.

        Les deux seuls gestes exécutés viennent de la liaison, qui est **exacte** — décider et
        écarter, sur l'étage qui rend la main. Ils repassent par `decide` et `dismiss` plutôt
        que d'écrire d'ici : le clic et la phrase doivent aboutir au même endroit, sans quoi
        deux chemins d'écriture divergeraient au premier étage ajouté."""
        record = await self._charger(study_id)
        await self._ensure_owner_or_preacher(actor_account_id, record)

        # ⚠️ **Deja entendue.** Un client sans reseau met ses gestes en file ; au
        # retour, il renvoie. Decider et ecarter posent un etat et supportent le
        # rejeu, mais une parole ferait un second passage du repondeur — donc un
        # appel de modele en plus, et peut-etre une autre phrase que celle que le
        # pasteur a deja lue. On rend l'etat, qui est ce qu'il attendait.
        if idempotency_key is not None and idempotency_key == record.last_turn_key:
            return await self._rejouer(record, persist=False)

        # ── Tant que le consentement n'est pas donné, **c'est le vestibule qui conduit** ──
        #
        # 🔴 **Le trou du 22/08, vu sur un téléphone.** Le vestibule était branché sur
        # l'ouverture et sur rien d'autre : chaque phrase suivante repartait vers l'aiguilleur,
        # qui ne connaît ni la maturité ni le sujet. La préparation restait donc en `absent`
        # **pour toujours**, et le pasteur ne pouvait pas en sortir en parlant — « Jean 14:15 »
        # s'entendait répondre qu'aucun texte n'était ouvert.
        #
        # Ici, un seul appel, un seul énoncé, et la maturité avance vraiment. L'aiguilleur et
        # ses sept répondeurs ne servent qu'**après** le consentement, là où il y a un travail
        # dont on peut parler.
        if record.maturity != Maturite.CONFIRME:
            lu = await self._lire_le_vestibule(
                church_id=record.church_id,
                author_id=record.author_id,
                texte=raw_input,
                at=self.clock(),
                sujet_en_cours=record.carried_subject,
            )
            if lu is not None:
                record.maturity = lu.maturite
                # Le sujet ne s'efface pas sur un tour qui n'en porte pas : « bonjour » après
                # « le pardon » ne doit pas faire perdre le pardon.
                record.carried_subject = lu.sujet or record.carried_subject
                await self.studies.save(record)

            if idempotency_key is not None:
                await self._marquer_parole(study_id, idempotency_key)
            dto = await self._rejouer(record, persist=False, parole=_parole(lu))
            dto.relance = lu.question if lu else None

            # 🔴 **Le chemin du vestibule repartait sans rien garder**, et c'était le pire
            # endroit : les tours d'avant le consentement sont précisément ceux où le pasteur
            # cherche son sujet. Mesuré en direct le 24/08 — deux tours de parole, un fil
            # resté vide.
            await self._garder_le_fil(study_id, raw_input, dto)
            return dto

        dto = await self._rejouer(record, persist=False)
        usage = await self.reservations.usage(
            record.church_id, record.author_id, self.clock()
        )
        tour = await conduire(
            raw_input,
            self._ecran(dto),
            await self._assistance(record, usage),
            # ⚠️ **La notation du pasteur est lue ici, parce que c'est ici qu'est le corpus.**
            # `Hb 2v29` demande les 357 formes de noms de livre pour devenir « Hébreux 2:29 »,
            # puis le compte des versets pour savoir qu'il n'y en a pas 29. La liaison est pure
            # et n'a ni l'un ni l'autre : elle reçoit une lecture déjà faite et déjà contrôlée.
            lire_la_notation(raw_input, self.index),
        )

        # L'étage qui a rendu la main — le même que celui du tour, et celui que le client
        # renverrait s'il avait touché l'option au lieu de l'écrire.
        etage = dto.trace[-1][0] if dto.trace else ""
        if tour.decision is not None:
            resultat = await self.decide(
                actor_account_id=actor_account_id,
                study_id=study_id,
                stage_code=etage,
                option_code=tour.decision,
            )
        elif tour.refus is not None:
            resultat = await self.dismiss(
                actor_account_id=actor_account_id,
                study_id=study_id,
                stage_code=etage,
                option_code=tour.refus,
            )
        elif tour.intention == "changer_de_sujet" and _travail_commence(record):
            # **§4 — un nouveau sujet suspend l'état, il ne s'y fond pas.**
            #
            # 🔴 Le défaut observé : une fois un sujet en mémoire, tout ce qui arrive est lu à
            # travers lui. Le pasteur envoie Luc 15 alors qu'il travaillait sur le pardon, et
            # l'agent lui répond sur le pardon — il répond avec ce qu'il a gardé, pas à la
            # préoccupation du tour.
            #
            # On ne tranche pas à sa place : on **renvoie la préparation au vestibule**, qui
            # posera la question. Aucun travail n'est perdu tant qu'il n'a pas choisi.
            record.maturity = Maturite.NOMME
            record.carried_subject = raw_input.strip()
            await self.studies.save(record)
            resultat = await self._rejouer(record, persist=False)
        else:
            dto.reponse = tour.reponse
            resultat = dto

        # ⚠️ **La cle se pose apres, jamais avant.** La reclamer d'abord serait
        # plus simple et perdrait la parole : un geste qui echoue laisserait sa
        # cle brulee, et le renvoi serait ignore. Ici, seule une parole
        # reellement traitee ferme la porte derriere elle.
        # ── Le fil se garde ────────────────────────────────────────────────────────────
        #
        # 🔴 Il disparaissait à chaque sortie d'écran. Le client affichait tout ce qu'il avait ;
        # c'est le serveur qui ne gardait rien — la saisie d'ouverture, et c'est tout. Un
        # pasteur qui s'arrêtait le mardi et reprenait le vendredi retrouvait une conversation
        # vide devant un moteur qui, lui, se souvenait de tout.
        #
        # ⚠️ **On garde ce qui s'est dit, pas ce que le moteur a calculé.** Les pesées, les
        # couples, les options se rejouent ; les paroles, non — elles viennent d'un modèle à
        # un instant, et ne reviendront pas les mêmes.
        await self._garder_le_fil(study_id, raw_input, resultat)

        if idempotency_key is not None:
            await self._marquer_parole(study_id, idempotency_key)

        return resultat

    async def _garder_le_fil(
        self, study_id: UUID, dit: str, resultat: StudyDTO
    ) -> None:
        """La parole du pasteur, puis ce que l'atelier lui a répondu.

        ⚠️ **L'adresse se lit, elle ne se devine pas.** Si le pasteur désigne un point — « le
        deuxième », « point 3 », ou les mots du point — sa phrase se range dessous. Sinon elle
        reste une parole du fil, sans adresse, et c'est un état normal : *ça peut être point ou
        pas, il peut mettre une pause et revenir changer*.

        Ranger sous le point qu'il regarde serait le troisième chemin, et c'est le seul où la
        machine décide — elle se tromperait, et il ne saurait pas pourquoi."""
        maintenant = self.clock()

        elements = await self.studies.list_elements(study_id)
        points = tuple(
            (e.element_code, e.ordinal, e.body or "")
            for e in elements
            if (e.body or "").strip()
        )
        vise = viser_un_point(dit, points)

        await self.studies.append_thread(
            ParoleDuFil(
                id=uuid4(),
                speaker="pasteur",
                body=dit.strip(),
                element_code=vise[0] if vise else None,
                element_ordinal=vise[1] if vise else None,
                written_at=maintenant,
            ),
            study_id=study_id,
        )
        repondu = (resultat.reponse or resultat.rationale or "").strip()
        if repondu:
            await self.studies.append_thread(
                ParoleDuFil(
                    id=uuid4(), speaker="urim", body=repondu, written_at=maintenant
                ),
                study_id=study_id,
            )

    async def _marquer_parole(self, study_id: UUID, cle: str) -> None:
        """Relit puis ecrit : le geste a pu remplacer l'enregistrement en cours."""
        record = await self.studies.get(study_id)
        if record is None:
            return
        record.last_turn_key = cle
        await self.studies.save(record)

    def _ecran(self, dto: StudyDTO) -> Ecran:
        """Ce que le pasteur voit, **dans l'ordre où il le voit**.

        ⚠️ L'ordre est celui du tour et non celui du moteur : le tour groupe les unités pesées
        par ce qu'elles font du sujet. Le rang lu par la liaison se compte sur cette liste-là,
        sinon « le deuxième » désignerait une autre option que celle touchée.

        Les écartées sont retirées, comme dans les pastilles : elles restent dans la vue,
        reléguées, mais elles ne sont plus des cibles au rang."""
        vivantes = sorted(
            (o for o in dto.options if not o[4]), key=lambda o: rang_a_l_ecran(o[5])
        )
        return Ecran(
            codes=tuple(o[0] for o in vivantes),
            # Le libellé d'abord, le code ensuite : une option venue du sens porte la référence
            # dans les deux, un locus dans aucun des deux. Ce qui n'en est pas une garde sa
            # place avec une référence vide — un livre vide n'apparaît dans aucune saisie.
            references=tuple(
                self._reference_depuis_libelle(o[1])
                or self._reference_depuis_libelle(o[0])
                or Reference("")
                for o in vivantes
            ),
            libelles=tuple(o[1] for o in vivantes),
            ancre=dto.resolved_label,
            attend=dto.outcome == str(Outcome.AWAIT),
        )

    async def _assistance(self, record: PreparationRecord, usage) -> AssistedResolver:
        """Le modèle, ou le silence — **une seule règle, deux appelants**.

        ⚠️ **Le quota éteint l'assistance, jamais Urim.**

        Épuisé, on remplace le modèle par le silence — et le reste continue : le corpus, les
        45 557 pesées, la concordance, le contrôle de référence, le bornage. C'est le
        comportement `DEGRADE`, et les adaptateurs `Null*` sont des **états de production**
        (S12/S37), pas des modes dégradés. Un mur sec serait la seule chose que ce moteur ne
        sait pas faire.

        La sortie est consultée avant de couper : illimité, on ne compte pas."""
        if usage.assistance_exhausted and not await self.tier.is_unlimited(
            record.author_id
        ):
            return NullVerseResolver()
        return self.resolver

    # -- refus -----------------------------------------------------------------

    async def dismiss(
        self,
        *,
        actor_account_id: UUID,
        study_id: UUID,
        stage_code: str,
        option_code: str,
    ) -> StudyDTO:
        """Écarter une option — **et la garder dans la liste, marquée**.

        Le moteur rejoue à chaque lecture : sans mémoire du refus, il repropose au tour suivant
        exactement ce que le pasteur vient de repousser. Dans un formulaire ça ne se voyait pas ;
        dans une conversation de onze tours, c'est la chose la plus irritante qu'un logiciel
        puisse faire.

        ⚠️ **Écarter n'est pas décider, et surtout n'efface pas.** L'option revient reléguée en
        fin de liste avec sa marque — même règle que les couples refusés qui voyagent avec les
        faisables : *les cacher laisserait croire qu'on n'y a pas pensé*. Et le pasteur qui
        change d'avis doit pouvoir la retrouver, sans quoi son geste serait irréversible par
        accident."""
        record = await self._charger(study_id)
        await self._ensure_owner_or_preacher(actor_account_id, record)

        # **RT1 — un sujet décliné ne revient pas.** Écarter la proposition du vestibule ne
        # dit pas « pas maintenant », ça dit « pas celui-là » : le re-servir trois tours plus
        # loin ferait de la conversation un harcèlement poli. Un autre candidat peut mûrir ;
        # celui-ci est clos.
        if stage_code == "vestibule" and record.carried_subject:
            record.declined_subjects = (
                *record.declined_subjects, record.carried_subject,
            )
            record.carried_subject = None
            record.maturity = Maturite.ABSENT
            await self.studies.save(record)

        await self.studies.dismiss(
            study_id=study_id,
            stage_code=stage_code,
            option_code=option_code,
            at=self.clock(),
        )
        # `persist=False` : écarter ne fait avancer aucun étage. Rejouer en écrivant
        # enregistrerait une tentative de résolution que personne n'a faite.
        return await self._rejouer(record, persist=False)

    def _appliquer(self, record: PreparationRecord, stage: str, option: str) -> None:
        if stage == "vestibule":
            # 🔴 **Le seul endroit du dépôt où `confirme` s'écrit.**
            #
            # Ni le modèle, ni un défaut, ni une migration : un tour du pasteur, sur une
            # option qu'un étage a offerte. C'est ce qui rend l'invariant I23 mécanique — une
            # saisie qui souffle « ouvre une préparation » ne trouve aucun chemin jusqu'ici,
            # parce que la sortie vient d'un étage franchi, jamais d'une chaîne de caractères.
            if option == CONSENTIR:
                # **`carried_subject` n'est pas effacé, et c'est le mécanisme** : c'est lui
                # que `_rejouer` fait descendre. « le pardon » entre dans le moteur, pas
                # « je voudrais travailler un peu sur le pardon aujourd'hui ».
                record.maturity = Maturite.CONFIRME
                return

            if option == LIRE_SEULEMENT:
                # **Lire n'engage rien, et c'est le défaut du produit.** Le moteur descend
                # quand même — il faut bien résoudre le texte pour l'ouvrir — mais la
                # préparation reste ce qu'elle est : une lecture. Le pasteur pourra préparer
                # ensuite, et rien de ce qui suit n'aura été fait dans son dos.
                record.maturity = Maturite.CONFIRME
                if record.carried_subject:
                    record.raw_input = record.carried_subject
                return

            if option == CHANGER:
                # Le travail en cours n'est pas détruit : il reste dans le fil du pasteur,
                # avec ses décisions. Celui-ci **repart de zéro** sur la nouvelle phrase.
                # La nouvelle charge **reste** portée : c'est elle qui descend maintenant.
                # L'effacer ferait repartir le moteur sur la phrase d'ouverture, c'est-à-dire
                # sur le sujet que le pasteur vient précisément d'abandonner.
                self._perimer(record, _TOUT_L_AVAL)
                record.entry_mode = None
                record.resolved_ref = None
                record.maturity = Maturite.CONFIRME
                return

            if option == RATTACHER:
                # **Sa phrase ne se perd pas** — elle reste dans le fil, comme tout ce qu'il a
                # écrit. Ce qui est refusé, c'est qu'elle déplace le travail sans qu'il l'ait
                # demandé.
                record.carried_subject = None
                record.maturity = Maturite.CONFIRME
                return

            raise OptionInconnueError(f"« {option} » n'est pas une issue du vestibule.")

        if stage == "route_entry":
            if option not in {m.value for m in EntryMode}:
                raise OptionInconnueError(f"« {option} » n'est pas un mode d'entrée.")
            self._perimer(record, _TOUT_L_AVAL)
            record.entry_mode = option
            record.resolved_ref = None
            return

        if stage == "resolve_passage":
            if option == PAS_UNE_CITATION:
                # ⚠️ **La sortie du chemin citation.** « L'amour du prochain » est un thème
                # écrit en mots bibliques : l'étage 0 y voit un recouvrement fort, l'étage 1
                # aligne cinq versets, et le pasteur n'avait aucun moyen de dire qu'il
                # n'avait jamais cité. Le mode est corrigé et le pipeline rejoué depuis le
                # début — c'est une correction d'entrée, pas une résolution de passage, d'où
                # l'écriture sur `entry_mode` et non sur `resolved_ref`.
                self._perimer(record, _TOUT_L_AVAL)
                record.entry_mode = EntryMode.CONVICTION.value
                record.resolved_ref = None
                return
            ref = self._reference_depuis_libelle(option)
            if ref is None:
                raise OptionInconnueError(f"« {option} » ne désigne aucun passage connu.")
            self._perimer(record, _TOUT_L_AVAL)
            record.resolved_ref = _serialiser(ref)
            return

        if stage == "bound_pericope":
            if option in (TEL_QUEL, EN_UN_SEUL):
                # Le pasteur garde ses bornes. `pericope_id` retombe à None, et **tout ce
                # qui est curé devient illisible** pour les étages avals — pesées, mises
                # en garde, faisabilité. S22 est mécanique, pas déclaratif.
                #
                # ⚠️ **Deux gestes distincts, une seule écriture — et c'est délibéré.**
                # `tel_quel` dit « mes bornes » contre l'unité qui les débordait ; `en_un_seul`
                # dit « toutes les unités ensemble ». Mais aucune des N unités ne peut porter
                # un sermon sur l'ensemble : en retenir une pour « en avoir une » attacherait
                # au tout la relecture d'un tiers du texte, sans que rien ne le signale — le
                # défaut exact qu'`explorer` refuse déjà quand plusieurs unités couvrent la
                # demande. Le drapeau reste vrai au sens propre : la demande du pasteur
                # l'emporte sur ce que la curation proposait.
                #
                # **Pas de troisième colonne**, parce que les trois cas se relisent dans le
                # corpus à tout instant — 0 unité sur le passage : le corpus n'avait rien ;
                # 1 : le pasteur a refusé qu'elle le déborde ; N : il les a réunies. C'est
                # exactement le mécanisme que `propose_theme` documente et pour la même
                # raison : une colonne dirait la même chose et pourrait la contredire.
                # 🔴 Mécanique, elle ne l'était pas : le couple et le thème tirés de l'unité
                # abandonnée survivaient au geste. Ils se périment ici — l'axe, lui, reste :
                # c'est un angle doctrinal, il ne dépend pas des bornes, et sur le chemin
                # intention c'est **le pasteur** qui l'a nommé avant même de voir un texte.
                self._perimer(record, _SOUS_LES_BORNES)
                record.pericope_id = None
                record.bounds_overridden = True
                return
            try:
                unite = UUID(option)
            except ValueError as exc:
                raise OptionInconnueError(
                    f"« {option} » n'est pas une unité littéraire connue."
                ) from exc
            self._perimer(record, _SOUS_LES_BORNES)
            record.pericope_id = unite
            record.bounds_overridden = False
            return

        if stage == "shape_homiletic":
            if ":" not in option:
                raise OptionInconnueError(f"« {option} » n'est pas un couple plan x matière.")
            plan, matiere = option.split(":", 1)
            # 🔴 **Le couple n'était pas vérifié, et l'étage ne le vérifiait plus non plus.**
            #
            # `shape_homiletic.applies()` exige `subject_matter is None` ; en écrivant les deux
            # champs d'un coup, cette ligne empêchait l'étage de se ré-exécuter — donc sa
            # validation et son refus motivé n'étaient plus jamais atteints. `abracadabra:
            # sur-mesure` traversait tout et ressortait dans le thème rendu au pasteur :
            # « pneumatologie, en abracadabra sur-mesure ».
            #
            # La vérification se fait donc ici, comme pour les unités et les références — et
            # avec le **motif de la curation** quand le couple existe mais ne tient pas : il
            # apprend quelque chose du texte, là où « option inconnue » ne dit rien (S19).
            couples = self.index.couples.get(record.pericope_id, ())
            choisi = next(
                (c for c in couples
                 if c.plan_source == plan and c.subject_matter == matiere),
                None,
            )
            if choisi is None:
                raise OptionInconnueError(
                    f"« {option} » n'a pas été relu sur cette unité littéraire."
                )
            if not choisi.feasible:
                raise OptionInconnueError(
                    choisi.refusal_reason
                    or f"« {option} » n'est pas faisable sur cette unité littéraire."
                )
            self._perimer(record, _LE_THEME)
            record.plan_source, record.subject_matter = plan, matiere
            return

        if stage == "weigh_conviction":
            # Deux décisions distinctes sortent du même étage — d'où le préfixe explicite.
            # Le déduire de la forme (« ça ressemble à un UUID donc c'est un texte ») aurait
            # marché et se serait cassé au premier axe nommé comme un identifiant.
            if option.startswith("axe:"):
                axe = self._verifier_axe(option.removeprefix("axe:"))
                self._perimer(record, _LE_THEME)
                record.axis_code = axe
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
                # ⚠️ L'axe **survit** ici, et c'est le chemin inversé qui l'exige : sur une
                # intention, le pasteur a nommé son angle **avant** de voir un texte. Le
                # périmer avec le reste lui reprendrait la seule chose qu'il ait dite.
                self._perimer(record, _SOUS_LE_TEXTE)
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
                self._perimer(record, _SOUS_LE_TEXTE)
                record.resolved_ref = _serialiser(reference)
                return
            raise OptionInconnueError(f"« {option} » n'est pas une option de cet étage.")

        if stage == "bear_axes":
            axe = self._verifier_axe(option)
            self._perimer(record, _LE_THEME)
            record.axis_code = axe
            return

        if stage == "propose_theme":
            record.theme = option
            return

        raise OptionInconnueError(f"L'étage « {stage} » n'attend aucune décision.")

    def _perimer(self, record: PreparationRecord, champs: tuple[str, ...]) -> None:
        """Ce qu'une décision amont **périme** — et pourquoi le moteur ne peut pas le faire.

        🔴 *« Le rejeu est le choix structurant : on stocke les décisions, et on refait tourner
        les huit étages. »* La phrase était vraie de la trace et fausse de tout le reste. Les
        bornes, l'axe, le couple et le thème sont stockés comme des **résultats**, et chaque
        étage qui les produit se garde de tourner deux fois (`applies`). Une décision amont ne
        remontait donc jamais l'aval — elle le laissait périmé :

            il change l'axe      -> le theme dit encore l'ancien
            il change le couple  -> le theme dit encore l'ancienne mise en forme
            il force ses bornes  -> l'axe, le couple ET le theme survivent a l'unite
                                    que le produit vient de declarer illisible (S22)

        Le dernier cas est le plus grave : S22 promet que la liberté accordée *« se propage
        d'elle-même, sans qu'aucun étage n'ait à connaître la règle »*. Elle ne se propageait
        pas du tout. C'est ici qu'elle se propage, une fois, pour tous les étages.

        ⚠️ **Le thème réécrit par le pasteur ne se périme jamais.** *Une proposition, jamais un
        titre — le titre, c'est votre voix.* On efface le thème seulement s'il est encore mot
        pour mot ce que le gabarit rendrait : le gabarit étant déterministe, l'égalité dit que
        personne n'y a touché."""
        # ⚠️ **La question se pose AVANT d'effacer quoi que ce soit.** Posée dans la boucle,
        # elle comparait le thème à un gabarit dont on venait de vider le plan et la matière :
        # « christologie » au lieu de « christologie, en expositif doctrinal », donc jamais
        # égal, donc un thème du moteur passait pour une phrase du pasteur et survivait.
        du_moteur = record.theme == theme_propose(
            record.axis_code, record.plan_source, record.subject_matter
        )
        for champ in champs:
            if champ == "theme" and not du_moteur:
                continue  # sa phrase à lui — on n'y touche pas
            setattr(record, champ, False if champ == "bounds_overridden" else None)

    def _verifier_axe(self, code: str) -> str:
        """L'axe retenu est-il un locus **que ce corpus connaît** ?

        🔴 Deux étages écrivent `axis_code` — `weigh_conviction` par `axe:<locus>` et
        `bear_axes` par le code nu — et **aucun des deux ne vérifiait**. `abracadabra` devenait
        l'axe doctrinal de la préparation, puis le thème rendu au pasteur. C'est la même famille
        de trou que le couple plan x matière, à quinze lignes d'écart : une décision appliquée
        sans demander au corpus si elle existe.

        ⚠️ **La garde porte sur les dix loci, pas sur ce que l'unité porte.** Un texte peut être
        prêché sur un axe qu'il *soutient* sans en faire son sujet — c'est même la seule porte
        de sortie du pasteur dont l'angle n'est pas celui que le corpus a jugé dominant. La
        fermer ici déciderait à sa place, et cet étage existe pour ne pas le faire."""
        connus = {axe.code for axe in self.index.axes}
        if code not in connus:
            raise OptionInconnueError(
                f"« {code} » n'est pas un des axes doctrinaux de ce corpus."
            )
        return code

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
        await self._ensure_owner_or_preacher(actor_account_id, record)
        # Le **contenu** reste libre — le squelette propose un ordre, il n'impose aucun texte,
        # et un élément vide est un état normal. Ce qui est fermé, c'est le **code de section**.
        #
        # ⚠️ **On canonise avant de refuser.** `Divisions`, `POINT`, `sous point`, `Intro`
        # retombent sur leur code : sans cela, fermer la liste ne ferait que déplacer le
        # problème — au lieu d'un verrou contourné par une majuscule, un plan refusé pour la
        # même majuscule.
        retenus: list[ElementRecord] = []
        for element in elements:
            code = code_canonique(element.element_code)
            if code is None:
                raise ElementInconnuError(
                    f"« {element.element_code} » n'est pas une section connue. "
                    f"Sections acceptées : {', '.join(CODES)}.",
                    details={"element_code": element.element_code, "connus": list(CODES)},
                )
            retenus.append(ElementRecord(code, element.ordinal, element.body))
        await self.studies.set_elements(study_id, retenus)
        return await self._rejouer(record, persist=False)

    async def promouvoir(
        self,
        *,
        actor_account_id: UUID,
        study_id: UUID,
        entry_id: UUID,
        element_code: str | None = None,
        ordinal: int | None = None,
    ) -> StudyDTO:
        """Faire d'une note **un point du plan** — le seul chemin du fil vers le document.

        🔴 **C'est ici que le verrou se tient.** Tout ce qui s'écrit dans le fil est gardé,
        rangé, relisible — et n'atteint aucun fichier. Le livrable n'imprime que
        `preparation_element`. Une note ne devient imprimable qu'en passant par ce geste, que
        le pasteur seul déclenche.

        ⚠️ **On ajoute, on ne remplace pas.** Sa note est le plus souvent une remarque *sur* le
        point — *« le deuxième, il faut parler de la loi »* — pas le texte du point. L'écraser
        lui ferait perdre ce qu'il avait écrit ; l'ajouter lui laisse la main, et il retaille.
        C'est la règle de l'articulation, et pour la même raison.

        ⚠️ **Une fois, et une seule.** `promote_thread` refuse la seconde reprise : deux points
        identiques dans un plan, et le pasteur ne saurait plus lequel est le sien."""
        record = await self._charger(study_id)
        await self._ensure_owner_or_preacher(actor_account_id, record)

        parole = next(
            (
                p
                for p in await self.studies.list_thread(study_id)
                if p.id == entry_id and p.est_du_pasteur and not p.promue
            ),
            None,
        )
        if parole is None:
            raise OptionInconnueError(
                "Cette note n'existe pas, ou vous l'avez déjà reprise."
            )

        code = element_code or parole.element_code
        rang = ordinal if ordinal is not None else parole.element_ordinal
        if code is None:
            # Une note sans adresse ne sait pas où aller, et la deviner serait décider à sa
            # place quel point elle complète. On le dit, il désigne, il recommence.
            raise OptionInconnueError(
                "Cette note n'est posée sous aucun point. Dites lequel elle complète — "
                "« le deuxième », « point 3 », ou les mots du point."
            )

        elements = list(await self.studies.list_elements(study_id))
        vise = next(
            (
                e
                for e in elements
                if e.element_code == code and (rang is None or e.ordinal == rang)
            ),
            None,
        )
        if vise is None:
            # Le point a disparu depuis qu'il a écrit — il l'a effacé, ou renommé. La note
            # ouvre alors sa propre ligne plutôt que de se perdre.
            elements.append(ElementRecord(code, rang or len(elements), parole.body))
        else:
            ancien = (vise.body or "").rstrip()
            # Deux sauts de ligne : sa note est une phrase de plus sous son point, pas la
            # suite de celle qu'il avait écrite.
            vise.body = (
                f"{ancien}\n\n{parole.body}" if ancien else parole.body
            )

        await self.set_elements(
            actor_account_id=actor_account_id, study_id=study_id, elements=elements
        )
        await self.studies.promote_thread(entry_id, at=self.clock())
        return await self._rejouer(record, persist=False)

    async def articuler(
        self, *, actor_account_id: UUID, study_id: UUID, element_code: str, ordinal: int
    ) -> PlanSuggestion | None:
        """**La seule prose qu'Urim produise — demandée, point par point, et jamais imprimée.**

        Ce qui la rend acceptable n'est pas une promesse, c'est le chemin des données : le
        livrable n'imprime que `preparation_element.body`. Cette proposition vit dans sa
        **propre table** ; elle n'atteint un document que si le pasteur la reprend dans son
        plan, c'est-à-dire s'il l'a lue et adoptée. C'est le patron du dépôt — *l'IA propose,
        l'homme dispose* — et celui de Sermon : *rien de non approuvé n'atteint le membre*.

        ⚠️ **Le quatrième mur n'est pas franchi.** `FORBIDDEN_IN_MODEL_PROMPT` interdit de
        donner le plan au modèle **dans la capture**, parce que le Retour existe pour mesurer
        l'écart entre le préparé et le prêché : un modèle qui aurait vu le plan fabriquerait la
        conformité. Ici on est dans l'atelier, avant le dimanche, et c'est le pasteur qui
        demande. Le Retour, lui, ne lira jamais cette table.

        ⚠️ **Ça consomme.** C'est un appel de modèle comme les autres : `mark_assisted` est
        posé. Et la garde du plafond s'applique — au plafond, la réponse est `None`, et le
        pasteur écrit son point comme il l'a toujours fait."""
        record = await self._charger(study_id)
        await self._ensure_owner_or_preacher(actor_account_id, record)

        elements = await self.studies.list_elements(study_id)
        point = next(
            (e for e in elements if e.element_code == element_code and e.ordinal == ordinal),
            None,
        )
        if point is None or not (point.body or "").strip():
            # On n'articule pas un point qui n'existe pas : ce serait l'écrire.
            return None

        empreinte = hashlib.sha256(
            normalize(point.body or "").encode()
        ).hexdigest()[:32]
        garde = await self.studies.get_plan_suggestion(
            study_id, element_code, ordinal, empreinte
        )
        if garde is not None:
            # Déjà demandé pour ce point : on rend le mémo. Redemander referait payer une
            # question qui a déjà sa réponse.
            return garde

        maintenant = self.clock()
        usage = await self.reservations.usage(
            record.church_id, record.author_id, maintenant
        )
        if usage.assistance_exhausted and not await self.tier.is_unlimited(
            record.author_id
        ):
            return None

        resolu = _deserialiser(record.resolved_ref) or self._passage_de_l_unite(record)
        servis, _variantes = self._texte_servi(
            StudyState(
                session_id=record.id,
                church_id=record.church_id,
                author_id=record.author_id,
                corpus_snapshot=record.corpus_snapshot or self.index.snapshot,
                entry_mode=EntryMode(record.entry_mode) if record.entry_mode else None,
                # 🔴 **La charge nettoyée descend ; la phrase du pasteur reste la sienne.**
            #
            # J'avais d'abord réécrit `raw_input` au consentement — et ça ne persistait pas :
            # la colonne n'est écrite qu'à la création, jamais au `save`. Le moteur travaillait
            # donc sur « Je vais prêcher sur la vie d'Élie » quand j'annonçais « la vie d'Élie ».
            #
            # Ici c'est mieux que corrigé, c'est mieux placé : ce que le pasteur a écrit reste
            # en base — c'est lui qui **titre** sa préparation dans le fil — et seul l'état du
            # moteur porte la charge extraite.
            raw_input=record.carried_subject or record.raw_input,
                resolved=resolu,
                bounds=self._bornes(record),
            )
        )
        suivant = next(
            (
                e.body or ""
                for e in sorted(elements, key=lambda e: (e.element_code, e.ordinal))
                if e.element_code == element_code and e.ordinal > ordinal
            ),
            "",
        )
        # ⚠️ **Les textes que le point cite lui-même voyagent avec lui**, et ce n'est pas un
        # confort. Au premier appel réel, un point qui citait Hébreux 9 alors qu'on servait
        # Actes 1 a fait **compléter le modèle de mémoire** — « dans le lieu très saint »,
        # exact et hors du texte fourni, donc invérifiable pour le pasteur. Lui donner ce
        # qu'il cite supprime le besoin de combler.
        appuis = "\n".join(
            f"{lisible_reference(ref)} — {texte}"
            for ref, texte in self._servir_les_appuis(point.body or "")
        )
        propose = await self.resolver.articuler(
            point=point.body or "",
            reference=_afficher(resolu) or record.raw_input,
            texte=" ".join(v.text for v in servis),
            suivant=suivant,
            appuis=appuis,
        )
        if propose is None:
            return None

        await self.studies.save_plan_suggestion(
            study_id, element_code, ordinal, empreinte, propose, maintenant
        )
        await self.reservations.mark_assisted(
            church_id=record.church_id,
            author_id=record.author_id,
            pericope_key=(
                f"pericope:{record.pericope_id}"
                if record.pericope_id is not None
                else _cle_provisoire(record.raw_input)
            ),
            at=maintenant,
        )
        return propose

    def _servir_les_appuis(self, ligne: str) -> list[tuple[Reference, str]]:
        """Les textes cités **dans la ligne du point**, servis depuis le corpus.

        Une référence qui n'existe pas est simplement écartée : ici on nourrit une invite, et
        « Hébreux 2 compte 18 versets » n'a rien à y faire. C'est le livrable qui montre ce
        motif au pasteur, pas le modèle."""
        lecteur = IndexedCorpusReader(self.index)
        servis: list[tuple[Reference, str]] = []
        for reference in references_dans(ligne, self.index):
            if not lecteur.check_reference(reference).exists:
                continue
            livre = self.index.book_by_label[reference.book]
            debut = (reference.chapter or 1, reference.verse_start or 1)
            fin = (
                reference.chapter or 1,
                reference.verse_end or reference.verse_start or 999,
            )
            texte = " ".join(v.body for v in verses_between(self.index, livre, debut, fin))
            if texte:
                servis.append((reference, texte))
        return servis

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
        await self._ensure_owner_or_preacher(actor_account_id, record)

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
        self, *, actor_account_id: UUID, church_id: UUID | None = None, reference: str
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
            # Les collisions **des versets servis**, même règle que l'original : on montre ce
            # qui porte sur le texte affiché, jamais ce qui traîne ailleurs dans l'unité.
            collisions=tuple(
                CollisionSeen(
                    reference=v.reference, word=c.word, form=c.form,
                    witnesses=tuple(
                        WitnessRead(
                            code=t.code, label=t.label, text_family=t.text_family,
                            stance=t.stance, reading=t.reading, body=t.body,
                        )
                        for t in c.witnesses
                    ),
                )
                for v in servis
                for c in self.index.collisions.get(
                    (livre, *_chapitre_verset(v.reference)), ()
                )
            ) if livre is not None else (),
        )

    async def concordance(
        self, *, actor_account_id: UUID, church_id: UUID | None = None, lemme: str
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

    async def _suggestions(
        self,
        record: PreparationRecord,
        chemin: str,
        lisible: str,
        assiste: AssistedResolver,
        maintenant: datetime,
    ) -> tuple[
        tuple[AxisGloss, ...], tuple[str, ...], tuple[PassageSuggestion, ...], bool
    ]:
        """Ce que le modèle a offert — **relu s'il l'a déjà dit, redemandé sinon**.

        ⚠️ **C'est d'abord une affaire de déterminisme, et le coût vient en second.** Le rejeu
        prétend rendre ce que le pasteur a vu ; sans mémo il *recalcule*, et se trouve d'accord
        tant que `mistral-small-latest` ne bouge pas. Le jour où l'alias bouge, hier rejoue
        autrement pendant que la trace affirme le contraire.

        Le coût suit : ce bloc partait à **chaque** rejeu — chaque ouverture d'écran, chaque
        refus — pour rendre mot pour mot ce qui venait d'être rendu.

        L'empreinte couvre le chemin **et** la saisie : « citation » et « conviction » ne posent
        pas la même question, et un pasteur qui corrige son mode doit obtenir une autre réponse
        plutôt que celle d'avant.

        Le quatrième rendu dit si le modèle a **réellement** servi. C'est lui qui décide de la
        facturation : un tour servi depuis le mémo n'a rien coûté, et le compter serait faire
        payer une relecture."""
        empreinte = _empreinte_de_la_demande(chemin, lisible)
        memo = await self.studies.get_suggestions(record.id, empreinte)
        if memo is not None:
            return memo.axes, memo.flags, memo.passages, False

        # ⚠️ **Une panne n'est pas une réponse.** Toute défaillance du transport rend une liste
        # vide, exactement comme un modèle qui n'a rien à dire. Sans ce compteur, un 429 d'une
        # seconde écrirait un mémo vide que le rejeu servirait **pour toujours** — la
        # préparation resterait blanche longtemps après le rétablissement.
        echecs_avant = getattr(assiste, "echecs", 0)

        if chemin == "conviction":
            loci, drapeaux, proposes = await asyncio.gather(
                assiste.axes(lisible),
                assiste.lever(lisible),
                self._passages_verifies(lisible, assiste),
            )
        else:
            loci, drapeaux = (), ()
            proposes = await self._passages_verifies(lisible, assiste)

        # ⚠️ **Ce qu'on refuse de garder, c'est l'absence de question — pas une réponse vide.**
        #
        # J'avais d'abord conditionné l'écriture au fait que le résultat ne soit pas vide, pour
        # ne pas figer une ignorance. C'était le mauvais critère, et les tests l'ont montré : un
        # modèle interrogé qui ne trouve rien **a répondu**, et ne pas le garder le fait
        # redemander à chaque rejeu — le gaspillage même qu'on venait supprimer.
        #
        # Le bon critère est : le modèle a-t-il été consulté **et a-t-il pu répondre** ? Sans
        # clé, ou quota épuisé, `NullVerseResolver` n'a rien été demander ; et un appel qui
        # échoue n'a rien appris non plus.
        a_repondu = getattr(assiste, "echecs", 0) == echecs_avant
        if not isinstance(assiste, NullVerseResolver) and a_repondu:
            await self.studies.save_suggestions(
                record.id,
                SuggestionSnapshot(
                    input_hash=empreinte,
                    model=getattr(assiste, "_model", "inconnu"),
                    axes=tuple(loci),
                    flags=tuple(drapeaux),
                    passages=tuple(proposes),
                ),
                maintenant,
            )
        return tuple(loci), tuple(drapeaux), tuple(proposes), True

    async def _passages_verifies(
        self, saisie: str, resolveur: AssistedResolver
    ) -> tuple[PassageSuggestion, ...]:
        """Les passages proposés par le sens, **vérifiés un par un contre les 31 170 versets**.

        ⚠️ M9-1, appliqué ici sans exception : *l'IA nomme la référence, la Segond donne le
        texte*. Un modèle qui se trompe de bornes — Job 41 fait 34 versets chez lui, 25 en
        Segond — proposerait un passage dont le texte n'existe pas, et le pasteur ne le
        découvrirait qu'en l'ouvrant.

        Une proposition qui tombe à un seul passage est **abandonnée** : elle aurait l'autorité
        d'une résolution sans en avoir passé les vérifications, et c'est précisément le
        proof-texting qu'on refuse."""
        proposes = await resolveur.passages(saisie)
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
        self,
        record: PreparationRecord,
        *,
        persist: bool = True,
        chosen_by: str | None = None,
        parole: str | None = None,
    ) -> StudyDTO:
        maintenant = self.clock()
        usage = await self.reservations.usage(
            record.church_id, record.author_id, maintenant
        )
        assiste = await self._assistance(record, usage)
        #: Vrai dès qu'un des trois chemins a interrogé le résolveur. Un drapeau plutôt qu'une
        #: inspection de l'adaptateur : c'est l'appel qui coûte, et lui seul le sait.
        sollicite = False
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
            citation_version=record.citation_version,
            resolved=resolu,
            bounds=self._bornes(record),
            pericope_id=record.pericope_id,
            bounds_overridden=record.bounds_overridden,
            version_id=record.version_id,
            axis=record.axis_code,
            plan_source=record.plan_source,
            subject_matter=record.subject_matter,
            theme=record.theme,
            maturity=record.maturity,
            carried_subject=record.carried_subject,
            declined_subjects=record.declined_subjects,
            vestibule_reply=parole,
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
        # 🔴 **Rien ne descend avant le consentement — le repli de résolution non plus.**
        #
        # Mesuré le 25/08 : le pasteur ouvre sur « Jean 3:16 », le vestibule arrête le moteur
        # (c'est son travail, rien n'est résolu), le service voit « rien résolu » et déclenche
        # son repli — une requête corpus, puis **un appel de modèle**. L'IA trouve Jean 3:16,
        # le moteur est rejoué avec ce passage, et le vestibule voit alors un texte résolu :
        # il croit qu'un travail est en cours et propose de *changer de sujet ou de rattacher*.
        # Il parlait d'un travail qu'il venait lui-même de fabriquer, une ligne plus haut.
        #
        # Deux dégâts silencieux avec : un appel de modèle à chaque ouverture non consentie, et
        # une résolution enregistrée pour un passage que le pasteur n'avait pas accepté de
        # préparer.
        descendu = record.maturity == Maturite.CONFIRME

        provenance = chosen_by
        #: L'identifiant de la version où la citation a été reconnue — `None` tant qu'aucune
        #: ne l'a été, ce qui reste le cas courant.
        version_reconnue: UUID | None = None
        # ⚠️ **Le corpus avant le modèle.** L'index ne porte qu'une version ; une citation
        # tirée d'une autre traduction détenue n'y est pas, et le détecteur la lit alors comme
        # une intention. Cas mesuré : « l'amour ne perir jamais » est Darby mot pour mot, quand
        # Segond dit « la charité ». Aller la chercher coûte une requête ; la deviner coûterait
        # un appel de modèle, et rendrait moins sûr ce que le corpus sait déjà.
        if (
            persist
            and descendu
            and record.resolved_ref is None
            and run.state.resolved is None
        ):
            ailleurs = await self.ailleurs.retrouver(decouper(record.raw_input))
            if ailleurs is not None and ailleurs.score >= CITATION_AFFINITY:
                provenance = "moteur"
                # La version est **écrite avant le rejeu**, pas après : c'est elle que l'étage
                # d'entrée lit pour dire ce qu'il a fait. Écrite après, le premier motif aurait
                # differé de tous les suivants.
                record.citation_version = ailleurs.version
                version_reconnue = ailleurs.version_id
                run = moteur.run(
                    etat.with_(
                        resolved=ailleurs.reference, citation_version=ailleurs.version
                    )
                )

        if (
            persist
            and descendu
            and record.resolved_ref is None
            and run.state.resolved is None
        ):
            sollicite = True
            trouve = await assiste.resolve(_lisible(record.raw_input))
            if trouve is not None and IndexedCorpusReader(self.index).check_reference(
                trouve
            ).exists:
                if _a_etabli_un_fait(run):
                    # 🔴 **Elle propose, elle ne résout pas.** Écraser un fait par une
                    # correction plausible est ce que l'étage 0 s'interdit nommément : *le
                    # calcul propose, la personne dispose*. Le motif garde son fait, l'étage
                    # rend la main avec la trouvaille en option, et rien n'est enregistré au
                    # nom d'un pasteur qui n'a rien choisi.
                    run = moteur.run(etat.with_(suggested_reference=trouve))
                else:
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
            loci, drapeaux, proposes, appele = await self._suggestions(
                record, "conviction", lisible, assiste, maintenant
            )
            sollicite = sollicite or appele
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
            _, _, proposes, appele = await self._suggestions(
                record, "impasse", _lisible(record.raw_input), assiste, maintenant
            )
            sollicite = sollicite or appele
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

            # Ou le moteur s'est arrete, et pourquoi il a rendu la main. Ecrit
            # ici parce que c'est le seul endroit qui le sait sans rejouer —
            # le fil d'accueil, lui, ne peut pas se le permettre.
            if dernier is not None:
                record.last_outcome = str(dernier.outcome)
                record.last_turn_at = maintenant
            if final.trace:
                record.last_stage_code = final.trace[-1].stage_code

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
                    version_detected=version_reconnue,
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

            # ⚠️ **« Réserver n'est pas consommer »** — la date se pose ici, quand le modèle
            # vient effectivement de servir, et pas à l'ouverture où l'on ignore encore s'il
            # servira. Posée une seule fois par réservation, donc **par texte** : rouvrir,
            # hésiter, revenir sur la même péricope reste une seule préparation comptée.
            # `NullVerseResolver` couvre les deux silences — pas de clé, ou quota épuisé — et
            # dans les deux cas rien n'a été consommé.
            if sollicite and not isinstance(assiste, NullVerseResolver):
                await self.reservations.mark_assisted(
                    church_id=record.church_id,
                    author_id=record.author_id,
                    pericope_key=(
                        f"pericope:{final.pericope_id}"
                        if final.pericope_id is not None
                        else _cle_provisoire(record.raw_input)
                    ),
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
            # ⚠️ L'étage vient de la **trace**, pas du résultat : `StageResult` ne porte pas son
            # code. Le dernier passage de trace est celui de l'étage qui a rendu la main, donc
            # celui dont les options sont offertes.
            options=_marquer_les_ecartees(
                dernier.options if dernier else (),
                final.trace[-1].stage_code if final.trace else "",
                await self.studies.list_dismissals(record.id),
            ),
            elements=tuple(await self.studies.list_elements(record.id)),
            # **Le fil est lu, pas rejoué.** Tout ce qui l'entoure se recalcule ; ces
            # paroles-là ne peuvent pas — elles ont été dites une fois.
            fil=await self.studies.list_thread(record.id),
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
        # ⚠️ **Une référence imprécise borne un intervalle ouvert, pas un verset.**
        #
        # « Galates 5 » n'a ni `verse_start` ni `verse_end` (S7), « 1 Rois » n'a pas même de
        # chapitre (S23) : lus comme un verset, ils servaient 5:1 et 1:1. Le bornage traduit
        # depuis toujours ces degrés de précision en bornes ouvertes (`_empan`) ; la
        # présentation, elle, les refermait — et « le tout, en un seul sermon » sur trois
        # unités rendait alors le premier verset de la première.
        fin = (
            fin_ref.chapter or _FIN_OUVERTE,
            fin_ref.verse_end or fin_ref.verse_start or _FIN_OUVERTE,
        )

        servis, variantes = [], []
        for v in verses_between(self.index, livre, debut, fin):
            reference = f"{etendue.start.book} {v.chapter}:{v.verse}"
            servis.append(VerseServed(
                reference=reference, text=v.body,
                elsewhere=self._ailleurs(livre, v.chapter, v.verse),
            ))
            for var in self.index.variants.get((livre, v.chapter, v.verse), ()):
                variantes.append(VariantSeen(
                    reference=reference, body=var.body,
                    doctrinal_weight=var.doctrinal_weight, note=var.note,
                    families_with=var.families_with,
                    families_without=var.families_without,
                    source_ref=var.source_ref,
                ))
        return tuple(servis), tuple(variantes)

    def _ailleurs(
        self, livre: int, chapitre: int, verset: int
    ) -> tuple[ReferenceElsewhere, ...]:
        """Ce que les autres témoins font de ce verset — **quand ils en font autre chose**.

        Le silence est la réponse ordinaire, et il est voulu : la numérotation concorde sur la
        quasi-totalité du corpus, et annoncer la concordance verset après verset enterrerait
        les quelques centaines d'endroits où elle manque. Le signal n'existe que là où il
        protège.

        ⚠️ **Aucune requête ici.** `reference_chez` lit l'index gelé — les étages du moteur sont
        synchrones et la présentation d'un passage ne doit pas toucher la base."""
        ailleurs = []
        for code in sorted(self.index.temoins):
            cible = self.index.reference_chez(code, livre, chapitre, verset)
            if cible == (chapitre, verset):
                continue
            ailleurs.append(ReferenceElsewhere(
                version=code,
                reference=f"{cible[0]}:{cible[1]}" if cible else None,
            ))
        return tuple(ailleurs)

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

    async def _ensure_preacher(
        self, actor_account_id: UUID, church_id: UUID | None
    ) -> None:
        """Préparer **n'exige rien** hors d'une église ; dans une église, c'est l'église qui dit.

        Sans église, il n'y a personne à qui demander : la garde ne s'applique pas à
        l'ouverture. Les appelants qui rouvrent une préparation existante passent par
        `_ensure_owner_or_preacher`, qui referme le seul trou que ce `None` ouvrirait.

        La règle elle-même vit dans `application/access.py` depuis que l'archive en a eu
        besoin : deux copies auraient été deux définitions de « mes préparations »."""
        await ensure_may_prepare(self.access, actor_account_id, church_id)

    async def _ensure_owner_or_preacher(
        self, actor_account_id: UUID, record: PreparationRecord
    ) -> None:
        """Rouvrir une préparation : **son auteur**, ou l'église quand il y en a une.

        ⚠️ Sur une préparation d'église, la garde reste ce qu'elle a toujours été — le droit
        de prêcher dans cette église, pas la propriété. Deux pasteurs d'une même assemblée
        peuvent donc se relire, et c'est délibéré ici : un travail d'église est un objet
        d'église.

        Sans église, cette règle n'a plus personne à interroger, et la seule qui reste est la
        propriété. C'est ce qui a décidé qu'**une préparation ne se rattache jamais d'office**
        à l'église de son auteur : le rattachement la rendrait lisible par ses collègues, et
        ce n'est pas un effet de bord qu'on inflige sans que quelqu'un l'ait voulu."""
        await ensure_may_read(self.access, actor_account_id, record)

