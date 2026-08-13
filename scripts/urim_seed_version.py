"""Semer une traduction française du domaine public — **pour que deux textes puissent se heurter**.

    python scripts/urim_seed_version.py --version darby
    python scripts/urim_seed_version.py --version martin
    python scripts/urim_seed_version.py --version ostervald
    python scripts/urim_seed_version.py --version darby --purge

## Pourquoi plusieurs versions, et pourquoi ce n'est pas un réglage

Un menu « choisissez votre traduction » demanderait au pasteur de configurer. Urim ne fait cela
nulle part : il **signale**. Là où deux traducteurs sérieux rendent le même verset autrement,
il y a quelque chose à dire — et c'est le produit qui doit le dire, au moment où ça compte.

Les témoins ne sont donc pas des préférences, ce sont des angles :

    Segond 1910   équilibrée, la norme des assemblées   · proche du Texte Reçu
    Darby         formelle, serre l'original            · TEXTE CRITIQUE
    Martin 1744   ancienne, tradition genevoise         · TEXTE REÇU
    Ostervald     révisée 1996, encore lue en chaire    · TEXTE REÇU

Darby contre les autres fait remonter les divergences Texte Reçu / texte critique **toutes
seules**, sans apparat, sans modèle, sans rien inventer. C'est la seule approche honnête des
variantes dont ce produit dispose : on n'affirme pas qu'un manuscrit porte ceci — on montre que
deux traducteurs ont lu autrement, et le pasteur vérifie des deux yeux.

Ostervald ne sert pas le même office que Martin, bien que les deux suivent le Texte Reçu :
Martin est un témoin d'archive, Ostervald est **la traduction que beaucoup d'assemblées
évangéliques francophones ont encore entre les mains**. Un écart signalé dans une formulation
que le pasteur ne reconnaît pas se discute ; un écart dans celle qu'il lit dimanche se voit.

## Deux formes de fichier, un seul semis

Les sources n'ont pas toutes le même format et il n'y en avait pas à choisir : getbible ne
propose pas Ostervald (117 versions, aucune correspondance). Le format est donc **déclaré par
la version** et ramené à une forme unique avant le semis — plutôt qu'un second script, qui
aurait divergé du premier dès le premier correctif de versification.

## Ce que ce semis vérifie, et qui est le vrai travail

**La versification.** Les traductions ne numérotent pas pareil. Un écart silencieux ferait
afficher le mauvais verset sous la bonne référence — pire que de ne rien afficher. Le script
compare **chapitre par chapitre** contre la Segond et imprime chaque divergence.

    python scripts/urim_seed_version.py --version martin --rapport   # le rapport seul

Il ne les corrige pas, et il ne les explique pas non plus : `urim_versification.py` aligne sur
le texte, distingue le décalage du glissement, et remplit `urim_corpus_versification_map`.
Ici on **compte**, et le seul travail est de compter à la bonne maille.

**La découpe des versets.** Une source peut avoir raté une séparation et servir deux versets sous
un seul numéro. `_recoudre` rend la coupure quand la source a laissé le numéro dans le texte, et
imprime chaque recousure des deux côtés — ne pas donner à relire un texte biblique qu'on vient de
couper serait le geste que ce dépôt refuse.

⚠️ **Aucun appel de modèle.** Le texte biblique ne vient jamais d'une machine — il vient des
traducteurs. C'est la garantie que le produit tient partout ailleurs : le modèle nomme des
références, la Bible donne le texte.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, insert, select

from app.contexts.urim.engine.normalizer import normalize as normalise
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.database import async_session_factory
from scripts.build_lsg_dataset import ALIAS, CHAPITRES_ATTENDUS
from scripts.urim_seed_books import BOOKS

#: Le même espace de nommage que `seed_urim_corpus.py` — sans quoi deux semis produiraient
#: deux identifiants pour la même chose.
NS = uuid5(NAMESPACE_URL, "https://dorea.app/urim/corpus")


@dataclass(frozen=True)
class Version:
    """⚠️ **Liste fermée, comme les loci et les traditions.**

    Semer « n'importe quelle version que la source propose » ferait entrer dans le corpus des
    traductions dont personne n'a vérifié la licence ni la philosophie. Chacune est ici nommée,
    avec ce qui justifie sa présence — et avec **d'où elle vient**, parce qu'une licence se
    vérifie à une adresse, pas de mémoire."""

    brut: str            # le fichier téléchargé, dans `data/`
    url: str
    forme: str           # 'getbible' | 'osis' — le format du fichier, jamais celui du contenu
    code: str            # le code du dépôt
    label: str
    genre: str           # 'formelle' | 'dynamique'
    pourquoi: str

    @property
    def id(self) -> UUID:
        return uuid5(NS, f"version:{self.code}")


#: `licence_coherente` impose, pour le domaine public : hors ligne autorisé, jamais plafonné.
#: Ce qui ne coûte rien à servir ne se compte pas — et le repli ne peut pas céder.
CATALOGUE = {
    "darby": Version(
        "darby_raw.json", "https://api.getbible.net/v2/darby.json", "getbible",
        "DARBY", "Darby (français)", "formelle",
        "serre l'original sur un texte critique — le contraste utile a la Segond",
    ),
    "martin": Version(
        "martin_raw.json", "https://api.getbible.net/v2/martin.json", "getbible",
        "MARTIN", "Martin (1744)", "formelle",
        "temoin du Texte Recu : sa divergence d'avec Darby EST le signal de variante",
    ),
    # Domaine public verifie a trois adresses qui ne se recopient pas : l'en-tete OSIS du
    # fichier lui-meme (`<rights>Public Domain</rights>`), le registre find.bible/FRAOST
    # (« Public Domain (OPEN) ») et la page de licence d'ebible.org/fra_fob. getbible, lui,
    # n'a pas Ostervald — d'ou une source, et donc un format, differents des deux autres.
    "ostervald": Version(
        "ostervald_raw.xml",
        "https://raw.githubusercontent.com/seven1m/open-bibles/master/fra-ostervald.osis.xml",
        "osis",
        "OST", "Ostervald (revision 1996)", "formelle",
        "la traduction que beaucoup d'assemblees evangeliques francophones lisent encore : "
        "l'ecart se voit dans la formulation que le pasteur reconnait",
    ),
}

#: Les codes OSIS vers le vocabulaire du dépôt — la même table que partout ailleurs, pour qu'il
#: n'existe pas une deuxième façon de nommer un livre.
_PAR_OSIS = {osis: label for _rang, osis, _t, label, _a in BOOKS}

_OSIS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"


def _lire_getbible(cache: Path) -> dict:
    return json.loads(cache.read_text(encoding="utf-8"))


def _lire_osis(cache: Path) -> dict:
    """Ramène un OSIS 2.1.1 à la forme getbible — **un adaptateur, pas un second semis**.

    Le contrôle du canon, le rapport de versification et l'insertion n'ont aucune raison de
    savoir dans quel format la source était écrite.
    """
    racine = ElementTree.parse(cache).getroot()
    livres = []
    for division in racine.iter(f"{_OSIS}div"):
        if division.get("type") != "book":
            continue
        # Le code OSIS inconnu est laissé tel quel : `semer` le refusera par son nom, plutôt
        # que de le faire disparaître ici sans que personne ne l'apprenne.
        osis = division.get("osisID", "")
        livres.append({
            "name": _PAR_OSIS.get(osis, osis),
            "chapters": [
                {
                    "chapter": chapitre.get("osisID", "..").split(".")[1],
                    # ⚠️ `.text` et non `itertext()` : ce fichier ne porte aucune balise dans
                    # ses versets, et si une révision en introduisait (note, titre de péricope),
                    # les aplatir collerait un appareil éditorial dans le texte biblique.
                    "verses": [
                        {
                            "verse": verset.get("osisID", "..").split(".")[2],
                            "text": verset.text or "",
                        }
                        for verset in chapitre.iter(f"{_OSIS}verse")
                    ],
                }
                for chapitre in division.iter(f"{_OSIS}chapter")
            ],
        })
    return {"books": livres}


LECTEURS = {"getbible": _lire_getbible, "osis": _lire_osis}


def _marqueur(numero: int) -> re.Pattern[str]:
    """Un numéro de verset resté dans le texte : entre une fin de phrase et une majuscule."""
    return re.compile(rf"(?<=[.!?:;»])\s?{numero}\s+(?=[A-ZÉÈÀÎÔÇ])")


def _prochaine_couture(versets: dict[int, str]) -> tuple[int, re.Match[str]] | None:
    """Le premier verset qui porte, dans son texte, le numéro d'un verset qui n'existe pas."""
    for numero in sorted(versets):
        if numero + 1 in versets:
            continue
        coupe = _marqueur(numero + 1).search(versets[numero])
        if coupe is not None:
            return numero + 1, coupe
    return None


def _recoudre(donnees: dict) -> None:
    """Rendre à un verset fondu dans son voisin le numéro que la source lui a mangé.

    🔴 Martin porte quatorze chapitres où un numéro de verset manque. Ce n'est pas une convention
    de numérotation — c'est une découpe qui n'a pas eu lieu en amont : le numéro du verset suivant
    est resté **dans** le texte du précédent, et les deux versets sont servis comme un seul.

        2 Rois 7:2   …tu n'en mangeras point.3 Or il y avait a l'entree de la porte quatre
                     hommes lepreux, et ils dirent l'un a l'autre…

    Ce qui autorise à écrire la règle plutôt qu'à la deviner : dans les onze cas où le marqueur
    existe, **il tombe entre les caractères 244 et 252**. La découpe amont a lâché autour de 250
    caractères, toujours au même endroit. Un chiffre à cette place, précédé d'une fin de phrase et
    suivi d'une majuscule, est un numéro de verset et rien d'autre.

    ⚠️ **Aucun mot n'est écrit, ajouté ni réécrit.** On rend une séparation que la source a
    perdue ; le texte reste celui du traducteur, au caractère près. C'est la seule raison pour
    laquelle ce geste a le droit d'exister dans un dépôt où le texte biblique ne vient jamais
    d'une machine.

    Et **on n'invente pas de césure** : sans marqueur, on ne coupe pas. Nombres 26:52 est
    visiblement fondu dans le 51 — la coupure se lit à l'œil, à « Et l'Eternel parla à Moïse ».
    La lire à l'œil est précisément ce qui appartient à un humain, pas à ce script.

    ⚠️ **On part du marqueur, jamais du trou.** Chercher les numéros manquants d'un chapitre
    rate exactement les versets avalés en **fin** de chapitre : la numérotation y reste 1…N sans
    aucun trou, le chapitre est seulement plus court, et rien ici ne sait qu'il devrait l'être
    moins. Esther 7:10 et Osée 1:11 sont dans ce cas, et leur numéro resté dans le texte est la
    seule chose qui les trahisse. C'est aussi pourquoi le trou ne sert plus qu'au **rapport** :
    ce qu'on n'a pas su recoudre doit se lire, mais il ne commande pas la recherche.
    """
    recousus: list[tuple[str, int, int, str, str]] = []
    laisses: list[tuple[str, int, int]] = []

    for livre in donnees["books"]:
        for chapitre in livre["chapters"]:
            versets = {int(v["verse"]): v["text"] for v in chapitre["verses"]}
            touche = False
            # Un verset a pu en avaler plus d'un : on recoupe tant qu'un marqueur se présente,
            # et chaque passage crée le numéro qu'il cherchait — la boucle s'arrête donc.
            while (trouve := _prochaine_couture(versets)) is not None:
                numero, coupe = trouve
                entier = versets[numero - 1]
                tete = entier[: coupe.start()].rstrip()
                queue = entier[coupe.end() :].lstrip()
                versets[numero - 1], versets[numero] = tete, queue
                recousus.append(
                    (livre["name"], int(chapitre["chapter"]), numero, tete, queue)
                )
                touche = True

            laisses.extend(
                (livre["name"], int(chapitre["chapter"]), n)
                for n in sorted(set(range(1, max(versets) + 1)) - set(versets))
            )
            if touche:
                chapitre["verses"] = [
                    {"verse": n, "text": versets[n]} for n in sorted(versets)
                ]

    if not recousus and not laisses:
        return

    print(f"  {len(recousus) + len(laisses)} numeros de verset manquent dans la source :\n")
    # Le contrôle est imprimé VERSET PAR VERSET, des deux côtés de la coupure. Recoudre du texte
    # biblique sans le donner à relire serait exactement le geste que ce dépôt refuse.
    for nom, ch, numero, tete, queue in recousus:
        print(f"    {nom} {ch}:{numero}  RECOUSU")
        print(f"      {numero - 1} ← …{tete[-72:]}")
        print(f"      {numero} → {queue[:72]}…")
    for nom, ch, numero in laisses:
        print(f"    {nom} {ch}:{numero}  laisse tel quel — aucun marqueur, la cesure est une "
              f"decision")
    print()


def _telecharger(version: Version) -> dict:
    """~6 à 10 Mo par version, mis en cache : resemer ne retélécharge pas."""
    cache = Path("data") / version.brut
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        requete = urllib.request.Request(
            version.url,
            headers={"User-Agent": "Mozilla/5.0 (Dorea corpus seed)"},
        )
        with urllib.request.urlopen(requete, timeout=300) as reponse:
            cache.write_bytes(reponse.read())
    return LECTEURS[version.forme](cache)


#: Le schéma de référence — celui que le pasteur écrit, et que tout le produit tient.
REFERENCE = "LSG"


async def _compter(s, code: str) -> dict[tuple[int, int], int]:
    """Combien de versets dans chaque chapitre — lu **en base**, pas dans le fichier source.

    Le rapport décrit alors le corpus tel qu'il est servi, et il reste disponible longtemps
    après le téléchargement : `--rapport` n'a besoin de rien d'autre que la base."""
    return {
        (livre, chapitre): n
        for livre, chapitre, n in await s.execute(
            select(CorpusVerseModel.book_id, CorpusVerseModel.chapter, func.count())
            .join(CorpusVersionModel, CorpusVersionModel.id == CorpusVerseModel.version_id)
            .where(CorpusVersionModel.code == code)
            .group_by(CorpusVerseModel.book_id, CorpusVerseModel.chapter)
        )
    }


def _detail(chapitres: list[tuple[int, int]], montre: int = 6) -> str:
    vus = "  ".join(f"ch. {chapitre} {ecart:+}" for chapitre, ecart in chapitres[:montre])
    reste = len(chapitres) - montre
    return f"{vus}  … et {reste} autres" if reste > 0 else vus


async def rapport(s, code: str) -> None:
    """Le rapport de numérotation — **au chapitre, et c'est tout le sujet**.

    🔴 Il comptait par livre, et il mentait par omission. Lévitique 5 perd sept versets que
    Lévitique 6 regagne ; Exode 7 en perd quatre qu'Exode 8 regagne. Le total du livre tombait
    juste, et le rapport annonçait « versification identique a la Segond » — sur un décalage de
    frontière qui afficherait sept versets sous la mauvaise référence. Neuf livres passaient
    ainsi, dont les décrochages hébreu/latin classiques (Osée 1/2, Michée 4/5, Nahum 1/2).

    D'où les deux sections : celle que la maille précédente ne pouvait pas voir vient
    **d'abord**, parce que c'est celle dont personne ne se méfiait.
    """
    par_rang = {rang: label for rang, _osis, _t, label, _a in BOOKS}
    segond = await _compter(s, REFERENCE)
    autre = await _compter(s, code)
    if not autre:
        raise SystemExit(f"  {code} n'est pas en base — la semer avant d'en demander le rapport.")

    ecarts: dict[int, list[tuple[int, int]]] = {}
    for livre, chapitre in sorted(set(segond) | set(autre)):
        delta = autre.get((livre, chapitre), 0) - segond.get((livre, chapitre), 0)
        if delta:
            ecarts.setdefault(livre, []).append((chapitre, delta))

    if not ecarts:
        print(f"  numerotation identique a la Segond sur les {len(segond)} chapitres.")
        return

    # Un livre dont les écarts s'annulent ne perd aucun verset : il les a **déplacés** d'un
    # chapitre à un autre — souvent le suivant, pas toujours (Martin compense Ésaïe 8 en 64).
    # C'est le cas silencieux, et le seul que l'ancienne maille ratait.
    frontieres = {b: c for b, c in ecarts.items() if sum(d for _ch, d in c) == 0}
    comptes = {b: c for b, c in ecarts.items() if b not in frontieres}

    total_chapitres = sum(len(c) for c in ecarts.values())
    print(f"  {total_chapitres} chapitres numerotent differemment de la Segond, "
          f"dans {len(ecarts)} livres.\n")

    if frontieres:
        print(f"  ⚠️ {len(frontieres)} livres dont le TOTAL tombe juste : le decalage se compense")
        print("     a l'interieur du livre, et un rapport au livre ne le voyait pas.\n")
        for livre in sorted(frontieres):
            print(f"    {par_rang[livre]:<24} {_detail(frontieres[livre])}")
        print()

    if comptes:
        print(f"  {len(comptes)} livres dont le compte de versets change :\n")
        for livre in sorted(comptes, key=lambda b: -abs(sum(d for _ch, d in comptes[b]))):
            somme = sum(d for _ch, d in comptes[livre])
            print(f"    {par_rang[livre]:<24} total {somme:+4}   {_detail(comptes[livre])}")

    print(
        "\n  ⚠️ Ces ecarts ne sont ni corriges ni expliques ici — compter ne dit pas OU le\n"
        f"     verset est parti. `urim_versification.py --version {code}` aligne sur le texte,\n"
        "     et remplir `urim_corpus_versification_map` est une decision."
    )


async def semer(version: Version, purge: bool) -> None:
    donnees = _telecharger(version)
    _recoudre(donnees)
    connus = {label for _, _, _, label, _ in BOOKS}
    rangs = {label: rang for rang, _osis, _t, label, _a in BOOKS}

    lignes: list[dict] = []
    inconnus: set[str] = set()
    chapitres = 0

    async with async_session_factory() as s:
        if purge:
            await s.execute(
                delete(CorpusVerseModel).where(CorpusVerseModel.version_id == version.id)
            )
            await s.execute(
                delete(CorpusVersionModel).where(CorpusVersionModel.id == version.id)
            )
            await s.commit()
            print(f"  {version.code} effacee\n")

        if await s.get(CorpusVersionModel, version.id):
            print(f"  {version.code} deja semee — --purge pour resemer.")
            return

        for livre in donnees["books"]:
            nom = ALIAS.get(livre["name"], livre["name"])
            if nom not in connus:
                inconnus.add(nom)
                continue
            for chapitre in livre["chapters"]:
                chapitres += 1
                for verset in chapitre["verses"]:
                    corps = verset["text"].strip()
                    lignes.append({
                        "version_id": version.id, "book_id": rangs[nom],
                        "chapter": int(chapitre["chapter"]), "verse": int(verset["verse"]),
                        "body": corps, "body_norm": normalise(corps),
                    })

        if inconnus:
            raise SystemExit(f"  livres non reconnus : {sorted(inconnus)}")
        if chapitres != CHAPITRES_ATTENDUS:
            raise SystemExit(f"  {chapitres} chapitres, {CHAPITRES_ATTENDUS} attendus.")

        s.add(CorpusVersionModel(
            id=version.id, code=version.code, language="fr", label=version.label,
            translation_kind=version.genre, license_kind="domaine_public", provider=None,
            offline_allowed=True, metered=False, versification="standard",
        ))
        # ⚠️ La version doit exister **avant** les versets : l'insertion en masse est un ordre
        # SQL direct, elle ne déclenche pas l'écriture de l'objet ORM encore en attente, et la
        # clé étrangère tombe sur 31 000 lignes à la fois.
        await s.flush()
        await s.execute(insert(CorpusVerseModel), lignes)
        await s.commit()
        print(f"  {len(lignes)} versets, {chapitres} chapitres — {version.code} semee\n")

        await rapport(s, version.code)


async def rapport_seul(code: str) -> None:
    async with async_session_factory() as s:
        await rapport(s, code)


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--version", required=True, choices=sorted(CATALOGUE))
    analyseur.add_argument("--purge", action="store_true", help="effacer et resemer")
    analyseur.add_argument(
        "--rapport", action="store_true",
        help="le rapport de numerotation seul, sans rien semer ni telecharger",
    )
    arguments = analyseur.parse_args()
    version = CATALOGUE[arguments.version]
    if arguments.rapport:
        asyncio.run(rapport_seul(version.code))
        return
    asyncio.run(semer(version, arguments.purge))


if __name__ == "__main__":
    main()
