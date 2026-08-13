"""Le contrôle de citation — **un verset inventé sur écran est fatal, et détectable**.

Trois verdicts, et la distinction entre les deux premiers est ce qui garde le garde-fou en vie
(S4) :

| verdict | ce que c'est | issue |
| :-- | :-- | :-- |
| `exact` | le verset, mot pour mot | ✅ |
| `extrait` | **une troncature** — couper la fin pour l'écran est légitime et universel | ✅ |
| `altere` | un mot changé, ajouté, ou l'ordre défait | ⛔ |

Un booléen confondrait les deux premiers. Rejeter une troncature au même titre qu'une
altération ferait contourner la validation par tous ceux qui coupent leurs versets — c'est-à-dire
tout le monde — et **le garde-fou mourrait de son excès de zèle**.

## La règle

Le texte projeté doit être une **sous-chaîne contiguë** du corpus après normalisation ; `…`
autorise **plusieurs fragments contigus, dans l'ordre, sans chevauchement**.

## Ce que la normalisation efface, et le risque assumé

On compare des **suites de mots** : casse, accents, apostrophes et ponctuation sont repliés. Un
pasteur qui tape sans accents sur une tablette un vendredi soir ne doit pas s'entendre dire
qu'il a falsifié l'Écriture.

⚠️ **Le prix est réel et il est écrit ici plutôt que découvert** : la ponctuation ne pesant pas,
un point d'interrogation ajouté passerait pour une troncature légitime. C'est le seul trou connu
de cette règle. Le refermer coûterait de rejeter la virgule oubliée — donc de faire contourner
la validation, ce que S4 a précisément appris à ne pas faire. On préfère un trou nommé à un
garde-fou mort.

Module **pur** : ni corpus, ni base, ni horloge. Il juge deux chaînes.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

#: Ce que le pasteur tape pour dire « je saute un morceau ». Les trois formes réelles : le
#: caractère typographique, trois points, et deux points suivis d'un espace hésitant.
_ELLIPSE = re.compile(r"…|\.\.\.")

#: **Les crochets sont une glose, pas le texte** — et c'est une prédication réelle qui l'a appris.
#:
#: Le témoin du 06/06 cite Jean 7:37-39 ainsi : *« Jésus, se tenant debout, s'écria [à haute
#: voix] : Si quelqu'un a soif… Celui qui croit [qui adhère, compte, et se confie] en moi »*.
#: C'est une version amplifiée, où le crochet **signale lui-même** qu'il ajoute. Sans cette
#: règle, chacune de ces insertions casse la contiguïté et le verdict tombe à `altere` : le
#: pasteur s'entendrait dire qu'il falsifie l'Écriture alors qu'il fait exactement l'inverse —
#: il montre où finit le texte et où commence l'explication.
#:
#: ⚠️ **La glose n'est pas effacée du document**, seulement de la comparaison. À l'écran, les
#: crochets restent visibles : l'assemblée voit, elle aussi, ce qui est ajouté.
_GLOSE = re.compile(r"\[[^\]]*\]")

#: Les cinq apostrophes, **par leur point de code** — comme le normaliseur du moteur les écrit
#: en échappement, et pour la même raison : sur un clavier ces glyphes sont indiscernables, et
#: une relecture ne verrait pas qu'il en manque un. Ici on va plus loin en les nommant, parce
#: qu'un numéro se vérifie dans une table Unicode et qu'un glyphe se croit.
_FORMES_APOSTROPHE = (
    0x0027,  # apostrophe droite — celle des claviers
    0x2019,  # apostrophe typographique — celle des traitements de texte
    0x02BC,  # lettre modificatrice — fréquente dans les corpus importés
    0x02BB,  # sa jumelle tournée
    0x0060,  # accent grave, tapé par erreur à sa place
)

_APOSTROPHES = re.compile(f"[{''.join(chr(code) for code in _FORMES_APOSTROPHE)}]")

#: Tout ce qui n'est ni lettre ni chiffre devient une frontière de mot. L'apostrophe est
#: traitée **avant**, et devient une frontière elle aussi : « l'amour » donne deux mots, ce qui
#: est la bonne granularité pour comparer un texte projeté à un texte servi. (C'est l'inverse du
#: normaliseur du moteur, qui la supprime pour faire converger « leglise » et « l'Église » — là
#: -bas on cherche une ressemblance, ici on vérifie une identité.)
_NON_MOT = re.compile(r"[^0-9a-z]+")

EXACT, EXTRAIT, ALTERE = "exact", "extrait", "altere"


@dataclass(frozen=True, slots=True)
class Verdict:
    """Le jugement d'une diapositive. `rationale` n'est jamais vide — comme partout ici.

    `version` dit **contre laquelle** le texte a été reconnu, et ce n'est pas cosmétique : sur
    Romains 8:1, reconnaître Ostervald plutôt que la LSG change la doctrine du verset projeté
    (S17 — sans la clause, « aucune condamnation » est inconditionnel ; avec elle, c'est une
    condition morale). C'est cette valeur que `citation_check.version_id` attend depuis qu'elle
    a été déclarée."""

    verdict: str
    rationale: str
    version: str = ""

    @property
    def projetable(self) -> bool:
        """`altere` bloque le fichier entier ; les deux autres passent."""
        return self.verdict in (EXACT, EXTRAIT)


def mots(texte: str) -> tuple[str, ...]:
    """La suite de mots normalisée — gloses retirées, casse, accents, apostrophes, ponctuation
    repliées."""
    sans_glose = _GLOSE.sub(" ", texte)
    plie = unicodedata.normalize("NFD", _APOSTROPHES.sub(" ", sans_glose.casefold()))
    sans_accent = "".join(c for c in plie if unicodedata.category(c) != "Mn")
    return tuple(mot for mot in _NON_MOT.sub(" ", sans_accent).split() if mot)


def juger(projete: str, servi: str) -> Verdict:
    """Le texte projeté est-il ce que le corpus porte ?

    `servi` est le texte **du corpus**, jamais une saisie : c'est ce qui fait de cette fonction
    un contrôle plutôt qu'une comparaison de deux opinions."""
    reference = mots(servi)
    if not reference:
        # Aucun texte servi : on ne peut rien affirmer, et affirmer quand même serait pire
        # que se taire. C'est un refus, pas un feu vert.
        return Verdict(ALTERE, "Aucun texte de référence pour cette référence.")

    fragments = [mots(part) for part in _ELLIPSE.split(projete)]
    fragments = [f for f in fragments if f]
    if not fragments:
        return Verdict(ALTERE, "La diapositive ne porte aucun texte.")

    if len(fragments) == 1 and fragments[0] == reference:
        return Verdict(EXACT, "Le texte projeté est celui du corpus.")

    position = _suivre(fragments, reference)
    if position is None:
        return Verdict(
            ALTERE,
            "Ce texte n'est pas celui du corpus. Le texte servi est : "
            f"« {servi.strip()} »",
        )

    coupe = "plusieurs passages coupés" if len(fragments) > 1 else "un extrait"
    return Verdict(
        EXTRAIT,
        f"Le texte projeté est {coupe} du verset, sans altération — "
        "couper pour l'écran est légitime.",
    )


def juger_parmi(projete: str, servis: Sequence[tuple[str, str]]) -> Verdict:
    """Juger contre **toutes les versions détenues**, et nommer celle qui reconnaît le texte.

    ⚠️ **C'est la correction de Q9, et elle change la nature du refus.** Un pasteur cite la
    Bible qu'il a. Jugé contre une seule version, un texte parfaitement fidèle à une autre rend
    `altere` — c'est-à-dire une **accusation**, là où la vérité est *« je ne détiens pas votre
    Bible »*. Le cas est réel et documenté dans ce dépôt : la clause de Romains 8:1 que le Texte
    Reçu ajoute, qu'**Ostervald porte** et que la LSG omet.

    C'est S19 appliqué au livrable — *on dit ce qui manque au corpus, jamais ce qui manque au
    pasteur* — et le motif du refus nomme donc les versions consultées.

    **L'ordre de `servis` est un ordre de préférence** (la version de la préparation d'abord),
    mais `exact` l'emporte sur `extrait` quel que soit le rang : mieux vaut nommer la version
    qui porte le texte entier que celle où il ne serait qu'un extrait."""
    if not servis:
        return Verdict(ALTERE, "Aucune version du corpus ne sert ce passage.")

    verdicts = [(label, juger(projete, servi)) for label, servi in servis]
    for attendu in (EXACT, EXTRAIT):
        for label, verdict in verdicts:
            if verdict.verdict == attendu:
                return Verdict(
                    verdict.verdict,
                    f"{verdict.rationale} (version reconnue : {label})",
                    version=label,
                )

    consultees = ", ".join(label for label, _ in servis)
    _, premier = servis[0]
    return Verdict(
        ALTERE,
        f"Ce texte ne correspond à aucune des {len(servis)} versions détenues "
        f"({consultees}). Vient-il d'une autre version ? Le texte servi est : "
        f"« {premier.strip()} »",
    )


def _suivre(
    fragments: list[tuple[str, ...]], reference: tuple[str, ...]
) -> int | None:
    """Chaque fragment est-il contigu, **dans l'ordre et sans chevauchement** ?

    C'est le « … » qui rend cette boucle nécessaire : sans lui il n'y aurait qu'une recherche de
    sous-chaîne. La progression stricte (`depuis = trouve + len(fragment)`) est ce qui interdit
    de recomposer une phrase que le texte ne dit pas en réutilisant deux fois le même passage."""
    depuis = 0
    for fragment in fragments:
        trouve = _index_de(reference, fragment, depuis)
        if trouve is None:
            return None
        depuis = trouve + len(fragment)
    return depuis


def _index_de(
    reference: tuple[str, ...], fragment: tuple[str, ...], depuis: int
) -> int | None:
    taille = len(fragment)
    for debut in range(depuis, len(reference) - taille + 1):
        if reference[debut:debut + taille] == fragment:
            return debut
    return None
