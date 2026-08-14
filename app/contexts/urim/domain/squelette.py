"""Le squelette d'une prédication — **les codes, et pourquoi la liste est celle-ci**.

Elle vivait dans `deliverable/domain/documents.py`, où le livrable en avait besoin pour son
verrou. Mais le squelette n'appartient pas au livrable : c'est **la préparation** qui le porte,
et `PUT /elements` l'écrit bien avant qu'un document existe. Il remonte donc ici, au domaine
commun, et le livrable l'importe comme les autres.

---

## Pourquoi fermer une liste qu'on avait laissée ouverte

La colonne était un texte libre. Deux dangers opposés, et il a fallu les peser :

| Laisser ouvert | Fermer |
| :-- | :-- |
| Le verrou du livrable s'adosse au code `divisions`. Un client qui envoie `Divisions`
  — ou `Point` — **refuse son document à un pasteur qui a pourtant écrit son plan** |
  Un code hors liste **ne s'enregistre plus**, ce qui est pire : ça bloque son travail,
  pas seulement son document |

La sortie n'est ni l'un ni l'autre : **on ferme, mais on normalise et on traduit d'abord.**
`Divisions`, `POINT`, `sous point`, `Intro` retombent tous sur leur code canonique. Ce qui est
refusé, c'est ce qu'on ne sait vraiment pas ranger — et le refus **nomme la liste**.

## Pourquoi quinze et non dix

Braga en nomme dix. **Les prédications réelles en portent cinq de plus** (`docs/temoins/`) :
objectif, contexte du livre, définitions, NB, témoignage personnel. Fermer aux dix aurait
refusé à trois pasteurs sur trois des sections qu'ils tiennent depuis toujours — le même défaut
que le verrou adossé à la `proposition`, corrigé la veille pour la même raison.

> La liste n'est pas la théorie d'un manuel : c'est ce que le manuel dit **plus** ce que les
> notes montrent.

⚠️ **Elle s'élargira**, et c'est prévu : un code de plus est une ligne ici et une migration.
Ce qu'on refuse, c'est qu'elle s'élargisse **par accident**, un client à la fois.
"""

from __future__ import annotations

import unicodedata

#: Les dix de Braga, dans l'ordre canonique — celui que l'écran propose.
ELEMENTS = (
    "titre",
    "introduction",
    "proposition",
    "phrase_interrogative",
    "phrase_de_transition",
    "divisions",
    "subdivisions",
    "illustrations",
    "application",
    "conclusion",
)

#: Ce que les prédications réelles portent en plus, et que Braga ne nomme pas.
ELEMENTS_OBSERVES = (
    "objectif",       # « Objectif : favorisant un retour aux fondamentaux » (Saint-Esprit)
    "contexte",       # datation, auteur, visée du livre — systématique en introduction
    "definitions",    # « Définition : A- un signe dans la Bible · B- la prière » (Signes)
    "nb",             # l'application immédiate, posée avant le plan (Signes)
    "temoignage",     # « Mon Témoignage » (Signes)
)

#: La liste fermée — **quinze**. C'est elle que la base contraint.
CODES = ELEMENTS + ELEMENTS_OBSERVES

#: **Le seuil du livrable** — un point du plan, écrit par lui. Ni la `proposition` (aucun témoin
#: n'en contient) ni le `theme` (le moteur le remplit d'office).
POINT_CENTRAL = "divisions"

#: Ce qu'un client ou un pasteur écrit naturellement, et qui désigne la même chose.
#:
#: ⚠️ **C'est la moitié utile de la fermeture.** Sans elle, fermer ne ferait que déplacer le
#: problème : au lieu d'un verrou contourné par une majuscule, on aurait un enregistrement
#: refusé pour la même majuscule.
SYNONYMES = {
    "point": "divisions",
    "points": "divisions",
    "division": "divisions",
    "sous_point": "subdivisions",
    "sous_points": "subdivisions",
    "subdivision": "subdivisions",
    "intro": "introduction",
    "transition": "phrase_de_transition",
    "phrase_transition": "phrase_de_transition",
    "question": "phrase_interrogative",
    "phrase_question": "phrase_interrogative",
    "illustration": "illustrations",
    "exemple": "illustrations",
    "exemples": "illustrations",
    "applications": "application",
    "objectifs": "objectif",
    "but": "objectif",
    "definition": "definitions",
    "contexte_historique": "contexte",
    "contexte_litteraire": "contexte",
    "temoignages": "temoignage",
    "ccl": "conclusion",
    "sujet": "titre",
    "theme": "titre",
}


def normaliser(brut: str) -> str:
    """`« Sous-Point »` → `sous_point`. Casse, accents, tirets et espaces repliés.

    Le pasteur tape sur une tablette un vendredi soir : exiger la graphie exacte d'un code
    interne serait lui faire porter une contrainte de programme."""
    plie = unicodedata.normalize("NFD", (brut or "").strip().casefold())
    sans_accent = "".join(c for c in plie if unicodedata.category(c) != "Mn")
    return "_".join(
        morceau for morceau in sans_accent.replace("-", " ").replace("_", " ").split()
    )


def code_canonique(brut: str) -> str | None:
    """Le code retenu, ou **`None` si on ne sait pas le ranger** — jamais une invention.

    Rendre un code par défaut serait pire que refuser : la section du pasteur se rangerait
    silencieusement sous une autre, et il s'en apercevrait en relisant son plan."""
    code = normaliser(brut)
    if code in CODES:
        return code
    return SYNONYMES.get(code)
