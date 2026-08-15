"""Les collisions de sens — **là où plusieurs traducteurs sérieux n'ont pas lu la même chose**.

    python scripts/urim_collisions.py                     # le rapport
    python scripts/urim_collisions.py --lire 15           # les prises, les temoins en regard
    python scripts/urim_collisions.py --tout              # TOUT ce qui est retenu, en entier
    python scripts/urim_collisions.py --forme segond_seule
    python scripts/urim_collisions.py --bandes            # de quoi recalibrer le seuil
    python scripts/urim_collisions.py --ecrire            # remplit urim_corpus_collision

Un menu « choisissez votre traduction » demanderait au pasteur de configurer. Urim signale,
partout ailleurs — et une divergence entre traductions du domaine public **est** un signalement :
elle marque un endroit où l'original est ambigu, ou un mot que le français ne rend pas d'une
seule façon.

C'est la seule approche honnête des divergences dont ce produit dispose. On n'affirme pas qu'un
manuscrit porte ceci — on montre que des traducteurs ont lu autrement, et le pasteur vérifie des
deux yeux.

⚠️⚠️ **UNE COLLISION N'EST PAS UNE VARIANTE TEXTUELLE.** Voir plus bas : ce n'est pas une
prudence de rédaction, c'est une propriété **mesurée** du détecteur.

## Tous les versets diffèrent : quatre artefacts avant le premier signal

Darby serre l'original, Segond arrondit, Martin écrit en 1744, Ostervald révise en 1996.
Comparer des chaînes signalerait les 31 000 versets. Chaque passage du détecteur a écarté une
famille de faux signaux, et chacune n'est apparue **qu'en lisant les prises de la précédente** :

1. **La divergence maximale visait à l'envers.** Les dix premières étaient « 72 000 » contre
   « soixante-douze mille », et 1 Chroniques 6:4 où les deux textes ne sont pas le même verset.
   Toutes ne se recouvrent presque pas — alors qu'une collision de sens est l'inverse : deux
   rendus manifestement du même verset qui ne diffèrent que sur **un mot lourd**. D'où
   `RECOUVREMENT_MINIMUM`.
2. **La translittération.** *Diphat/Diphath*, *Léschem/Léshem*. Les mots rares de la Bible sont
   massivement des noms propres, et l'IDF les met tous au plafond. D'où `_apparie`, sur la
   proximité graphique — et, pour ce qui lui échappait encore, `_nom_propre`.
3. **Le lexique amputait la comparaison.** En ne gardant que les mots connus de l'IDF — bâti sur
   la seule Segond — la graphie de Darby disparaissait *avant* d'être comparée. **Peser et
   comparer ne demandent pas le même ensemble de mots.**
4. **La reformulation.** 2 650 versets à égalité au plafond. Une collision est une
   **substitution** : deux mots d'écart, un de chaque côté. D'où `SUBSTITUTION_MAXIMUM`.

⚠️ **La versification est appliquée.** Sans elle, le Psautier entier ressortirait, puisque
Martin ne numérote pas les suscriptions — le premier signal aurait été du bruit pur sur le livre
le plus prêché de la Bible.

---

## 🔴 Ce que la lecture à quatre a démenti

L'hypothèse était belle : *Darby suit un texte critique, les trois autres le Texte Reçu ; donc
« Darby seul contre les trois autres » est un écart d'édition, c'est-à-dire un signal de
variante sans apparat.* **Les prises l'ont réfutée sur deux plans.**

**La ligne des familles ne passe pas là.** Sondé sur les lieux classiques :

    1 Jean 5:7 (comma johanneum)   LSG omet · DARBY omet · OST porte  · MARTIN porte
    Romains 8:1 (la clause)        LSG omet · DARBY omet · OST porte  · MARTIN porte
    Apocalypse 22:19               LSG arbre · DARBY arbre · OST livre · MARTIN livre
    Marc 1:2                       LSG Esaie · DARBY Esaie · OST les prophetes · MARTIN idem

La Segond 1910 n'est pas « proche du Texte Reçu » : elle est **éclectique**, et suit le texte
critique à peu près autant que Darby. Ce qui reste de « Darby seul » dans le Nouveau Testament —
151 prises — se lit *« aisé »* contre *« facile »* (Mt 9:5, Lc 5:23), *« festins »* contre
*« repas »* (Mt 23:6), *« modèles »* contre *« exemple »* (Jc 5:10) : c'est le style formel de
Darby, pas une édition.

**Et le détecteur ne peut structurellement pas voir une variante.** Ce à quoi une variante
ressemble chez ces témoins, c'est une **proposition entière** présente ou absente (la clause de
Rm 8:1, la doxologie de Mt 6:13, le comma johanneum) — donc une *reformulation*, précisément ce
que `SUBSTITUTION_MAXIMUM` existe pour rejeter ; ou un **verset entièrement absent** (Mt 23:14,
Ac 8:37, Ac 15:34 chez Darby), qui n'est pas une divergence mais un silence.

⇒ **La forme décrit qui lit avec qui, et ne dit jamais pourquoi.** Il a existé ici un champ « la
séparation suit la ligne des éditions » : il est tombé sur la mesure. Ce qui le remplace est
`urim_corpus_version.text_family`, un fait porté par le témoin, affiché à côté de lui, dont le
produit ne tire **aucune** conclusion. `urim_corpus_textual_variant` garde son monopole entier —
elle se remplit depuis un apparat critique, par un humain qui signe.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, insert, select

from app.contexts.urim.engine.normalizer import normalize
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusCollisionModel,
    CorpusCollisionWitnessModel,
    CorpusIdfModel,
    CorpusVerseModel,
    CorpusVersificationMapModel,
    CorpusVersionModel,
)
from app.core.database import async_session_factory
from scripts.urim_seed_books import BOOKS

#: Le schéma de référence — celui que le pasteur écrit, et que tout le produit tient.
REFERENCE = "LSG"

#: Le même espace de nommage que les autres semis du corpus : deux passages du détecteur sur le
#: même verset doivent rendre le même identifiant, sinon `--ecrire` fabrique des doublons
#: invisibles pour tout ce qui pointe dessus.
NS = uuid5(NAMESPACE_URL, "https://dorea.app/urim/corpus")

#: La preuve que c'est bien le même verset, exigée **avant** de peser quoi que ce soit.
RECOUVREMENT_MINIMUM = 0.5

#: Deux mots assez proches sont la même chose écrite autrement. On ne tient pas une liste de
#: noms propres : elle serait fausse le jour où un traducteur en ajoute un.
PROXIMITE_GRAPHIQUE = 0.8

#: Un verset trop court n'a pas assez de mots pleins pour qu'une divergence veuille dire quoi
#: que ce soit — « Jésus pleura » diverge à 100 % ou à 0 %, jamais entre les deux.
MOTS_PLEINS_MINIMUM = 5

#: 🔴 **Le quatrième artefact : la reformulation.**
#:
#: Le poids seul ne discriminait plus rien — tout mot rare atteint le plafond de l'IDF, et
#: 2 650 versets s'y retrouvaient à égalité. Les prises l'ont montré : *« consacrèrent »* contre
#: *« sanctifièrent »* est **un mot pour un autre**, un choix de traducteur sur un verbe
#: théologique. Néhémie 10:34, où Darby refait la phrase entière, en aligne quatre ou cinq et
#: n'apprend rien.
#:
#: Une collision de sens est une **substitution** : deux mots d'écart, un de chaque côté. Ce
#: n'est pas un réglage de sensibilité, c'est la définition de ce qu'on cherche.
#:
#: ⚠️ Depuis la lecture à quatre, ce seuil ne rejette plus le **verset** : il fait **abstenir le
#: témoin** qui reformule. Voir `Lecture`.
SUBSTITUTION_MAXIMUM = 2

#: 🔴 **Calibré en relisant les bandes, pas décrété — et `--bandes` sert à le refaire.**
#:
#: Le 99ᵉ centile, qui tenait ici, est **dégénéré** : le 98ᵉ et le 99ᵉ valent tous deux 10.347,
#: le plafond de l'IDF. Trois bandes relues :
#:
#:     99e   93 prises    le plafond ; rien à distinguer au-dessus
#:     95e  217 prises    ~4 sur 5 sont de vraies collisions de sens
#:     90e  383 prises    la bande ajoutee tombe a ~1 sur 2 — « quant », « joignit », « fuyons »
#:
#: On s'arrête au 95ᵉ **parce que la bande suivante a été lue**, et qu'elle fait entrer des mots
#: outils et des variations de syntaxe. Un centile, et non un score : « les 5 % où le désaccord
#: pèse le plus lourd » se défend, « au-dessus de 0,6 » ne se défend pas.
CENTILE = 95.0

#: Les trois formes du désaccord. Elles **décrivent une répartition** ; aucune ne nomme une
#: cause, et c'est ce que la mesure a imposé (voir l'en-tête).
FORMES = ("temoin_isole", "partage", "segond_seule")

#: 🔴 **Le cinquième artefact : l'élision orpheline** — trouvé, comme les quatre autres, en
#: relisant les prises. Deux des 221 retenues portaient un mot d'**une seule lettre** : `[n]`
#: dans Daniel 11:42, `[d]` dans Nombres 7:81.
#:
#: Un fragment d'élision ne paraît presque nulle part ailleurs — donc au plafond de l'IDF, donc
#: exactement dans la zone que le seuil retient. Le même mécanisme que les noms propres, sur ce
#: qui n'est même pas un mot.
#:
#: ⚠️ **J'ai d'abord attribué ces fragments à une espace après l'apostrophe. La mesure l'a
#: démenti, et la vraie cause est ailleurs — trois causes, en fait :**
#:
#:     -t-il / -t-elle   1 548 versets sur les 4 temoins : le normaliseur coupe aux traits
#:                       d'union, et le « t » euphonique reste seul. Ce n'est PAS un defaut du
#:                       corpus, c'est une propriete du francais.
#:     [l']homme         41 versets, Darby seule : ses crochets d'edition separent l'article
#:                       elide du mot qu'il porte.
#:     « N'y a t-il »    quelques versets ou la source a mis une espace a la place du premier
#:                       trait d'union. Vrai defaut, non repare — hors du sujet de ce module.
#:
#: L'espace après l'apostrophe existait bel et bien, mais **dans `data/ls1910.json`** — trente
#: versets, réparés depuis (`build_lsg_dataset.recoller_les_elisions`, gardés par
#: `tests/test_lsg_dataset.py`). La base de développement, elle, avait été recousue à la main :
#: le détecteur ne pouvait donc pas les voir, et j'ai lu la bonne conclusion sur la mauvaise
#: preuve.
#:
#: **Ce qui reste vrai, et pourquoi ce garde-fou tient toujours** : quelle que soit la cause, un
#: fragment d'élision ne porte aucun sens, et une collision ne se bâtit pas dessus.
_ELISIONS_ORPHELINES = frozenset({
    "c", "d", "j", "l", "m", "n", "s", "t", "qu", "jusqu", "lorsqu", "puisqu", "quoiqu",
})

#: L'article élidé en tête de mot. Les apostrophes sont écrites en échappement et reprennent
#: **exactement** celles du normaliseur partagé : sur un clavier ces glyphes sont indiscernables,
#: et une relecture ne verrait pas qu'il en manque un.
_ELISION_INITIALE = re.compile(
    "^[a-zA-Z]"
    "['"        # apostrophe droite — celle des claviers
    "\u2019"    # apostrophe typographique — celle des traitements de texte
    "\u02bc"    # lettre modificatrice, fréquente dans les corpus importés
    "\u02bb"    # sa jumelle tournée
    "`]"        # accent grave, tapé par erreur à la place de l'apostrophe
)


@dataclass(frozen=True)
class Lecture:
    """Ce qu'un témoin fait de ce mot — **y compris ne rien en dire**.

    🔴 `muet` est une valeur, pas une absence. Un témoin qui ne tient pas le verset, ou qui le
    reformule d'un bout à l'autre, **ne se prononce pas** : chez lui, l'absence du mot ne veut
    rien dire. L'ignorer le ferait compter pour un accord — le contraire exact de ce qu'il a
    fait, et la façon la plus simple de transformer « un seul diverge » en « la Segond est
    seule »."""

    code: str
    stance: str          # accorde | diverge | muet
    reading: str | None  # le mot qu'il écrit à la place, quand l'appariement est propre
    body: str


@dataclass(frozen=True)
class Collision:
    livre: int
    chapitre: int
    verset: int
    mot: str
    poids: float
    forme: str
    lectures: tuple[Lecture, ...]

    @property
    def id(self) -> UUID:
        return uuid5(NS, f"collision:{self.livre}:{self.chapitre}:{self.verset}:{self.mot}")

    @property
    def divergents(self) -> tuple[str, ...]:
        return tuple(le.code for le in self.lectures if le.stance == "diverge")

    @property
    def muets(self) -> tuple[str, ...]:
        return tuple(le.code for le in self.lectures if le.stance == "muet")


def _apparie(mot: str, autres: set[str]) -> bool:
    """Le même mot sous une autre graphie.

    ⚠️ `autres` est le vocabulaire **entier** de l'autre rendu, jamais sa part connue du
    lexique. C'est le défaut qui a fait survivre les noms propres à leur propre filtre :
    l'IDF est bâti sur la Segond, « leshem » n'y figure pas, il disparaissait donc avant la
    comparaison et « léschem » ressortait comme un mot sans équivalent.

    Le test de longueur n'est **pas une heuristique, c'est une borne**. Le ratio de
    `SequenceMatcher` vaut `2·M / T` où `M` est le nombre de caractères appariés — au plus la
    longueur du plus court des deux mots. Un couple qui échoue à cette borne ne pouvait pas
    atteindre le seuil, et l'écarter ne change donc aucun résultat : il rend seulement une
    comparaison quadratique abordable sur les dix-huit millions de couples que fait la Bible
    entière."""
    taille = len(mot)
    for autre in autres:
        total = taille + len(autre)
        if 2 * min(taille, len(autre)) < PROXIMITE_GRAPHIQUE * total:
            continue
        if SequenceMatcher(None, mot, autre).ratio() >= PROXIMITE_GRAPHIQUE:
            return True
    return False


def _nom_propre(mot: str, corps: str) -> bool:
    """La majuscule en contexte — **le deuxième artefact, ce qu'il en restait**.

    `_apparie` attrape les graphies voisines (*Kirjath/Kiriath*) et laisse passer les autres :
    *Hakkots/Kots*, *Achrach/Akhrakh*, *Kaïnam* absent chez trois témoins. Or les mots rares de
    la Bible sont massivement des toponymes et des patronymes, et ils occupent exactement le
    plafond de l'IDF, c'est-à-dire la zone que le seuil retient. Environ deux prises sur dix en
    étaient.

    La majuscule les distingue sans qu'on ait à tenir une liste : **un mot rare capitalisé en
    milieu de phrase est une translittération.** 3 292 versets écartés là-dessus.

    Trois précautions, chacune payée par une prise :

    **On lit la majuscule dans la Segond seule.** Martin capitalise les noms communs — *Roi*,
    *Prophète*, *Scribes*, *Ecriture* — et la juger d'après elle écarterait la moitié du
    vocabulaire théologique.

    **L'élision se retire avant de regarder.** Le normaliseur colle l'article au mot (`d'Ijjé` →
    `dijje`, S21) : sans ce retrait, la majuscule n'est plus en tête et le nom passait.

    **Un mot en tête de phrase ne conclut rien.** « Nommons un chef » (Nb 14:4) est une vraie
    collision, « Nocha le quatrième » un nom propre, et la position ne les sépare pas. Le doute
    profite donc à la prise, et le résidu se voit dans `--tout`.

    ⚠️ Ce filtre ne peut pas manger « Dieu », « l'Éternel » ni « l'Esprit », bien qu'ils soient
    capitalisés : ces mots-là sont fréquents, leur poids est très en dessous du seuil, et ils
    n'atteignent jamais la zone retenue."""
    for trouve in re.finditer(r"\S+", corps):
        suite = trouve.group(0)
        if mot not in normalize(suite).split():
            continue
        nu = _ELISION_INITIALE.sub("", suite)
        majuscules = [i for i, c in enumerate(nu) if c.isupper()]
        if not majuscules:
            continue
        avant = corps[: trouve.start()].rstrip()
        debut_de_phrase = not avant or avant[-1] in ".!?:;»\""
        if debut_de_phrase and majuscules == [0]:
            continue
        return True
    return False


def _mots(norme: str, poids: dict[str, float]) -> tuple[set[str], set[str]]:
    """`(tout le vocabulaire, sa part pesable)` — les deux ensembles du troisième artefact.

    ⚠️ **Ils ne servent pas à la même chose et ne doivent pas être confondus.** On *pèse* sur
    la part connue du lexique, on *compare* sur le vocabulaire entier : l'IDF est bâti sur la
    seule Segond, donc restreindre la comparaison au lexique ferait disparaître la graphie de
    Darby avant qu'on ait pu l'apparier."""
    tous = set(norme.split())
    return tous, {m for m in tous if m in poids}


def _ecart(
    mots_a: tuple[set[str], set[str]], mots_b: tuple[set[str], set[str]]
) -> tuple[set[str], set[str]] | None:
    """Les mots sur lesquels deux rendus du même verset se séparent — ou `None`.

    `None` veut dire **« ce témoin ne se prononce pas »**, et il y a trois façons de ne pas se
    prononcer : trop peu de mots pleins pour que la comparaison veuille dire quelque chose, un
    recouvrement trop faible pour qu'on tienne le même verset, ou une reformulation.

    Rend `(perdus, gagnés)` : les mots de la Segond sans équivalent chez l'autre, et
    réciproquement."""
    (tous_a, pesables_a), (tous_b, pesables_b) = mots_a, mots_b
    if len(pesables_a) < MOTS_PLEINS_MINIMUM or len(pesables_b) < MOTS_PLEINS_MINIMUM:
        return None

    commun, union = pesables_a & pesables_b, pesables_a | pesables_b
    if not union or len(commun) / len(union) < RECOUVREMENT_MINIMUM:
        return None

    perdus = {m for m in pesables_a - pesables_b if not _apparie(m, tous_b)}
    gagnes = {m for m in pesables_b - pesables_a if not _apparie(m, tous_a)}
    if len(perdus) + len(gagnes) > SUBSTITUTION_MAXIMUM:
        return None
    return perdus, gagnes


def _forme(divergents: tuple[str, ...], parlants: tuple[str, ...]) -> str:
    """La répartition, et rien d'autre.

    ⚠️ **Un seul témoin qui parle ne rend jamais `segond_seule`.** Il serait vrai, littéralement,
    que tous ceux qui se sont prononcés divergent — et faux au sens où le pasteur le lirait :
    « la Segond est seule » sur la foi d'un témoin, les deux autres n'ayant rien dit. C'est
    `temoin_isole`, et la liste des muets voyage avec."""
    if len(parlants) == 1 or len(divergents) == 1:
        return "temoin_isole"
    if len(divergents) == len(parlants):
        return "segond_seule"
    return "partage"


def _empreinte(
    versions: dict[str, tuple[int, int]], correspondances: int
) -> str:
    """Ce que le détecteur a réellement lu — **et donc ce qui périme ses lignes**.

    Une collision dépend des versions semées : en ajouter une change la répartition de toutes
    les autres. Même patron que `corpus_snapshot`, `input_hash` et `judged_fingerprint` — *une
    décision ne vaut que sur l'objet qu'elle a regardé.*

    Entrent : le code de chaque version, son **compte de versets** et la **longueur totale** de
    son texte normalisé, plus le nombre de correspondances de versification. Ajouter un témoin,
    re-semer une traduction, recoudre un verset dont la source avait mangé la séparation — tout
    cela déplace l'empreinte.

    ⚠️ Ce qu'elle ne voit pas : une réécriture qui conserverait **à la fois** le compte de
    versets et la longueur totale du texte. Ce n'est pas une preuve d'identité, c'est un
    détecteur de changement, et il vaut mieux le dire que le laisser croire."""
    graine = "|".join(
        f"{code}:{n}:{taille}" for code, (n, taille) in sorted(versions.items())
    ) + f"|map:{correspondances}"
    return hashlib.sha256(graine.encode()).hexdigest()[:32]


async def _lire_le_corpus(session):
    """Les textes, les poids et la carte de numérotation — une passe, tout en mémoire."""
    versions = {
        v.code: v for v in (await session.execute(select(CorpusVersionModel))).scalars()
    }
    if REFERENCE not in versions:
        raise SystemExit(f"  la version de reference {REFERENCE} n'est pas semee.")

    poids = {
        t: idf
        for t, idf in await session.execute(
            select(CorpusIdfModel.token, CorpusIdfModel.idf).where(
                CorpusIdfModel.language == "fr"
            )
        )
    }

    renvoi: dict[str, dict[tuple[int, int, int], tuple[int, int]]] = defaultdict(dict)
    correspondances = 0
    for code, livre, dch, dv, ach, av in await session.execute(
        select(
            CorpusVersificationMapModel.to_scheme,
            CorpusVersificationMapModel.book_id,
            CorpusVersificationMapModel.from_ch,
            CorpusVersificationMapModel.from_v,
            CorpusVersificationMapModel.to_ch,
            CorpusVersificationMapModel.to_v,
        ).where(CorpusVersificationMapModel.from_scheme == REFERENCE)
    ):
        renvoi[code][(livre, dch, dv)] = (ach, av)
        correspondances += 1

    textes: dict[str, dict[tuple[int, int, int], tuple[str, str]]] = {}
    for code, version in versions.items():
        textes[code] = {
            (livre, ch, v): (corps, norme)
            for livre, ch, v, corps, norme in await session.execute(
                select(
                    CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                    CorpusVerseModel.verse, CorpusVerseModel.body,
                    CorpusVerseModel.body_norm,
                ).where(CorpusVerseModel.version_id == version.id)
            )
        }

    tailles = {
        code: (len(t), sum(len(norme) for _corps, norme in t.values()))
        for code, t in textes.items()
    }
    return versions, poids, renvoi, textes, _empreinte(tailles, correspondances)


def detecter(
    poids: dict[str, float],
    renvoi: dict[str, dict],
    textes: dict[str, dict],
    temoins: tuple[str, ...],
) -> list[Collision]:
    """Une collision par verset au plus : **le mot le plus lourd** sur lequel ils se séparent.

    Le maximum, et non la somme : une collision de sens tient dans un mot, et une phrase
    reformulée d'un bout à l'autre n'en est pas une.

    ⚠️ **On ne nomme le mot que d'un côté — celui de la Segond.** Prétendre dire ce que chaque
    témoin écrit à la place suppose un appariement positionnel que le texte ne donne pas : le
    prototype affirmait ainsi que Martin lisait *« donc »* là où la Segond a *« Habazinia »*.
    `reading` n'est rempli que lorsque l'écart est **un mot pour un mot**, et sinon le verset
    entier parle tout seul."""
    collisions: list[Collision] = []
    for (livre, ch, v), (corps_a, norme_a) in textes[REFERENCE].items():
        # Le vocabulaire de la Segond se calcule **une fois par verset**, pas une fois par
        # témoin : le refaire à chaque comparaison triplait le travail sur 31 000 versets, et
        # privait la boucle de son seul raccourci — un verset trop court n'a rien à dire, et
        # il n'y a aucune raison d'aller ouvrir trois traductions pour l'apprendre.
        mots_a = _mots(norme_a, poids)
        if len(mots_a[1]) < MOTS_PLEINS_MINIMUM:
            continue

        rendus: dict[str, tuple[str, str]] = {}
        ecarts: dict[str, tuple[set[str], set[str]]] = {}
        for code in temoins:
            ach, av = renvoi[code].get((livre, ch, v), (ch, v))
            autre = textes[code].get((livre, ach, av))
            if autre is None:
                continue
            rendus[code] = autre
            lu = _ecart(mots_a, _mots(autre[1], poids))
            if lu is not None:
                ecarts[code] = lu

        parlants = tuple(c for c in temoins if c in ecarts)
        if not parlants:
            continue

        candidats = sorted(
            {
                m for c in parlants for m in ecarts[c][0]
                if poids[m] > 0 and m not in _ELISIONS_ORPHELINES
            },
            key=lambda m: -poids[m],
        )
        mot = next((m for m in candidats if not _nom_propre(m, corps_a)), None)
        if mot is None:
            continue

        lectures = [Lecture(REFERENCE, "accorde", None, corps_a)]
        for code in temoins:
            corps = rendus.get(code, ("", ""))[0]
            if code not in ecarts:
                lectures.append(Lecture(code, "muet", None, corps))
                continue
            perdus, gagnes = ecarts[code]
            if mot not in perdus:
                lectures.append(Lecture(code, "accorde", None, corps))
                continue
            propre = next(iter(gagnes)) if perdus == {mot} and len(gagnes) == 1 else None
            lectures.append(Lecture(code, "diverge", propre, corps))

        divergents = tuple(le.code for le in lectures if le.stance == "diverge")
        collisions.append(Collision(
            livre, ch, v, mot, poids[mot], _forme(divergents, parlants), tuple(lectures)
        ))
    return collisions


def _seuil(collisions: list[Collision], centile: float) -> float:
    scores = sorted(c.poids for c in collisions)
    return scores[min(len(scores) - 1, int(len(scores) * centile / 100))]


async def _ecrire(session, retenues: list[Collision], empreinte: str) -> None:
    """Remplir la table — **une décision, pas l'effet de bord d'un rapport qu'on lance pour
    voir**. C'est pourquoi `--ecrire` est explicite, comme pour la carte de versification.

    On efface tout avant : la table est une **projection**, pas une archive. Une ligne survivante
    d'un passage précédent porterait une répartition calculée sur d'autres témoins, et son
    empreinte périmée ne se verrait qu'à la lecture. C'est aussi ce qui garantit que la table ne
    mélange jamais deux empreintes, et donc que l'index peut la charger sans la vérifier.

    ⚠️ **Redémarrer l'API après coup.** L'index du corpus est gelé une fois par processus ; ce
    que ce script écrit reste invisible jusqu'au redémarrage. La surface de curation, elle,
    purge l'index à chaque écriture — mais elle n'est pas ce chemin-ci, et un curateur qui
    croirait son travail perdu chercherait un bug là où il n'y en a pas."""
    quand = datetime.now(UTC)
    await session.execute(delete(CorpusCollisionWitnessModel))
    await session.execute(delete(CorpusCollisionModel))
    await session.flush()

    await session.execute(insert(CorpusCollisionModel), [
        {
            "id": c.id, "book_id": c.livre, "chapter": c.chapitre, "verse": c.verset,
            "word": c.mot, "weight": c.poids, "form": c.forme,
            "corpus_fingerprint": empreinte, "detected_at": quand,
        }
        for c in retenues
    ])
    await session.execute(insert(CorpusCollisionWitnessModel), [
        {
            "collision_id": c.id, "version_code": le.code, "stance": le.stance,
            "reading": le.reading, "body": le.body,
        }
        for c in retenues for le in c.lectures
    ])
    await session.commit()


def _afficher(collision: Collision, par_rang: dict[int, str], familles: dict[str, str]) -> None:
    """Une prise, ses témoins en regard — **ce qu'on relit, et que rien ne remplace**."""
    print(f"\n  {par_rang[collision.livre]} {collision.chapitre}:{collision.verset}"
          f"   [{collision.mot}]   {collision.forme}")
    for lecture in collision.lectures:
        marque = {"accorde": " ", "diverge": "≠", "muet": "·"}[lecture.stance]
        lu = f" ({lecture.reading})" if lecture.reading else ""
        print(f"    {marque} {lecture.code:7} {familles.get(lecture.code, ''):12}"
              f" {lecture.body[:150] or '— ne tient pas ce verset —'}{lu}")


async def lancer(lire: int, tout: bool, forme: str | None, bandes: bool, ecrire: bool) -> None:
    par_rang = {rang: label for rang, _osis, _t, label, _a in BOOKS}

    async with async_session_factory() as session:
        versions, poids, renvoi, textes, empreinte = await _lire_le_corpus(session)
        temoins = tuple(sorted(c for c in versions if c != REFERENCE))
        if not temoins:
            raise SystemExit("  aucun second temoin seme — rien a comparer.")

        familles = {c: v.text_family for c, v in versions.items()}
        collisions = detecter(poids, renvoi, textes, temoins)
        if not collisions:
            print("  rien a comparer.")
            return

        seuil = _seuil(collisions, CENTILE)
        retenues = sorted(
            (c for c in collisions if c.poids >= seuil), key=lambda c: -c.poids
        )

        print("=" * 78)
        print(f"  COLLISIONS   {REFERENCE} contre {', '.join(temoins)}")
        print("=" * 78)
        for code in (REFERENCE, *temoins):
            print(f"    {code:8} {versions[code].label:30} {familles[code]}")
        print(f"\n  {len(collisions)} versets ou les temoins se separent")
        print(f"  seuil ({CENTILE}e centile) : {seuil:.3f}   ->   {len(retenues)} retenues")
        print(f"  empreinte : {empreinte}")
        formes = Counter(c.forme for c in retenues)
        for nom in FORMES:
            print(f"    {nom:16} {formes.get(nom, 0)}")

        if bandes:
            print("\n  LES BANDES — de quoi relire, et donc recalibrer le seuil")
            scores = sorted(c.poids for c in collisions)
            for centile in (50, 75, 90, 95, 98, 99):
                valeur = scores[min(len(scores) - 1, int(len(scores) * centile / 100))]
                combien = sum(1 for c in collisions if c.poids >= valeur)
                print(f"    {centile}e centile   {valeur:.3f}   {combien} prises")

        lot = [c for c in retenues if forme is None or c.forme == forme]
        if tout:
            print(f"\n{'=' * 78}\n  LES {len(lot)} RETENUES, EN ENTIER\n{'=' * 78}")
            for collision in lot:
                _afficher(collision, par_rang, familles)
        elif lire:
            print(f"\n{'=' * 78}\n  LES {min(lire, len(lot))} PLUS FORTES\n{'=' * 78}")
            for collision in lot[:lire]:
                _afficher(collision, par_rang, familles)
        else:
            print("\n  rapport seul — --lire N, --tout, --bandes pour relire.")

        if ecrire:
            await _ecrire(session, retenues, empreinte)
            print(f"\n  {len(retenues)} collisions ecrites, empreinte {empreinte}.")


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument(
        "--lire", type=int, default=0, help="afficher N prises, les temoins en regard"
    )
    analyseur.add_argument(
        "--tout", action="store_true", help="relire EN ENTIER ce que le detecteur retient"
    )
    analyseur.add_argument("--forme", choices=FORMES, help="ne relire qu'une repartition")
    analyseur.add_argument(
        "--bandes", action="store_true", help="les centiles, pour recalibrer le seuil"
    )
    analyseur.add_argument(
        "--ecrire", action="store_true", help="remplir urim_corpus_collision"
    )
    arguments = analyseur.parse_args()
    asyncio.run(lancer(
        arguments.lire, arguments.tout, arguments.forme, arguments.bandes, arguments.ecrire
    ))


if __name__ == "__main__":
    main()
