"""**Le vocabulaire du corpus, dit en français** — un seul, lu par tous ceux qui montrent.

Ces tables vivaient dans le rendu du document, et elles y étaient bien : c'est là qu'on a
d'abord eu besoin de dire « textuel doctrinal » à un prédicateur. Elles remontent ici le jour
où un **second** lecteur en a eu besoin — l'écran, qui affichait `theologie_propre, en textuel
doctrinal` au pasteur.

> **Un vocabulaire, deux lecteurs.** L'alternative était d'en inventer un troisième pour
> l'écran, et de laisser les deux diverger au premier mot ajouté.

⚠️ **Rien ici n'est une donnée du moteur.** Ce sont des mots pour un humain : aucune décision
ne se prend dessus, aucune empreinte ne s'y compare. Le moteur travaille sur les codes, et il
n'a jamais besoin de savoir comment on les dit.

C'est aussi pourquoi ce module est **pur** — ni base, ni corpus, ni horloge. Il traduit, et
c'est tout.
"""

from __future__ import annotations

#: Les dix loci, tels qu'un prédicateur les nomme. Le libellé du corpus dit « Pneumatologie —
#: le Saint-Esprit » ; on garde la moitié qui parle.
LOCI: dict[str, str] = {
    "theologie_propre": "Dieu lui-même",
    "christologie": "Jésus-Christ",
    "pneumatologie": "le Saint-Esprit",
    "anthropologie": "l'homme",
    "hamartiologie": "le péché",
    "soteriologie": "le salut",
    "ecclesiologie": "l'Église",
    "angelologie": "les anges",
    "demonologie": "Satan et les démons",
    "eschatologie": "les derniers temps",
}

#: Les quatre forces. `resiste` garde son avertissement : c'est celle qui protège.
FORCES: dict[str, str] = {
    "dominant": "au cœur du texte",
    "porte": "présent, en appui",
    "resiste": "⚠ complique ce point",
    "absent": "le texte n'en dit rien",
}

#: « proof-texting » ne se traduit pas, il s'explique : c'est faire dire au texte ce qu'on
#: voulait déjà entendre.
RISQUES: dict[str, str] = {
    "faible": "peu de risque de faire dire au texte plus qu'il ne dit",
    "moyen": "attention à ne pas faire dire au texte plus qu'il ne dit",
    "eleve": "⚠ risque réel de faire dire au texte ce qu'on voulait déjà entendre",
}

PLANS: dict[str, str] = {
    "thematique": "un plan par thème",
    "expositif": "un plan verset par verset",
    "textuel": "un plan collé au texte",
}

MATIERES: dict[str, str] = {
    "doctrinal": "une doctrine",
    "ethique": "une conduite",
    "biographique": "un personnage",
    "historique": "un récit",
    "typologique": "une figure",
    "prophetique": "une annonce",
}


def en_clair(valeur: str, table: dict[str, str]) -> str:
    """Le mot du corpus, rendu en français — **et tel quel si on ne le connaît pas**.

    Un code inconnu s'affiche plutôt que de disparaître : mieux vaut un mot technique qu'un
    trou dans la note de quelqu'un."""
    if valeur in table:
        return table[valeur]
    # Le corpus écrit parfois « Pneumatologie — le Saint-Esprit » : on garde la moitié droite.
    return valeur.split("—")[-1].strip() if "—" in valeur else valeur


def forme_en_clair(plan: str | None, matiere: str | None) -> str:
    """« un plan collé au texte sur une doctrine » — la façon dont le document le dit déjà.

    Vide si le couple est incomplet : un demi-couple ne se dit pas, il se tait."""
    if not plan or not matiere:
        return ""
    return f"{en_clair(plan, PLANS)} sur {en_clair(matiere, MATIERES)}"
