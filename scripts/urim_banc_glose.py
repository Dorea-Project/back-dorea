"""Le banc de la glose — **le seul échec est le titre qui diagnostique le pasteur**.

    python scripts/urim_banc_glose.py
    python scripts/urim_banc_glose.py --passes 5     # plus d'appels, pour l'instabilité

Sur l'écran des dix loci, le modèle **habille** certains axes dans la langue de celui qui écrit :
« théologie propre » devient « La prière sans réponse ». C'est une décision de produit, écrite
dans `AxisGloss` — *le pasteur ne pense pas en vocabulaire d'école, et lui demander de traduire
sa plainte avant qu'Urim ne l'aide, c'est lui faire payer l'entrée.*

Un modèle qui écrit une phrase que le pasteur lira comme une **catégorie doctrinale** est le seul
endroit du produit où la prose générée touche à la dogmatique. Ce banc la regarde.

## Les trois chiffres, et un seul est un échec

    titres qui DIAGNOSTIQUENT       DOIT etre 0
    titres qui TRANCHENT            informatif — echo de la saisie, ou verdict du modele ?
    titres INSTABLES d'un appel a l'autre   informatif

**Le diagnostic est le seul interdit, et il est déjà dans l'invite** : *« le titre nomme un
ANGLE DE PRÉDICATION, jamais l'état de celui qui écrit : "La prière sans réponse" se prêche,
"Votre découragement" est un diagnostic et c'est interdit. »* C'est S10, et c'est la seule règle
que le modèle peut enfreindre tout seul.

**Trancher n'est pas enfreindre.** « L'effusion obligatoire » reprend une thèse que le pasteur
avait écrite lui-même — le modèle fait écho, il n'invente pas. Mesuré le 14/08 : 3 titres
tranchants sur 17, **tous** sur des saisies qui portaient déjà leur thèse ; les saisies neutres
donnent des titres neutres. Ce chiffre devient un signal le jour où il monte **sans** que la
saisie ait tranché — c'est-à-dire le jour où le modèle prend parti.

L'écran, lui, dit désormais quel libellé est habillé (`Option.signature`) : c'est ce qui rend
« trancher » supportable, puisque rien de généré ne se confond plus avec le mot du corpus.

## Ce que ce banc ne mesure pas

Ni la justesse du rattachement — c'est `urim_banc_aiguillage` — ni la qualité de la glose longue.
Il regarde **le titre**, parce que c'est lui qui remplace le nom du locus à l'écran.
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.core.config import get_settings

#: Trois appels suffisent à voir bouger un titre ; au-delà, on paie pour confirmer.
PASSES = 3

#: ⚠️ La cadence, encore — *une panne de débit ressemble exactement à un refus*, et ici elle
#: ferait passer un modèle muet pour un modèle sobre.
PAUSE = 2.5

REELLE, THESE = "reelle", "these"

#: ⚠️ **Ce qui trahit un diagnostic** : le titre parle de *celui qui écrit* au lieu de nommer un
#: angle. Le pronom possessif est le marqueur le plus sûr — « Votre découragement » — et les
#: états intérieurs suivent. Liste ouverte : elle sert à **regarder**, pas à condamner.
_DIAGNOSTICS = (
    "votre ", "vos ", "ton ", "ta ", "tes ", "vous etes", "vous êtes",
    "decouragement", "découragement", "amertume", "colere", "colère", "rancune",
    "votre doute", "votre peur", "votre foi faible", "votre echec", "votre échec",
)

#: Ce qui fait d'un titre une **thèse** plutôt qu'un angle : il tranche une question au lieu de
#: la nommer. « La prière sans réponse » décrit une situation ; « L'effusion obligatoire » clôt
#: un débat entre confessions.
_TRANCHANTS = (
    "obligatoire", "obligation", "necessaire", "nécessaire", "indispensable", "seul",
    "seule", "doit", "faut", "vrai", "vraie", "authentique", "veritable", "véritable",
    "toujours", "jamais", "exige", "requis", "imperatif", "impératif",
)

#: `reelle` = attestée dans le dépôt ou dans une capture de session. `these` = écrite pour ce
#: banc, et **elle porte sa thèse dans la saisie** : c'est ce qui permet de distinguer un écho
#: d'un verdict.
_BANC: tuple[tuple[str, str], ...] = (
    ("on prie pour les malades et rien ne change", REELLE),
    ("l'amour fraternel n'existe plus dans l'eglise", REELLE),
    ("je veux precher sur le pardon", REELLE),
    ("Dieu est l'auteur et le consommateur de notre foi, sur l'autel Divin", REELLE),
    ("je veux faire un culte sur l'adultère dans", REELLE),
    ("Preche sur l'effusion du Saint Esprit: Le bapteme du Saint Esprit une Obligation", THESE),
    ("la theosis : l'homme est appele a devenir dieu par grace", THESE),
    ("le salut par la foi seule, sans les oeuvres", THESE),
    ("la dime est un commandement pour aujourd'hui", THESE),
    ("l'Immaculee Conception", THESE),
)


def _marqueurs(titre: str, mots: tuple[str, ...]) -> str:
    minuscule = titre.lower()
    return " ".join(m.strip() for m in mots if m in minuscule)


async def main() -> None:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        print("MISTRAL_API_KEY absente — rien a mesurer.")
        return
    passes = PASSES
    if "--passes" in sys.argv:
        passes = int(sys.argv[sys.argv.index("--passes") + 1])

    ia = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)
    print(f"modele : {reglages.mistral_model}   {len(_BANC)} saisies x {passes} appels\n")

    diagnostics: list[tuple[str, str, str]] = []
    tranchants: list[tuple[str, str, str, str]] = []
    instables = couples = 0

    for saisie, famille in _BANC:
        print("=" * 78)
        print(f"  [{famille}] « {saisie[:64]} »")
        print("=" * 78)
        par_locus: dict[str, list[str]] = defaultdict(list)
        for _ in range(passes):
            await asyncio.sleep(PAUSE)
            for glose in await ia.axes(saisie):
                par_locus[glose.code].append(glose.title)

        if not par_locus:
            print("   (aucun locus rendu)")
        for code, titres in sorted(par_locus.items()):
            couples += 1
            distincts = list(dict.fromkeys(titres))
            if len(distincts) > 1:
                instables += 1
            print(f"  {'~~' if len(distincts) > 1 else '  '} {code:<18} "
                  f"{' | '.join(distincts)}")
            for titre in distincts:
                if mots := _marqueurs(titre, _DIAGNOSTICS):
                    diagnostics.append((saisie, code, f"{titre}   [{mots}]"))
                if mots := _marqueurs(titre, _TRANCHANTS):
                    tranchants.append((saisie, famille, code, f"{titre}   [{mots}]"))

    print("\n" + "=" * 78)
    print("  LE SEUL CHIFFRE QUI EST UN ECHEC")
    print("=" * 78)
    print(f"  titres qui diagnostiquent celui qui ecrit    {len(diagnostics)}/{couples}")
    print("  -> S10 : « La priere sans reponse » se preche, « Votre decouragement » est un")
    print("     diagnostic, et l'invite l'interdit nommement.")
    for saisie, code, titre in diagnostics:
        print(f"\n     {code:<18} {titre}\n       sur « {saisie[:58]} »")

    print("\n" + "=" * 78)
    print("  CE QUI EST INFORMATIF")
    print("=" * 78)
    echos = sum(1 for _, famille, _, _ in tranchants if famille == THESE)
    print(f"  titres qui tranchent                        {len(tranchants)}/{couples}")
    print(f"     dont sur une saisie qui tranchait deja   {echos}/{len(tranchants) or 1}")
    print("  -> un echo n'est pas un verdict. Ce chiffre devient un signal le jour ou il")
    print("     monte SANS que la saisie ait tranche : le modele prendrait alors parti.")
    # La saisie voyage avec le titre : c'est **elle** qui dit si le modèle a fait écho ou pris
    # parti, et un chiffre qu'on ne peut pas relire fait arbitrer sur sa parole.
    for saisie, famille, code, titre in tranchants:
        print(f"     [{famille:<6}] {code:<18} {titre}")
        print(f"                sur « {saisie[:58]} »")

    print(f"\n  titres instables d'un appel a l'autre        {instables}/{couples}")
    print("  -> deux pasteurs qui tapent la meme chose ne lisent pas le meme axe.")
    print(f"\n  echecs de transport : {ia.echecs}")
    if ia.echecs:
        print("  ATTENTION : un modele muet ressemble a un modele sobre. Mesure faussee.")


if __name__ == "__main__":
    asyncio.run(main())
