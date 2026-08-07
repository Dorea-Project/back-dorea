"""Le geste posé — *« je suis passé le voir »*, et rien de plus.

Le pendant exact du signalement par un tiers, et son inverse dans le temps. Là où *« je m'en
occupe »* déclare une **intention** que le responsable se donne, *« je suis passé »* déclare un
**acte accompli** — et c'est le seul fait du moteur qui dise que quelqu'un a pris soin de
quelqu'un sans que l'institution y soit pour rien.

`FactKind.GESTURE_DONE` portait ce nom depuis l'écriture du contrat, avec son commentaire —
*« visite, appel abouti, aide déclarée »* — et **aucune source ne pouvait l'émettre**. Le domaine
l'attendait de partout ailleurs : `Signal.record_gesture()` n'avait aucun appelant, la colonne
`gestures_count` restait à zéro, et le garde de reprojection protégeait des gestes que rien
n'écrivait. Ce module est la porte qui manquait.

---

**Il dit le geste, jamais le motif.** *« Je suis passé le voir »*, pas *« parce qu'il est
malade »*. Le motif appartient à la personne : c'est à elle de le déclarer — un tag d'absence — ou
à l'église de le publier — une annonce. Un tiers qui pourrait écrire la raison construirait un
dossier de santé tenu par les voisins, et ce dossier survivrait à tous ceux qui l'ont écrit.

**Il ne nomme personne.** L'annotation dit *« quelqu'un »*, comme le signalement par un tiers ne
nomme pas son émetteur. Nommer celui qui est passé a une vraie utilité — pouvoir lui demander des
nouvelles plutôt que de déranger la personne — mais c'est le **lien**, et le lien vient avec ses
propres gardes. On ne le fait pas entrer par la petite porte d'une annotation.

**Il ne ferme rien.** Un geste informe, il n'éteint pas : c'est l'asymétrie déjà écrite au registre
pour la reconnaissance déposée — *« un responsable qui pourrait déposer "elle va bien" à la place
de quelqu'un ferait taire un cas avec sa propre impression »*. Ici, la même règle vue du membre :
ce que Jean a constaté chez Sondet n'est pas ce que Sondet dit de lui-même.

Une liste **fermée**, comme les nuances et comme les tags d'absence : on tape, on n'écrit pas.
"""

from __future__ import annotations

from enum import StrEnum


class GestureKind(StrEnum):
    """Liste **fermée**. Chaque membre décrit un acte qui a eu lieu, jamais son motif."""

    VISIT = "visit"  # être allé chez la personne
    CALL = "call"  # l'avoir eue, pas l'avoir appelée dans le vide
    HELP = "help"  # un coup de main donné


# Ce qui s'écrira sur la fiche du cas. Trois règles tiennent ces phrases :
#
# - **rien sur l'état de la personne** — on décrit ce que le déclarant a fait, pas ce qu'il a
#   trouvé. Un « il allait bien » posé par un tiers est une impression, et elle ferait taire ;
# - **personne n'est nommé** — ni le déclarant, ni un pronom qui trahirait qui il est ;
# - **aucun accord de genre** — ces phrases s'affichent pour n'importe qui, et une formulation qui
#   oblige à choisir entre « passé » et « passée » finit toujours par se tromper sur quelqu'un.
GESTURE_LABELS: dict[GestureKind, str] = {
    GestureKind.VISIT: "Quelqu'un de l'église lui a rendu visite",
    GestureKind.CALL: "Quelqu'un de l'église lui a parlé au téléphone",
    GestureKind.HELP: "Quelqu'un de l'église lui a donné un coup de main",
}
