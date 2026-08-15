"""Le banc du tour — **deux chiffres, et un seul est un échec**.

    python scripts/urim_banc_tour.py

Il mesure la boucle entière — liaison, puis aiguilleur, puis répondeur — et non l'aiguilleur
seul. C'est la différence avec `urim_banc_aiguillage.py`, dont les 38/38 ne disent rien de ce
qui arrive en production : **les deux tiers du fil ne devraient jamais atteindre le modèle**.

## Les deux chiffres

    liaisons manquees        DOIT etre 0 — un appel paye pour rien, ET la mauvaise cible
    vraies saisies RENVOYEES DOIT etre 0 — on lui dit qu'il n'a rien a faire ici

Le reste est agréable, sans plus. C'est la leçon de la porte : *refuser un pasteur légitime
coûte infiniment plus cher que servir un étudiant.* Une réponse **à côté** n'est pas un refus :
les répondeurs étant déterministes, une intention mal aiguillée donne une réponse hors sujet et
jamais une réponse fausse — c'est le mode d'échec qu'on a accepté en branchant un aiguilleur
probabiliste, et il se compte à part.

## Pourquoi une liaison manquée est pire qu'un appel de trop

Le scénario du 12/08 : trois refus successifs, neuf appels, dix secondes, rien appris. Le coût
n'était pas le pire — l'aiguilleur rend `preciser`, ce qui est juste, et laisse le répondeur
sans aucun moyen de savoir **quelle** option était visée.

    Une intention mal aiguillée donne une reponse hors sujet.
    Une designation manquee fait agir sur le mauvais objet.

## Ce que « faux aiguillage » veut dire sur une vraie saisie

Les onze saisies attestées du Pasteur X sont des **ouvertures**, et l'aiguilleur ne voit jamais
une ouverture. Elles arrivent pourtant ici le jour où il les tape en cours de préparation — et
leur bonne lecture n'est pas un code unique : « l'amour fraternel n'existe plus dans l'eglise »
peut se lire comme un changement de sujet ou comme une correction, et les deux servent.

Chaque cas porte donc l'ensemble des codes **admis**, et la règle qui les fabrique tient en une
ligne : *une vraie saisie de pasteur ne doit jamais partir en `hors_champ` ni en
`indechiffrable`* — sauf la seule où c'est la bonne réponse, le micro resté ouvert sur la
voiture 406. Décider d'un code unique reviendrait à mesurer si le modèle est d'accord avec moi.

## Séquentiel et cadencé, et ce n'est pas de la prudence

🔴 Le premier passage du banc de la porte a tiré vingt cas en parallèle : 429 dès le sixième,
tout le reste revenu vide, et le rapport annonçait une porte parfaite — zéro étrangère servie,
et zéro pasteur servi non plus. **Une panne de débit ressemble exactement à un refus.** Un banc
sans cadence ne mesure pas la boucle, il mesure le quota, et il rend le verdict le plus flatteur
possible.

## La notation du pasteur, et les deux limites qui restent

`Jn14v28`, `Eph 1v20-22`, `jn 2:3` sont désormais des **liaisons** : le lecteur du corpus les
comprend, et la liaison confronte les références obtenues à l'écran. L'homonymie de `Jn` — quatre
livres — se résout par l'affichage, sans que personne n'ait à préférer un livre.

**`Hb 2v29` et `Ph 28v9` ne désignent rien, et reçoivent le verdict du corpus** — *« Hébreux 2
compte 18 versets »*, *« Philippiens compte 4 chapitres »*. Ce sont les deux références fautives
de ses notes ; Urim savait les nommer depuis le premier jour et ne le disait qu'aux textes
d'appui. Le tour les renvoyait à l'aiguilleur, qui répondait à côté sans rien dire de l'erreur.
Zéro appel : le corpus sait cela tout seul.

**La limite qui reste : le nom de livre doit ouvrir la saisie**, et la saisie doit être la
référence *et rien d'autre* pour que le contrôle ose contredire. « prends Hb 2v29 » n'est pas
lu ; « Nombres 500 personnes sont venues » n'est pas contredit. Balayer la phrase entière
rendrait « Marc a quitté l'église » équivalent à une référence.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.contexts.urim.application.conversation import (
    Ecran,
    Notation,
    Tour,
    conduire,
    lire_la_notation,
)
from app.contexts.urim.engine.state import Reference
from app.contexts.urim.infrastructure.corpus.index import load_corpus_index
from app.core.config import get_settings
from app.core.database import async_session_factory
from scripts.urim_curate_pericopes import ESSAIS, INTERVALLE, Cadence

REEL, CONSTRUIT = "reel", "construit"

#: Les deux codes qui **renvoient** le pasteur. Une vraie saisie de préparation qui y tombe est
#: le seul échec que ce banc compte — c'est l'asymétrie de la porte, transposée au tour.
RENVOIS = ("hors_champ", "indechiffrable")

#: L'écran d'un tour en cours : deux loci, l'unité relue, puis des passages proposés par le
#: sens — dont **les textes que le Pasteur X a réellement cités dans ses notes**, sans quoi sa
#: notation n'aurait rien à désigner et le banc mesurerait un écran qui ne lui ressemble pas.
#:
#: **L'ordre est celui de l'affichage** — c'est lui qui donne son sens à « le deuxième », et le
#: compter sur la liste du moteur ferait agir sur la mauvaise option.
_UNITE = "texte:11111111-2222-3333-4444-555555555555"

_AFFICHE: tuple[tuple[str, str, Reference], ...] = (
    ("axe:soteriologie", "Sotériologie", Reference("")),
    ("axe:ecclesiologie", "Ecclésiologie", Reference("")),
    (_UNITE, "La charité sans hypocrisie", Reference("")),
    ("Romains 12:9-16", "Romains 12:9-16", Reference("Romains", 12, 9, 16)),
    ("Jean 14:15-31", "Jean 14:15-31", Reference("Jean", 14, 15, 31)),
    ("Éphésiens 1:15-23", "Éphésiens 1:15-23", Reference("Éphésiens", 1, 15, 23)),
    ("Hébreux 2:1-18", "Hébreux 2:1-18", Reference("Hébreux", 2, 1, 18)),
    ("Jean 2:1-11", "Jean 2:1-11", Reference("Jean", 2, 1, 11)),
    ("Luc 15:11-24", "Luc 15:11-24", Reference("Luc", 15, 11, 24)),
)

ECRAN = Ecran(
    codes=tuple(code for code, _, _ in _AFFICHE),
    libelles=tuple(libelle for _, libelle, _ in _AFFICHE),
    references=tuple(reference for _, _, reference in _AFFICHE),
    ancre="Romains 12:9-16",
    attend=True,
)


@dataclass(frozen=True)
class CasLie:
    """Une saisie qui **désigne l'écran**. Elle doit coûter zéro appel, et viser juste."""

    texte: str
    #: Le code d'option attendu — `None` quand rien n'est décidé : l'acquiescement, et la
    #: référence que le corpus refuse.
    attendu: str | None
    #: Un morceau de phrase que la réponse doit porter. Sert aux cas qui ne décident rien mais
    #: **disent** quelque chose : sans lui, « rien décidé » se confondrait avec « rien fait ».
    marque: str = ""
    ecarte: bool = False
    #: Le cas passe par le **lecteur de notation**, donc par le corpus. Sans corpus chargé, il
    #: n'est pas mesuré — et on le **dit**, plutôt que de le compter comme réussi ou raté.
    notation: bool = False
    note: str = ""


@dataclass(frozen=True)
class CasAiguille:
    """Une saisie que la liaison laisse passer. Elle coûte un appel, et un seul."""

    texte: str
    acceptes: tuple[str, ...]
    provenance: str
    note: str = ""


_LIAISONS: tuple[CasLie, ...] = (
    # ------------------------------------------------- les quatre tours de la maquette
    CasLie("Ecclésiologie", "axe:ecclesiologie", note="maquette, tour 2"),
    CasLie("La charité sans hypocrisie", "texte:11111111-2222-3333-4444-555555555555",
           note="maquette, tour 4 — l'unite designee par son intitule"),
    CasLie("Romains 12", "Romains 12:9-16", note="le livre et son chapitre suffisent"),
    CasLie("romains 12:9-16", "Romains 12:9-16"),

    # ------------------------------------------------- les rangs
    CasLie("le deuxième", "axe:ecclesiologie"),
    CasLie("le 2", "axe:ecclesiologie"),
    CasLie("prends le troisième", "texte:11111111-2222-3333-4444-555555555555"),
    CasLie("le dernier", "Luc 15:11-24"),

    # ------------------------------------------------- LE SCENARIO DU 12/08 : trois refus
    CasLie("non, pas le premier", "axe:soteriologie", ecarte=True,
           note="9 appels et 10 secondes pour ces trois lignes-la"),
    CasLie("pas la charité sans hypocrisie",
           "texte:11111111-2222-3333-4444-555555555555", ecarte=True),
    CasLie("enlève Luc 15", "Luc 15:11-24", ecarte=True),

    # ------------------------------------- LA NOTATION DU PASTEUR, sur des textes affiches
    CasLie("Jn14v28", "Jean 14:15-31", notation=True,
           note="Jn designe QUATRE livres — c'est l'ecran qui tranche, personne ne devine"),
    CasLie("Eph 1v20-22", "Éphésiens 1:15-23", notation=True),
    CasLie("jn 2:3", "Jean 2:1-11", notation=True,
           note="le verset choisit entre Jean 14 et Jean 2"),
    CasLie("non, pas Jn14v28", "Jean 14:15-31", ecarte=True, notation=True,
           note="un prefixe de retrait est retire — vocabulaire ferme, jamais de la prose"),

    # ------------------------------------------------- LE CONTROLE DE REFERENCE
    #
    # `Hb 2v29` est LA reference inexistante de ses notes. Elle ne designe rien — et c'est
    # justement ce qu'il faut lui dire. Urim le savait depuis le premier jour, et ne le disait
    # qu'aux textes d'appui : au tour, la saisie repartait a l'aiguilleur, qui repondait a cote
    # sans rien dire de l'erreur de reference. Zero appel : le corpus sait ca tout seul.
    CasLie("Hb 2v29", None, marque="il n'y a pas de verset 29", notation=True,
           note="Hebreux 2 compte 18 versets — le motif du corpus traverse intact"),
    CasLie("Ph 28v9", None, marque="il n'y a pas de chapitre 28", notation=True,
           note="l'autre reference fautive de ses notes : Philippiens a 4 chapitres"),

    # ------------------------------------------------- les bornes, et l'acquiescement
    CasLie("versets 9 à 16", "Romains 12:9-16",
           note="des bornes qui coincident avec une option affichee"),
    CasLie("oui", None, note="la 3e forme d'indechiffrable, consommee sans appel"),
    CasLie("ok", None),
    CasLie("...", None, note="ni mot ni chiffre — rien a classer"),
)


_AIGUILLAGES: tuple[CasAiguille, ...] = (
    # ============================================ LES ONZE SAISIES REELLES DU PASTEUR X
    #
    # Toutes sont des OUVERTURES : l'aiguilleur ne les voit qu'ici, le jour ou le pasteur les
    # tape en cours de preparation. Leur ensemble de codes admis est genereux — ce qu'on
    # mesure n'est pas l'accord avec moi, c'est le renvoi.
    # ⚠️ Ses QUATRE references sont passees du cote LIAISON : trois designent une option, et
    # `Hb 2v29` recoit le verdict du corpus. Aucune ne coute d'appel.
    CasAiguille("le fils prodigue rentre chez son pere",
                ("changer_de_sujet", "preciser", "interroger_texte"), REEL,
                "une scene racontee de memoire"),
    CasAiguille("l'amour fraternel n'existe plus dans l'eglise",
                ("changer_de_sujet", "preciser", "interroger_travail"), REEL,
                "UNE PLAINTE — le piege : 'la vie d'une assemblee' l'envoie en hors_champ"),
    CasAiguille("Dieu est l'auteur et le consommateur de notre foi, sur l'autel Divin",
                ("changer_de_sujet", "preciser", "interroger_texte"), REEL,
                "bancale, et c'est une vraie predication"),
    CasAiguille("je veux faire un culte sur l'adultère dans",
                ("changer_de_sujet", "preciser"), REEL,
                "TRONQUEE — le piege : 'fragment interrompu' l'envoie en indechiffrable"),
    CasAiguille("les esclaves hebreux ne portaient pas de chaussures",
                ("interroger_texte", "preciser"), REEL,
                "de l'HISTOIRE — le corpus ne sait pas repondre, et c'est le repondeur qui le dit"),
    CasAiguille("que veut dire upodema", ("interroger_texte",), REEL, "un mot grec seul"),
    CasAiguille("Ma voiture 406, a besoin de reparation , jefgf Paradis",
                ("indechiffrable",), REEL,
                "LE SEUL CAS REEL OU LE RENVOI EST JUSTE — le micro reste ouvert (S36)"),

    # ============================================ les cas construits — mesurent surtout
    # si le modele est d'accord avec moi. Repris du banc de l'aiguilleur, pour que les deux
    # restent comparables.
    CasAiguille("Quel plan je peux tenir sur ce texte ?", ("interroger_travail",), CONSTRUIT,
                "maquette, tour 5 — LE tour qui n'avait aucune route"),
    CasAiguille("Propose-moi un theme.", ("demander_production",), CONSTRUIT, "maquette, tour 6"),
    CasAiguille("mets moi ca en powerpoint", ("demander_production",), CONSTRUIT),
    CasAiguille("pourquoi le bloc se ferme au verset 16 ?", ("interroger_texte",), CONSTRUIT),
    CasAiguille("y a un risque de proof texting sur ce que je fais ?",
                ("interroger_travail",), CONSTRUIT),
    CasAiguille("ce n'est pas ca", ("preciser",), CONSTRUIT),
    CasAiguille("en fait je vais precher sur autre chose", ("changer_de_sujet",), CONSTRUIT),
    CasAiguille("comment je dis ca a des jeunes qui ont quitte l'eglise ?",
                ("hors_champ",), CONSTRUIT, "scenario du 12/08"),
    CasAiguille("prie pour moi", ("hors_champ",), CONSTRUIT,
                "TROUVE PAR LE BANC DE L'AIGUILLEUR : partait en indechiffrable"),
    CasAiguille("attends deux minutes je arrive euh le fils la le retour bon",
                ("indechiffrable",), CONSTRUIT, "dictee en marchant"),
)


class _Compte:
    """Le modèle, **avec un compteur d'appels et sa cadence**.

    Le compteur est la moitié de la mesure : un tour que la liaison pouvait résoudre et qui
    passe ici est un défaut, pas une lenteur. La cadence est dans le même objet parce que seuls
    les vrais appels doivent être ralentis — les quinze liaisons ne consomment rien, et les
    faire attendre allongerait le banc pour rien."""

    def __init__(self, ia: MistralAssistant, cadence: Cadence) -> None:
        self._ia, self._cadence = ia, cadence
        self.appels = 0

    @property
    def echecs(self) -> int:
        """Le compteur du transport, **relu tel quel** — c'est lui qui distingue une panne
        d'un tour non classable, et le dupliquer ici les reconfondrait."""
        return self._ia.echecs

    async def aiguiller(self, texte: str) -> str | None:
        self.appels += 1
        await self._cadence.attendre()
        return await self._ia.aiguiller(texte)


@dataclass
class VerdictLie:
    cas: CasLie
    tour: Tour
    appels: int

    @property
    def juste(self) -> bool:
        if self.appels or self.cas.marque not in (self.tour.reponse or ""):
            return False
        vise = self.tour.refus if self.cas.ecarte else self.tour.decision
        return vise == self.cas.attendu and not (
            self.cas.ecarte and self.tour.decision is not None
        )


@dataclass
class VerdictAiguille:
    cas: CasAiguille
    obtenu: str | None

    @property
    def juste(self) -> bool:
        return self.obtenu in self.cas.acceptes

    @property
    def renvoye(self) -> bool:
        """🔴 **L'échec.** On lui a dit qu'il n'avait rien à faire ici.

        C'est la transposition exacte de l'asymétrie de la porte : là-bas, refuser un pasteur
        légitime coûtait infiniment plus cher que servir un étudiant."""
        return self.obtenu in RENVOIS and self.obtenu not in self.cas.acceptes

    @property
    def hors_sujet(self) -> bool:
        """Gênant, pas grave. Le répondeur a répondu à côté — **jamais faux**, puisqu'il est
        déterministe. C'est le mode d'échec qu'on a accepté en branchant un aiguilleur
        probabiliste, et il ne se compte pas avec le précédent."""
        return not self.juste and not self.renvoye


async def _les_liaisons(ia: _Compte, index) -> list[VerdictLie]:
    """Aucun appel attendu — et le compteur le prouve, il ne le suppose pas."""
    verdicts: list[VerdictLie] = []
    for cas in _LIAISONS:
        if cas.notation and index is None:
            print(f"  ---  corpus absent, non mesure : {cas.texte}")
            continue
        avant = ia.appels
        tour = await conduire(cas.texte, ECRAN, ia, _lues(cas.texte, index))
        v = VerdictLie(cas, tour, ia.appels - avant)
        verdicts.append(v)
        marque = "OK " if v.juste else "NON"
        geste = "ecarte " if tour.refus else "decide " if tour.decision else "       "
        print(
            f"  {marque}  {v.appels} appel   {geste}{tour.refus or tour.decision or '—':<44}"
            f" {cas.texte[:26]}"
        )
    return verdicts


def _lues(saisie: str, index) -> Notation:
    """Ce que le lecteur de notation a compris — vide quand le corpus n'est pas chargé.

    ⚠️ **Le vrai corpus, jamais une doublure.** Reconnaître `Hb` comme Hébreux tient dans les
    357 formes de noms de livre, et savoir qu'Hébreux 2 s'arrête au verset 18 tient dans le
    texte lui-même ; en fabriquer trois à la main ferait passer un banc pour une preuve, et
    c'est exactement la faute que le dépôt s'interdit ailleurs."""
    return lire_la_notation(saisie, index) if index is not None else Notation()


async def _les_aiguillages(ia: _Compte, index) -> list[VerdictAiguille]:
    """⚠️ **Séquentiel, cadencé, et avec reprises.** Une panne de débit ressemble exactement à
    un refus : sans la comparaison des échecs avant/après, un 429 passerait pour un tour non
    classable, et le banc rendrait le verdict le plus flatteur possible."""
    verdicts: list[VerdictAiguille] = []
    for cas in _AIGUILLAGES:
        for essai in range(ESSAIS):
            avant = ia.echecs
            tour = await conduire(cas.texte, ECRAN, ia, _lues(cas.texte, index))
            if ia.echecs == avant:
                break
            await asyncio.sleep(2**essai)
        else:
            print(f"  ECHEC  le modele n'a pas repondu : {cas.texte[:44]}")
            continue
        obtenu = _code_depuis(tour)
        v = VerdictAiguille(cas, obtenu)
        verdicts.append(v)
        marque = "OK " if v.juste else "NON"
        print(f"  {marque}  {cas.provenance:<10} -> {obtenu!s:<22} {cas.texte[:38]}")
    return verdicts


#: La phrase du répondeur → le code qui l'a produite. Le tour ne rend pas l'intention : il rend
#: la réponse, ce qui est la bonne surface pour le produit et la mauvaise pour un banc. On la
#: retrouve par une marque propre à chaque répondeur, plutôt qu'en faisant remonter un champ de
#: diagnostic dans le contrat — **le banc s'adapte au produit, pas l'inverse**.
_MARQUES: tuple[tuple[str, str], ...] = (
    ("hors_champ", "ne sais pas conseiller sur les personnes"),
    ("hors_champ", "ne suis pas quelqu'un"),
    ("indechiffrable", "Je n'ai rien reçu"),
    ("preciser", "Rien n'est figé"),
    ("interroger_texte", "vient du corpus et de rien d'autre"),
    ("interroger_travail", "déjà sous vos yeux"),
    ("demander_production", "jamais un titre"),
    ("changer_de_sujet", "autre préparation"),
    ("_sans_texte", "Aucun texte n'est encore ouvert"),
    ("_panne", "c'est de mon côté"),
    ("_sans_modele", "phrase libre"),
    ("_reference_introuvable", "votre préparation ne bouge pas"),
)


def _code_depuis(tour: Tour) -> str | None:
    return next(
        (code for code, marque in _MARQUES if marque in (tour.reponse or "")), None
    )


def _rapport(lies: list[VerdictLie], aiguilles: list[VerdictAiguille]) -> None:
    reels = [v for v in aiguilles if v.cas.provenance == REEL]
    construits = [v for v in aiguilles if v.cas.provenance == CONSTRUIT]
    manquees = [v for v in lies if not v.juste]
    renvoyes = [v for v in reels if v.renvoye]
    a_cote = [v for v in reels if v.hors_sujet]

    def part(lot: list) -> str:
        if not lot:
            return "—"
        n = sum(1 for v in lot if v.juste)
        return f"{n}/{len(lot)}  ({100 * n / len(lot):.0f} %)"

    # ⚠️ **Un banc qui ne sait plus lire ses propres réponses doit le crier.** `_MARQUES`
    # retrouve le code depuis la phrase du répondeur ; le jour où une formulation change, le
    # cas deviendrait « à côté » — c'est-à-dire *gênant, pas grave* — alors que c'est le banc
    # qui est cassé. C'est la même faute que le 429 pris pour un refus.
    illisibles = [v for v in aiguilles if v.obtenu is None]
    if illisibles:
        print("\n" + "!" * 78)
        print(f"  BANC PERIME — {len(illisibles)} reponse(s) que _MARQUES ne reconnait plus.")
        print("  Une formulation de repondeur a change : les chiffres ci-dessous mentent.")
        print("!" * 78)

    print("\n" + "=" * 78)
    print("  LES DEUX CHIFFRES QUI SONT DES ECHECS")
    print("=" * 78)
    print(f"  liaisons manquees                    {len(manquees)}/{len(lies)}")
    print(f"  vraies saisies RENVOYEES             {len(renvoyes)}/{len(reels)}")
    print("  → une designation manquee fait agir sur le mauvais objet ; une saisie de")
    print("    pasteur renvoyee lui dit qu'il n'a rien a faire ici.")

    print("\n" + "=" * 78)
    print("  CE QUI EST GENANT, SANS PLUS")
    print("=" * 78)
    print(f"  reponses a cote sur les REELLES      {len(a_cote)}/{len(reels)}")
    print("  → les repondeurs sont deterministes : une intention mal aiguillee donne")
    print("    une reponse hors sujet, JAMAIS une reponse fausse.")
    print(f"  aiguillage juste sur les construites {part(construits)}")
    print("  → ce chiffre dit surtout si le modele est d'accord avec moi.")

    if a_cote:
        print("\n" + "=" * 78)
        print("  LES REPONSES A COTE  (genant, pas grave)")
        print("=" * 78)
        for v in a_cote:
            print(f"  {v.obtenu!s:<22} « {v.cas.texte[:48]} »")

    if manquees:
        print("\n" + "=" * 78)
        print("  LES DESIGNATIONS MANQUEES")
        print("=" * 78)
        for v in manquees:
            vise = v.tour.refus or v.tour.decision
            print(f"\n  « {v.cas.texte} »   {v.appels} appel(s)")
            print(f"    attendu {v.cas.attendu}, obtenu {vise}")
            if v.cas.note:
                print(f"    note : {v.cas.note}")

    if renvoyes:
        print("\n" + "=" * 78)
        print("  LES PASTEURS QU'ON AURAIT RENVOYES")
        print("=" * 78)
        for v in renvoyes:
            print(f"\n  « {v.cas.texte} »")
            print(f"    admis {', '.join(v.cas.acceptes)} — obtenu {v.obtenu}")
            if v.cas.note:
                print(f"    note : {v.cas.note}")


async def _corpus():
    """Le corpus réel, ou `None` — **et on le dit**, on ne se rabat pas en silence.

    Un banc qui perdrait le lecteur de notation sans le signaler compterait quatre cas comme
    ratés alors que c'est la mesure qui manque. C'est la même faute que le 429 pris pour un
    refus, à un autre endroit."""
    try:
        async with async_session_factory() as session:
            return await load_corpus_index(session)
    except Exception as erreur:  # un banc ne doit jamais tomber sur ce qu'il vient mesurer
        print(f"CORPUS ABSENT ({type(erreur).__name__}) — la notation ne sera PAS mesuree.\n")
        return None


async def main() -> None:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        print("MISTRAL_API_KEY absente — rien a mesurer.")
        return

    index = await _corpus()
    ia = _Compte(
        MistralAssistant(reglages.mistral_api_key, reglages.mistral_model),
        Cadence(INTERVALLE),
    )
    print(
        f"Modele : {reglages.mistral_model}   —   {len(_LIAISONS)} liaisons, "
        f"{len(_AIGUILLAGES)} aiguillages"
    )
    if index is not None:
        print(f"Corpus : {index.snapshot}   —   {len(index.books_by_form)} formes de nom")
    print()

    print("-" * 78)
    print("  LA LIAISON — zero appel attendu")
    print("-" * 78)
    lies = await _les_liaisons(ia, index)

    print("\n" + "-" * 78)
    print("  L'AIGUILLEUR — un appel par cas, sequentiel et cadence")
    print("-" * 78)
    aiguilles = await _les_aiguillages(ia, index)

    _rapport(lies, aiguilles)
    print(f"\n  appels de modele au total : {ia.appels}  (plancher : {len(_AIGUILLAGES)})")


if __name__ == "__main__":
    asyncio.run(main())
