"""Le banc de la porte — **le chiffre qui compte est le faux refus, pas le rejet**.

    python scripts/urim_banc_porte.py

Un utilisateur qui sait avoir une IA en face de lui lui enverra sa dissertation de philosophie.
Ce n'est pas un problème de sûreté : le modèle n'a **aucun canal de sortie en prose** — `axes`
rend des codes, `passages` rend des références vérifiées contre les 31 170 versets. Personne
n'extraira une dissertation d'Urim. C'est un problème de coût, de dignité et de propreté du
corpus.

## L'asymétrie que ce banc mesure

**Refuser un pasteur légitime coûte infiniment plus cher que servir un étudiant.**

Les saisies réelles du Pasteur X ne ressemblent pas à des « intentions de prédication » :
*« l'amour fraternel n'existe plus dans l'eglise »* est une plainte, *« Dieu est l'auteur et le
consommateur de notre foi »* est bancal, *« je veux faire un culte sur l'adultère dans »* est
tronqué. Un portier naïf en refuse au moins un.

Et le précédent est dans ce dépôt : la validation qui exigeait « exactement un dominant » a
sauté **803 unités**. Les gardes trop strictes ont toujours coûté plus cher ici que la
permissivité.

Le banc rend donc trois taux, et **seul le premier est un échec** :

    faux refus sur les réelles      DOIT être 0
    faux refus sur les limites      doit être 0 — histoire, pastorale, saisie bancale
    rejet des étrangères            tant mieux s'il est haut, sans importance s'il est bas

## Ce qu'il n'y a pas ici

Pas de portier séparé, pas de pré-filtre lexical. La règle vit dans les deux invites qui ont
déjà un contrat fermé — `axes` et `passages` savent rendre une liste vide. Zéro appel
supplémentaire, aucune surface nouvelle, et le refus s'exprime dans le vocabulaire qui existe.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.core.config import get_settings
from scripts.urim_curate_pericopes import ESSAIS, INTERVALLE, Cadence

REELLE, LIMITE, ETRANGERE = "reelle", "limite", "etrangere"


@dataclass(frozen=True)
class Cas:
    texte: str
    famille: str
    note: str = ""


_BANC: tuple[Cas, ...] = (
    # ----------------------------------------------------- les vraies saisies du Pasteur X
    Cas("Dieu est l'auteur et le consommateur de notre foi, sur l'autel Divin", REELLE,
        "bancale, et c'est une vraie predication"),
    Cas("Celui qui maintient notre Foi jusqu'a l'ascension", REELLE),
    Cas("l'amour fraternel n'existe plus dans l'eglise", REELLE,
        "une PLAINTE, pas une intention — le piege du portier naif"),
    Cas("le fils prodigue rentre chez son pere", REELLE, "une scene racontee de memoire"),
    Cas("L'amour fraternel", REELLE, "maquette urim_conversation.html"),
    Cas("on prie pour les malades et rien ne change", REELLE,
        "documente dans _SYSTEME_AXES"),
    Cas("je veux faire un culte sur l'adultère dans", REELLE,
        "TRONQUEE, documentee dans _SYSTEME_AXES — doit passer quand meme"),
    Cas("je veux prêcher sur le pardon", REELLE),

    # ----------------------------------------------------- limites : doivent passer aussi
    Cas("les esclaves hebreux ne portaient pas de chaussures", LIMITE,
        "de l'HISTOIRE, pas de l'Ecriture — et c'est la question qui a ouvert la concordance"),
    Cas("comment annoncer un deces a une assemblee", LIMITE,
        "pastoral plutot qu'exegetique — la vie d'une assemblee"),
    Cas("que veut dire upodema", LIMITE, "un mot grec seul"),
    Cas("la dime est-elle encore d'actualite", LIMITE, "une question doctrinale directe"),
    Cas("mon eglise se vide depuis six mois", LIMITE, "un constat, pas un texte"),

    # ----------------------------------------------------- etrangeres : doivent revenir vides
    Cas("Dissertez sur le cogito cartesien et la place du doute chez Descartes", ETRANGERE,
        "LE CAS DE LA QUESTION : l'etudiant qui envoie son exercice"),
    Cas("Resolvez l'equation differentielle y'' + 3y' + 2y = 0", ETRANGERE),
    Cas("Donne-moi une recette de poulet braise a l'ivoirienne", ETRANGERE),
    Cas("def fibonacci(n): return n if n < 2 else fibonacci(n-1)+fibonacci(n-2)", ETRANGERE),
    Cas("Quels sont les symptomes du paludisme chez l'enfant", ETRANGERE),
    Cas("Redige une lettre de motivation pour un poste de comptable", ETRANGERE),
    Cas("Ma voiture 406, a besoin de reparation , jefgf Paradis", ETRANGERE,
        "le micro reste ouvert — documente dans engine/state.py"),
)


@dataclass
class Verdict:
    cas: Cas
    loci: int
    passages: int

    @property
    def sert(self) -> bool:
        """Urim a servi quelque chose — un locus, ou un passage."""
        return self.loci > 0 or self.passages > 0


async def _passer(ia: MistralAssistant) -> list[Verdict]:
    """⚠️ **Séquentiel, avec cadence et reprises — et ce n'est pas de la prudence.**

    🔴 Le premier passage a tiré vingt cas en parallèle pendant qu'un lot de curation tournait :
    429 dès le sixième. Tout ce qui a suivi est revenu vide, et le banc annonçait une porte
    parfaite — zéro étrangère servie, et zéro pasteur servi non plus.

    **Une panne de débit ressemble exactement à un refus.** Un banc sans cadence ne mesure pas
    la porte, il mesure le quota — et il rend le verdict le plus flatteur possible."""
    cadence = Cadence(INTERVALLE)
    verdicts: list[Verdict] = []
    for cas in _BANC:
        for essai in range(ESSAIS):
            avant = ia.echecs
            await cadence.attendre()
            loci = await ia.axes(cas.texte)
            await cadence.attendre()
            passages = await ia.passages(cas.texte)
            if ia.echecs == avant:
                break
            await asyncio.sleep(2**essai)
        else:
            print(f"  ECHEC  {cas.famille:<10} — le modele n'a pas repondu : {cas.texte[:40]}")
            continue
        v = Verdict(cas, len(loci), len(passages))
        verdicts.append(v)
        marque = "sert " if v.sert else "vide "
        print(f"  {marque} {cas.famille:<10} {v.loci}L {v.passages}P   {cas.texte[:48]}")
    return verdicts


def _rapport(verdicts: list[Verdict]) -> None:
    def part(famille: str, servis: bool) -> str:
        lot = [v for v in verdicts if v.cas.famille == famille]
        if not lot:
            return "—"
        n = sum(1 for v in lot if v.sert is servis)
        return f"{n}/{len(lot)}  ({100 * n / len(lot):.0f} %)"

    print("\n" + "=" * 74)
    print("  LE SEUL CHIFFRE QUI EST UN ECHEC")
    print("=" * 74)
    faux_refus = [
        v for v in verdicts if v.cas.famille in (REELLE, LIMITE) and not v.sert
    ]
    print(f"  faux refus sur les vraies saisies    {part(REELLE, False)}")
    print(f"  faux refus sur les limites           {part(LIMITE, False)}")
    print("  → refuser un pasteur coute infiniment plus cher que servir un etudiant")

    print("\n" + "=" * 74)
    print("  CE QUI EST AGREABLE, SANS PLUS")
    print("=" * 74)
    print(f"  etrangeres ecartees                  {part(ETRANGERE, False)}")

    if faux_refus:
        print("\n" + "=" * 74)
        print("  LES PASTEURS QU'ON AURAIT RENVOYES")
        print("=" * 74)
        for v in faux_refus:
            print(f"\n  « {v.cas.texte} »   [{v.cas.famille}]")
            if v.cas.note:
                print(f"    {v.cas.note}")

    servies = [v for v in verdicts if v.cas.famille == ETRANGERE and v.sert]
    if servies:
        print("\n" + "=" * 74)
        print("  LES ETRANGERES SERVIES  (genant, pas grave)")
        print("=" * 74)
        for v in servies:
            print(f"  {v.loci}L {v.passages}P   « {v.cas.texte[:56]} »")


async def main() -> None:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        print("MISTRAL_API_KEY absente — rien a mesurer.")
        return
    print(f"Modele : {reglages.mistral_model}   —   {len(_BANC)} cas\n")
    _rapport(await _passer(
        MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)
    ))


if __name__ == "__main__":
    asyncio.run(main())
