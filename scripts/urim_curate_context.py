"""Les notes de contexte **littéraire** — et pourquoi l'historique n'est pas de ce lot.

    python scripts/urim_curate_context.py                 # toutes les unités non examinées
    python scripts/urim_curate_context.py --livre Hag     # un livre, pour juger
    python scripts/urim_curate_context.py --limite 20

## La question tranchée avant d'écrire une ligne

`CorpusContextNoteModel` porte S40 : **sourcé, ou absent**. Or un modèle ne source pas — il
récite, et ce qu'il récite a l'air documenté. Le lot des mises en garde n'a pu exister que parce
que leur source est le **passage lui-même** : « le texte ne dit pas X » se contrôle en relisant.

Les neuf notes posées à la main disent où passe la ligne, et elle ne passe pas là où le
`context_kind` la met. Huit d'entre elles ne s'appuient que sur des endroits du corpus — un
renvoi (Nombres 21:8-9 depuis Jean 3:14), un rattachement (le « donc » de Romains 8:1 au cri de
7:24-25), une construction (le chiasme de 2 Corinthiens 5 autour du v. 18), une répétition
ironique (les mots de Jézabel exécutés à la lettre). **Trois de ces huit sont étiquetées
`historique`** — la Pâque de Jean 2:23, l'héritage inaliénable de Lévitique 25:23, la collecte
de 1 Co 16:1-4 : ce sont des observations littéraires en habit d'historien.

La neuvième est celle d'Aggée — *« 520 av. J.-C., seize ans après le retour »*. Elle est vraie,
et **aucun détecteur du dépôt ne l'attraperait si elle était fausse** : D3 n'y voit ni manuscrit
ni autorité, D5 compare des mots cités au passage et une date n'est pas une citation. C'est
exactement l'erreur que S40 nomme — celle qu'un pasteur répète avec assurance parce qu'elle
avait l'air documentée.

D'où la règle de ce lot, plus étroite que `context_kind` :

> **Une note est légitime exactement quand tout son contenu se résout à un endroit du corpus.**

Et cette propriété-là, contrairement à « est-ce théologiquement juste », une machine sait la
vérifier. Le lot ne génère donc que du `litteraire` ; `historique` reste aux quatre lignes
humaines, et le restera.

## Ce que ce lot fait de neuf : le modèle déclare ses sources, et on les résout

Les autres lots vérifient la **forme** d'une ligne générée. Celui-ci vérifie son **appui** :
le modèle rend ses renvois dans un champ à part, chacun est cherché dans `urim_corpus_verse`,
et un renvoi qui ne tombe sur aucun verset **jette la note entière**. « 520 av. J.-C. » ne cite
aucun verset : refusé sans qu'on ait eu à détecter une chronologie.

C'est aussi ce qui oblige à **montrer le voisinage au modèle**. Une note littéraire parle de ce
qui précède et de ce qui suit ; sans ces versets dans l'invite, le modèle les inventerait, et on
serait revenu au problème qu'on croyait avoir résolu.

## Ce que ce lot garantit, et ce qu'il ne garantit pas

**Garanti par la machine** : chaque référence citée existe dans le texte en base ; aucune date,
aucun siècle numéroté, aucune ère ; aucun manuscrit ni autorité extérieure
(`verifier_forme_machine`, partagé avec la route Plateforme) ; et la note **montre** au lecteur
où aller voir — un renvoi que le modèle n'écrit pas dans sa propre phrase est un renvoi dont il
ne s'est pas servi.

**Mesuré mais non garanti** : que le renvoi parle bien du même sujet. Ce contrôle a existé, et
les prises du corpus l'ont rétrogradé en signal — voir `_EXIGER_ANCRAGE`. Il refusait 2 Rois
23:25 renvoyant à Deutéronome 6:5.

**Non garanti** : qu'un chiasme annoncé en soit un. Le modèle peut décrire une construction que
le texte ne porte pas — c'est une affirmation *sur le passage*, du même genre que celles des
mises en garde, et elle se contrôle de la même façon : en relisant. C'est le niveau de risque
que tout ce corpus accepte, et il est différent de celui que S40 refuse. Une érudition
extérieure fausse n'a **aucun** contradicteur ; un chiasme faux en a un, et il est en base.

⚠️ **Signature `ia-mistral`, `source_ref` porte « non relu ».** Ces notes sont un point de
départ pour un relecteur, pas un état définitif — c'est la seule chose qui rend la signature
d'une machine acceptable ici.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from bisect import bisect_left
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.contexts.urim.application.curation import (
    SIGNATAIRE_IA,
    verifier_forme_machine,
)
from app.contexts.urim.domain.errors import CurationInvalideError
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusContextNoteModel,
    CorpusExaminationModel,
    CorpusIdfModel,
    CorpusPericopeModel,
    CorpusVerseModel,
    CorpusVersionModel,
)
from app.core.config import get_settings
from app.core.database import async_session_factory
from scripts.urim_curate_pericopes import CONCURRENCE, ESSAIS, INTERVALLE, Cadence
from scripts.urim_ecarts import VERSION_DE_CURATION
from scripts.urim_seed_books import BOOKS

#: La dimension au registre d'examen — c'est elle qui rend ce lot reprenable. Sans elle, une
#: unité regardée sans trouvaille est indiscernable d'une unité jamais regardée, et rattraper
#: cent unités en referait deux mille six cents.
_DIMENSION = "context_note"

#: 🔴 **Le seul genre que ce lot produit**, et c'est la décision qui précède tout le code.
#: Voir l'en-tête : `historique` n'a pas de source dans le dépôt, donc pas de vérificateur.
_GENRE = "litteraire"

#: 🔴 **La forme attendue, nommée — pas un plafond.**
#:
#: Le premier réglage des mises en garde était un maximum à trois, et la distribution l'a
#: démenti : 48 % à zéro, **douze unités à une**, 27 % à deux, 25 % à trois. Un modèle qui
#: jugerait au mérite donnerait une pente ; ce trou à un était la signature d'un quota rempli.
#: Baisser le plafond aurait déplacé la masse, pas supprimé le zèle. Nommer la forme l'a fait
#: tomber de 81 % à 47 %.
#:
#: 🔴 **Ici la nommer n'a pas suffi, et c'est le témoin qui l'a dit.** Cinq passages sur
#: les 77 mêmes unités des Proverbes — un livre dont les chapitres 1-9 sont un discours suivi
#: et les chapitres 10+ des sentences indépendantes. Le zèle a mis cinq tours à tomber :
#:
#:     tour 1   2,6 % à zéro · 24,7 % à une · 72,7 % à deux
#:     tour 3  14,3 %        · 33,8 %       · 51,9 %
#:     tour 5  15,6 %        · 59,7 %       · 24,7 %
#:
#: Mais le chiffre qui a servi à régler n'est aucun de ceux-là : c'est **l'écart entre les
#: deux moitiés du livre**. Au tour 3, les deux genres donnaient *exactement* 14,3 % de zéro,
#: et les sentences en produisaient même un peu plus que le discours. Un taux insensible au
#: texte est un quota, quel que soit sa valeur — même famille de preuve que le « trou à un »
#: des mises en garde. Au tour 5 : **2,9 % de zéro sur le discours, 25,6 % sur les sentences.**
#:
#: Trois causes, toutes lues dans les prises, aucune devinée :
#:
#: 1. Je lui avais donné le gabarit moi-même — « progression en trois temps » figurait dans ma
#:    liste des espèces, et il me l'a renvoyé mot pour mot sur un distique des Proverbes.
#: 2. L'exigence de renvoi était devenue un rite : des références justes, résolues, accrochées
#:    à des notes qui ne s'en servaient pas. C'est ce qui donne son vrai sens au contrôle
#:    `aucun renvoi visible` — un renvoi que le modèle n'écrit pas dans sa propre phrase est
#:    un renvoi dont il ne s'est pas servi.
#: 3. La règle (1) demandait un jugement (« est-ce important ? ») là où il fallait un geste :
#:    lis le verset d'avant et celui d'après, parlent-ils d'autre chose ? Un modèle exécute un
#:    test qu'il ne sait pas porter.
_ATTENDU = "0 souvent · 1 quand il y en a · 2 rare"

#: La troncature qui suit la forme attendue. Elle ne remplace pas la règle (2) de l'invite :
#: c'est le filet, pas le réglage.
_MAX_PAR_UNITE = 2

#: Combien de versets de part et d'autre on met sous les yeux du modèle. Une note littéraire
#: parle du voisinage ; six versets suffisent à voir un « donc » se rattacher, et au-delà
#: l'invite noie le passage lui-même.
_VOISINAGE = 6

#: Longueur minimale d'une note. Plus court qu'une phrase, ce n'est pas une observation.
_CORPS_MINIMUM = 40

#: 🔴 **La chronologie, refusée en dur** — le cas d'Aggée, celui que rien d'autre n'attrape.
#:
#: L'exigence de renvoi résolu suffirait presque : une date ne cite aucun verset. Mais elle
#: laisserait passer la date **accompagnée** d'un renvoi juste — « deuxième année de Darius
#: (1:1), soit 520 av. J.-C. » — où l'érudition voyage en passager clandestin d'une source
#: valable. C'est la forme la plus vraisemblable de l'erreur, donc celle qu'il faut nommer.
#:
#: 🔴 **Un siècle nu n'est pas une date** — corrigé sur une prise du corpus. Le premier motif
#: refusait `\bsiècles?\b`, et il a jeté une note sur la doxologie de Jude 25 : *« puissance aux
#: siècles des siècles »*. C'est une formule de louange, pas une chronologie. Un siècle ne date
#: quelque chose que s'il est **numéroté** — « au XIIIe siècle », « au 3e siècle ».
_CHRONOLOGIE = re.compile(
    r"av(?:ant)?\.?\s*J[\s.-]*C|apr?(?:[eè]s)?\.?\s*J[\s.-]*C"
    r"|\b(?:[ivx]+|\d{1,2})\s*(?:er|[eè]me|e)?\s*si[eè]cle"
    r"|\bsi[eè]cle\s+(?:avant|apr[eè]s)\b"
    r"|\bnotre\s+[eè]re\b|\b[eè]re\s+chr[eé]tienne\b",
    re.I,
)

#: Un renvoi tel que le modèle le rend : « Nb 21:8-9 », « 1 Co 16:1-4 », ou « 2:23 » pour le
#: livre de l'unité. Le livre est **optionnel et strictement résolu** : présent et inconnu, la
#: note tombe — c'est là que « le livre d'Hénoch 3:2 » se fait prendre.
_RENVOI = re.compile(
    r"^\s*(?:(?P<livre>.+?)\s+)?(?P<ch>\d{1,3})\s*[:.]\s*(?P<v1>\d{1,3})"
    # Le tiret demi-cadratin (U+2013) autant que le trait d'union, et le chapitre écrit une
    # seconde fois dans la borne haute : le modèle rend « 4:18-19 » comme « 4:18-4:19 ». Une
    # bonne note d'un témoin est tombée sur cette seule variante — une plage rejetée pour un
    # caractère est une note perdue sans raison.
    r"(?:\s*[-\u2013]\s*(?:(?P<ch2>\d{1,3})\s*[:.]\s*)?(?P<v2>\d{1,3}))?\s*$"
)

#: 🔴 **La forme courte, « v. 26 » ou « 26 » — et c'est la troisième fois que
#: l'instrument a tort de la même façon.**
#:
#: La règle (3) demande au modèle de déclarer les versets de sa propre unité, parce qu'une
#: construction n'a pas d'autre source qu'eux. Il obéit, et il les rend comme un humain les
#: écrit : `['v. 26', 'v. 27']`. Le vérificateur exigeait un chapitre et jetait la note —
#: celle, précisément, que cette règle venait d'ajouter pour la sauver.
#:
#: Elle n'est admise que sur une unité tenant dans **un seul chapitre**, où le numéro nu ne
#: peut désigner qu'un verset. À cheval sur deux chapitres, elle serait une devinette.
_RENVOI_COURT = re.compile(
    r"^\s*(?:vv?\.|versets?)?\s*(?P<v1>\d{1,3})"
    r"(?:\s*[-\u2013]\s*(?P<v2>\d{1,3}))?\s*$",
    re.I,
)

#: 🔴 **La section entière — « Exode 25-31 » — quatrième panne du même genre.**
#:
#: Le passage sur le corpus a rejeté 32 notes pour « renvoi introuvable », et les deux prises
#: visibles étaient toutes deux celle-ci : une note d'Exode 39 renvoyant l'achèvement du
#: tabernacle à l'ordre donné en **Exode 25-31** et à sa réalisation en **Exode 35-39**. C'est
#: la référence juste, et la seule forme sous laquelle elle s'écrit — personne ne cite un récit
#: de sept chapitres par un verset.
#:
#: Elle se résout au **premier chapitre nommé**, et l'ancrage se mesure alors contre ce chapitre
#: entier : la note prétend répondre à toute la section, c'est donc contre elle qu'il faut la
#: peser. Le chapitre exige un nom de livre — un « 25-31 » nu dans le champ des renvois serait
#: indiscernable d'une plage de versets, et deviner ici reviendrait à ne rien vérifier.
_RENVOI_CHAPITRE = re.compile(
    r"^\s*(?P<livre>.+?)\s+(?P<ch>\d{1,3})"
    r"(?:\s*[-\u2013]\s*(?P<ch2>\d{1,3}))?\s*$"
)

#: 🔴 **Le seuil d'ancrage, et c'est la table du corpus qui le donne — pas ma jauge.**
#:
#: Premier réglage : « un mot partagé d'au moins cinq lettres ». Le passage sur le corpus entier
#: l'a démenti sur la prise la plus nette du lot — une note de Jérémie 50:44 renvoyant l'image du
#: lion à Amos 3:4 et Ésaïe 5:29, juste, classique, correctement citée, **jetée parce que
#: `lion` fait quatre lettres**. Le seul mot que les trois versets partagent est précisément
#: celui qui fonde le renvoi.
#:
#: Descendre le seuil à quatre aurait fait de `Dieu` un laissez-passer. La longueur d'un mot est
#: un proxy de sa rareté ; `urim_corpus_idf` **est** sa rareté, et son propre docstring dit
#: pourquoi elle existe : « Ancres rares : les mots fréquents ne discriminent rien ».
#:
#:     lion 6,02 · serpent 6,74 · proie 6,36 · collecte 9,65
#:     dieu 2,15 · dans 1,69 · pour 1,81 · seigneur 3,22 · terre 3,31
#:
#: À 5,0, la table exclut environ quatre cents tokens sur 22 328 — la forme juste d'une liste de
#: mots vides : peu nombreux, et mesurés plutôt que devinés.
_IDF_ANCRAGE = 5.0

#: 🔴 **L'ancrage : calculé, et NE REFUSANT PLUS. Les prises du corpus l'ont condamné.**
#:
#: L'idée était juste : un renvoi peut exister et n'avoir aucun rapport, et c'est ainsi qu'une
#: invention survit à un vérificateur de références. L'instrument, lui, ne l'est pas. Il exige
#: qu'un renvoi hors du livre partage une **ancre rare** avec le passage, et un recouvrement
#: lexical mot à mot est un mauvais témoin du lien entre deux textes.
#:
#: Quatre prises lisibles sur les 54 refus du corpus, et **trois étaient fausses** :
#:
#: - Jérémie 50:44 → Amos 3:4, l'image du lion : perdue parce que `lion` faisait quatre lettres.
#:   Corrigé en passant à `urim_corpus_idf`.
#: - Jérémie 50:44 → Ésaïe 5:29, la même image : perdue parce que LSG y écrit « lionne » et
#:   « lionceaux ». Corrigé en n'exigeant plus l'ancrage de *chaque* renvoi.
#: - **2 Rois 23:25 → Deutéronome 6:5** : « de tout son cœur, de toute son âme et de toute sa
#:   force ». La citation la plus littérale de l'Ancien Testament, refusée parce que le mot
#:   partagé le plus rare est `force` à **4,76** — sous un seuil de 5,0. Rien ne rattrape ça :
#:   une citation quasi verbatim ne partage que des mots moyennement fréquents, parce que ce
#:   qu'elle partage est une **phrase**, pas un mot rare.
#: - Romains 15:25-28 → Deutéronome 15:4-11 : refus défendable, le renvoi était ornemental.
#:
#: Le contrôle est donc **rétrogradé de refus en signal**, exactement comme le détecteur de
#: négation de doctrine l'avait été après que huit de ses neuf prises se furent révélées bonnes.
#: Ce qui reste pour attraper un renvoi ornemental est `aucun renvoi visible`, et il travaille
#: sur une meilleure preuve : un renvoi que le modèle n'a pas écrit dans sa propre phrase est un
#: renvoi dont il ne s'est pas servi.
#:
#: ⚠️ **Le remettre à `True` exige un meilleur instrument, pas un autre seuil.** Une piste : le
#: n-gramme partagé plutôt que le mot — « et de toute » relie 2 Rois 23 à Deutéronome 6 là où
#: aucun mot isolé n'y parvient. Et voir la ligature `œ`, qui casse `cœur` en deux fragments
#: dans 2 212 versets et fausse toute mesure lexicale sur ce corpus.
_EXIGER_ANCRAGE = False

_SYSTEME = (
    "Tu es bibliste. On te donne une pericope de la Bible Louis Segond 1910, les versets qui la "
    "precedent et ceux qui la suivent. Ta tache est de relever le CONTEXTE LITTERAIRE : comment "
    "ce passage est construit, et a quoi il est rattache DANS L'ECRITURE.\n"
    "Quatre especes, et rien d'autre :\n"
    "- LE RATTACHEMENT : le passage continue, repond ou conclut ce qui precede. Un « donc », un "
    "« c'est pourquoi », une question laissee ouverte plus haut.\n"
    "- LE RENVOI : le passage cite, reprend ou suppose un autre texte de l'Ecriture.\n"
    "- LA CONSTRUCTION : chiasme, inclusion, repetition ironique — une figure qui change "
    "l'ORDRE dans lequel il faut lire. Decrire ce que les versets disent l'un apres l'autre "
    "n'est PAS une construction, c'est une paraphrase.\n"
    "- LA REPRISE DE MOT : un terme revient a quelques versets d'intervalle et porte l'argument.\n"
    "HUIT REGLES QUE TU DOIS SUIVRE CONTRE TON INSTINCT :\n"
    "(0) LE TEST QUI DECIDE DE TOUT — n'ecris une note que si son absence ferait LIRE LE PASSAGE "
    "AUTREMENT. « Le donc du v. 1 rattache l'unite au cri de 7:24-25 : la lire sans le chapitre "
    "7 supprime la question a laquelle elle repond » est une bonne note. « Les v. 11-12 forment "
    "une progression en trois temps : la richesse mal acquise, l'espoir differe, le desir "
    "accompli » n'en est PAS une : cela redit le passage dans l'ordre ou il est ecrit, et un "
    "lecteur qui n'a pas la note lit exactement la meme chose. Tout passage a des voisins et "
    "une suite de phrases ; seul compte ce dont l'ignorance FAUSSE la lecture.\n"
    "(1) COMMENCE PAR CE TEST, AVANT D'ECRIRE QUOI QUE CE SOIT. Lis le dernier verset de CE QUI "
    "PRECEDE et le premier de CE QUI SUIT. Parlent-ils du meme sujet que l'unite ? Si NON — "
    "s'ils traitent d'autre chose, comme deux sentences voisines qui n'ont rien a voir — alors "
    "l'unite n'a AUCUN rattachement, et tu ne peux ecrire une note que si elle porte une figure "
    "interne (chiasme, inclusion, repetition) ou cite explicitement un autre texte. Sinon rends "
    "une liste VIDE. Beaucoup d'unites sont dans ce cas : un proverbe, une loi, une genealogie, "
    "une sentence de sagesse se lisent entieres. Ne cherche pas un rattachement pour en trouver "
    "un. Et n'ecris JAMAIS une note pour dire qu'il n'y a pas de contexte : « ce passage forme "
    "une unite autonome » n'est pas une note, c'est une liste vide mal rendue.\n"
    "(2) SI, ET SEULEMENT SI, le passage en porte un, ecris-en UNE : la principale. Deux est "
    "reserve aux unites qui portent deux faits vraiment distincts. N'ecris jamais une seconde "
    "note pour etoffer la premiere.\n"
    "(3) CHAQUE NOTE CITE AU MOINS UN RENVOI, rendu dans le champ 'renvois' sous la forme "
    "'Livre chapitre:verset' ou 'chapitre:verset' pour le livre de l'unite. LES VERSETS DE "
    "L'UNITE ELLE-MEME SONT DES RENVOIS VALABLES, et souvent les seuls : une construction se "
    "cite par ses propres versets — une inclusion sur 'la crainte de l'Eternel' aux v. 26 et 27 "
    "d'une unite du chapitre 1 declare '1:26' et '1:27', avec le chapitre. Ces references sont "
    "VERIFIEES contre le texte en base : une reference qui n'existe pas fait jeter la note. "
    "Chaque renvoi doit se voir AUSSI dans le corps de la note — « v. 19 » suffit pour un "
    "verset de l'unite, « 1:12 » ou « Nombres 21:8 » pour tout le reste.\n"
    "(3 bis) N'ACCROCHE JAMAIS UN RENVOI POUR SATISFAIRE LA REGLE (3). Si tu n'as aucun texte "
    "precis a citer, c'est que la note n'a pas lieu d'etre : rends une liste vide. Une "
    "reference que ta phrase n'utilise pas est un ornement, et elle sera detectee.\n"
    "(4) AUCUNE DATE, AUCUN SIECLE, AUCUNE ERE, aucun regne date, aucune chronologie. Le "
    "contexte historique n'est PAS de ce lot : il n'a pas de source verifiable ici et il est "
    "refuse. Tu ne dis pas quand cela s'est passe, tu dis comment le texte est bati.\n"
    "(5) Ne cite AUCUNE autorite exterieure et AUCUN manuscrit : pas de commentateur, pas "
    "d'edition critique, pas de concile. Ton seul appui est l'Ecriture qu'on te donne.\n"
    "(6) Une note DECRIT, elle n'enseigne pas. Elle ne dit pas ce que le passage signifie ni ce "
    "qu'il faut en croire — la lecture doctrinale est faite ailleurs. Une ou deux phrases "
    "sobres.\n"
    'Reponds par un objet JSON : {"notes": [{"corps": "...", "renvois": ["...", "..."]}]} — au '
    "plus DEUX notes, et la liste peut etre vide."
)

#: Les motifs de rejet, comptés puis imprimés. Un lot qui ne dit pas ce qu'il a jeté ne se règle
#: pas : c'est en lisant les prises qu'on apprend si le vérificateur ou le modèle a tort.
_MOTIFS = ("sans renvoi", "renvoi introuvable", "aucun renvoi visible",
           "renvoi sans ancrage", "chronologie", "forme machine", "trop court")


class IndexDesLivres:
    """Le nom d'un livre → son rang, sur toutes les formes que les humains écrivent.

    Construit depuis `BOOKS`, qui porte déjà les abréviations reconnues par le moteur : un
    second dictionnaire ici divergerait le jour où l'un des deux serait corrigé."""

    def __init__(self) -> None:
        self._par_nom: dict[str, int] = {}
        for rang, osis, _, nom, abrevs in BOOKS:
            for forme in (osis, nom, *abrevs):
                self._par_nom[replier(forme)] = rang

    def rang(self, nom: str) -> int | None:
        return self._par_nom.get(replier(nom))


def replier(texte: str) -> str:
    """Sans accents, sans points, sans casse — la forme sur laquelle deux noms se comparent."""
    decompose = unicodedata.normalize("NFD", texte)
    sans = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s.]+", " ", sans).strip().lower()


@dataclass(frozen=True, slots=True)
class Renvoi:
    """Un renvoi résolu. `section` distingue « Exode 25-31 » de « Exode 25:3-7 ».

    La distinction n'est pas cosmétique : une section se montre dans la note par son numéro de
    chapitre, et son ancrage se pèse contre le chapitre entier."""

    livre: int
    chapitre: int
    premier: int
    dernier: int
    section: bool = False


def lire_renvoi(brut: str, unite: Unite, livres: IndexDesLivres) -> Renvoi | None:
    """« Nb 21:8-9 » → un `Renvoi`, ou rien.

    ⚠️ **Un nom de livre présent et inconnu rend `None`** — il ne retombe pas sur le livre de
    l'unité. C'est la différence entre un vérificateur et une politesse : « le livre d'Hénoch
    3:2 » doit tomber, or Genèse 3:2 existe et le laisserait passer."""
    trouve = _RENVOI.match(brut)
    if trouve is None:
        return _lire_court(brut, unite) or _lire_section(brut, livres)
    nom = trouve.group("livre")
    if nom:
        rang = livres.rang(nom)
        if rang is None:
            return None
    else:
        rang = unite.livre
    chapitre = int(trouve.group("ch"))
    # « 4:18-4:19 » est admis, « 4:18-5:2 » non : une plage qui franchit un chapitre ne se
    # vérifie pas telle quelle, et la refuser coûte une note rare là où l'accepter en fausserait
    # la résolution.
    if trouve.group("ch2") and int(trouve.group("ch2")) != chapitre:
        return None
    premier = int(trouve.group("v1"))
    dernier = int(trouve.group("v2") or premier)
    if dernier < premier:
        return None
    return Renvoi(rang, chapitre, premier, dernier)


def _lire_section(brut: str, livres: IndexDesLivres) -> Renvoi | None:
    """« Exode 25-31 » → le premier chapitre nommé, pesé en entier."""
    trouve = _RENVOI_CHAPITRE.match(brut)
    if trouve is None:
        return None
    rang = livres.rang(trouve.group("livre"))
    if rang is None:
        return None
    chapitre = int(trouve.group("ch"))
    if trouve.group("ch2") and int(trouve.group("ch2")) < chapitre:
        return None
    # Le chapitre entier : les versets inexistants sont filtrés à la résolution.
    return Renvoi(rang, chapitre, 1, 200, section=True)


def _lire_court(brut: str, unite: Unite) -> Renvoi | None:
    """« v. 26 », « 26 », « v. 15-19 » → le verset de l'unité, quand il n'y a qu'un chapitre."""
    if len(unite.chapitres) != 1:
        return None
    trouve = _RENVOI_COURT.match(brut)
    if trouve is None:
        return None
    premier = int(trouve.group("v1"))
    dernier = int(trouve.group("v2") or premier)
    if dernier < premier:
        return None
    return Renvoi(unite.livre, next(iter(unite.chapitres)), premier, dernier)


@dataclass(frozen=True, slots=True)
class Unite:
    """L'unité curée, réduite à ce dont la vérification a besoin.

    Les chapitres sont là pour une seule raison, et c'est la première prise du lot qui l'a
    apprise — voir `renvoi_visible`."""

    livre: int
    chapitres: frozenset[int]


#: Une référence longue telle qu'elle s'écrit dans une note : « 1:13 », « 1:12-15 ».
_MONTREE_LONGUE = r"\b{ch}\s*[:.]\s*(\d{{1,3}})(?:\s*[-\u2013]\s*(\d{{1,3}}))?"

#: Une référence courte, et tout ce qui la suit de numérique : « v. 19 », « v. 9-10 »,
#: « v. 15.18 », « versets 3, 5 et 7 ». Les humains listent, ils ne normalisent pas.
_MONTREE_COURTE = re.compile(r"\b(?:vv?\.|versets?)\s*([\d\s.,;\u2013et-]*\d)", re.I)


def renvoi_visible(corps: str, unite: Unite, renvoi: Renvoi) -> bool:
    """Ce verset-là se voit-il dans la note, sous une forme qu'un lecteur suivrait ?

    🔴 **Deux fois corrigé, deux fois contre l'instrument.** Le premier réglage n'acceptait que
    « 2:19 » : deux bonnes notes d'Aggée sont tombées pour avoir écrit « au v. 19 » — la
    convention même des neuf notes humaines (*« le chiasme autour du v. 18 »*), donc un contrôle
    auquel l'étalon aurait échoué. Le second refusait encore *« (1:12-15) »* pour un renvoi à
    1:13, et *« (v. 15.18) »* pour 2:18 : une plage qui **contient** le verset le montre, et une
    liste séparée d'un point le montre aussi.

    Deux bonnes lignes perdues sur cinq, sur de la typographie. C'est le rapport exact des huit
    formes interdites sur neuf que le détecteur d'écarts avait signalées à tort."""
    # Une section — « Exode 25-31 » — se montre par son numéro de chapitre : c'est ainsi qu'elle
    # s'écrit, et personne ne cite sept chapitres par un verset.
    if renvoi.section:
        return bool(re.search(rf"\b{renvoi.chapitre}\b", corps))
    for trouve in re.finditer(_MONTREE_LONGUE.format(ch=renvoi.chapitre), corps):
        debut = int(trouve.group(1))
        fin = int(trouve.group(2) or debut)
        if debut <= renvoi.premier <= fin:
            return True
    # La forme courte n'est admise que là où elle ne peut pas être ambiguë : dans le livre et
    # dans un chapitre de l'unité, où « v. 19 » ne peut désigner qu'un verset.
    if renvoi.livre != unite.livre or renvoi.chapitre not in unite.chapitres:
        return False
    for trouve in _MONTREE_COURTE.finditer(corps):
        nombres = [int(n) for n in re.findall(r"\d{1,3}", trouve.group(1))]
        if renvoi.premier in nombres or (
            len(nombres) > 1 and nombres[0] <= renvoi.premier <= nombres[-1]
        ):
            return True
    return False


def ancres(texte_norme: str, idf: dict[str, float]) -> set[str]:
    """Les mots par lesquels deux passages peuvent se répondre — les autres ne prouvent rien.

    Un token absent de la table est tenu pour rare : les deux textes comparés viennent du corpus,
    donc son absence dit une lacune de la table, pas la banalité du mot. Se tromper dans ce
    sens-là garde une note ; se tromper dans l'autre la perd."""
    return {
        mot for mot in texte_norme.split()
        if idf.get(mot, _IDF_ANCRAGE) >= _IDF_ANCRAGE
    }


def verifier_note(
    corps: str, renvois: list[str], unite: Unite, texte_norme: str,
    versets: dict[tuple[int, int, int], tuple[str, str]], livres: IndexDesLivres,
    idf: dict[str, float],
) -> str | None:
    """`None` si la note tient, sinon le motif du rejet — celui qu'on imprimera.

    L'ordre des contrôles est celui du coût : la forme d'abord, la résolution ensuite."""
    corps = corps.strip()
    if len(corps) < _CORPS_MINIMUM:
        return "trop court"
    try:
        verifier_forme_machine(corps, SIGNATAIRE_IA)
    except CurationInvalideError:
        return "forme machine"
    if _CHRONOLOGIE.search(corps):
        return "chronologie"
    if not renvois:
        return "sans renvoi"

    montre = dehors = ancree = False
    for brut in renvois:
        if not isinstance(brut, str):
            return "sans renvoi"
        lu = lire_renvoi(brut, unite, livres)
        if lu is None:
            return "renvoi introuvable"
        cites = [
            versets[(lu.livre, lu.chapitre, n)]
            for n in range(lu.premier, lu.dernier + 1)
            if (lu.livre, lu.chapitre, n) in versets
        ]
        if not cites:
            return "renvoi introuvable"
        # ⚠️ **Un seul renvoi visible suffit, et le contrôle porte sur la note entière.**
        #
        # 🔴 Le réglage précédent l'exigeait de chacun, et jetait des notes justes parce qu'un
        # troisième renvoi était écrit « 15.18 » au lieu de « 15-18 ». Or ce que ce contrôle
        # protège n'est pas la typographie : c'est le fait qu'un pasteur qui lit la note voie
        # de quoi la vérifier. Une note qui montre 2:11 et 2:15 le lui donne. Celle qui ne
        # montre rien — « le passage reprend un épisode du désert » — ne le lui donne pas, et
        # c'est le seul cas qu'il faut refuser.
        montre = montre or renvoi_visible(corps, unite, lu)
        if lu.livre != unite.livre:
            dehors = True
            if ancres(" ".join(n for _, n in cites), idf) & ancres(texte_norme, idf):
                ancree = True

    if montre is False:
        return "aucun renvoi visible"
    # ⚠️ **Un seul renvoi ancré suffit, et le contrôle porte sur la note entière** — comme la
    # visibilité, et pour la même raison.
    #
    # 🔴 Le réglage précédent l'exigeait de chacun. La note du lion de Jérémie 50:44 déclarait
    # Amos 3:4 **et** Ésaïe 5:29 ; la première ancre sur « lion », la seconde non — LSG y écrit
    # « lionne » et « lionceaux ». Une citation d'appui non lexicalement ancrée faisait tomber
    # une note dont la source principale était solide, et toutes les références étaient réelles.
    return "renvoi sans ancrage" if (_EXIGER_ANCRAGE and dehors and not ancree) else None


def _notes_depuis(
    contenu: str, unite: Unite, texte_norme: str,
    versets: dict[tuple[int, int, int], tuple[str, str]], livres: IndexDesLivres,
    idf: dict[str, float], rejets: dict[str, list[tuple[str, list]]],
) -> list[str] | None:
    """Le JSON du modèle → des notes vérifiées, ou rien.

    ⚠️ **Une liste vide est un succès**, pas un échec : c'est la réponse attendue sur beaucoup
    de textes. La distinguer d'un refus de parser est tout l'objet du `None`."""
    bloc = re.search(r"\{.*\}", contenu, re.S)
    if bloc is None:
        return None
    try:
        notes = json.loads(bloc.group(0)).get("notes")
    except json.JSONDecodeError:
        return None
    if not isinstance(notes, list):
        return None

    propres: list[str] = []
    for note in notes[:_MAX_PAR_UNITE]:
        if not isinstance(note, dict):
            continue
        corps = note.get("corps")
        renvois = note.get("renvois")
        if not isinstance(corps, str):
            continue
        if not isinstance(renvois, list):
            renvois = []
        motif = verifier_note(corps, renvois, unite, texte_norme, versets, livres, idf)
        if motif is not None:
            # ⚠️ **Les renvois déclarés voyagent avec la prise.** Le motif seul ne permet pas de
            # juger qui a tort : « renvoi absent du corps » sur une note qui dit « (v. 4) » se
            # lit tout autrement selon que le modèle avait déclaré « 2:4 » ou le passage entier.
            # Sans eux j'ai deviné une fois, et j'ai deviné faux.
            rejets[motif].append((corps.strip()[:220], list(renvois)))
            continue
        propres.append(corps.strip()[:2000])
    return propres


async def _une_unite(
    ia: MistralAssistant, verrou: asyncio.Semaphore, cadence: Cadence,
    unite_id: UUID, invite: str, verifier,
) -> tuple[UUID, list[str] | None]:
    async with verrou:
        for essai in range(ESSAIS):
            await cadence.attendre()
            contenu = await ia.demander(_SYSTEME, invite, etiquette="context")
            if contenu:
                notes = verifier(contenu)
                if notes is not None:
                    return unite_id, notes
            await asyncio.sleep(2**essai)
    return unite_id, None


async def _purger(livre_voulu: str | None) -> None:
    """⚠️ **Bornée par `--livre`, et bornée au genre généré.**

    Sans la borne de livre, éprouver une invite sur Aggée effacerait la curation des
    soixante-cinq autres — une heure de modèle pour juger un réglage. Sans la borne de genre,
    elle emporterait les notes `historique` posées à la main, qui sont l'étalon contre lequel
    tout ce lot a été décidé : détruire le témoin avant de mesurer contre lui."""
    async with async_session_factory() as s:
        portee = []
        portee_examen = []
        if livre_voulu:
            rangs = [r for r, osis, *_ in BOOKS if osis == livre_voulu]
            if not rangs:
                raise SystemExit(f"  livre inconnu : {livre_voulu}")
            unites_du_livre = select(CorpusPericopeModel.id).where(
                CorpusPericopeModel.book_id == rangs[0]
            )
            portee = [CorpusContextNoteModel.pericope_id.in_(unites_du_livre)]
            portee_examen = [CorpusExaminationModel.pericope_id.in_(unites_du_livre)]
        await s.execute(
            delete(CorpusContextNoteModel).where(
                CorpusContextNoteModel.reviewed_by == SIGNATAIRE_IA,
                CorpusContextNoteModel.context_kind == _GENRE,
                *portee,
            )
        )
        # Et son registre, sinon la purge serait un piège : les unités resteraient marquées
        # « examinées » et la relance ne ferait rien du tout.
        await s.execute(
            delete(CorpusExaminationModel).where(
                CorpusExaminationModel.dimension == _DIMENSION,
                CorpusExaminationModel.examined_by == SIGNATAIRE_IA,
                *portee_examen,
            )
        )
        await s.commit()
    print("  notes litteraires de l'IA effacees — les 9 relues a la main sont gardees\n")


async def curer(livre_voulu: str | None, limite: int | None, purge: bool) -> None:
    reglages = get_settings()
    if not reglages.mistral_api_key:
        raise SystemExit("MISTRAL_API_KEY absente — rien a faire.")
    if purge:
        await _purger(livre_voulu)

    par_rang = {rang: (osis, nom) for rang, osis, _, nom, _ in BOOKS}
    livres = IndexDesLivres()
    ia = MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)

    async with async_session_factory() as s:
        # ⚠️ **On saute ce qui a été EXAMINÉ, pas ce qui porte une trouvaille.** La leçon des
        # mises en garde : les unités où le modèle a justement répondu « rien à signaler »
        # repasseraient à chaque relance, et un second passage rendrait d'autres résultats sur
        # des unités déjà jugées, sans qu'on sache lesquelles croire.
        deja = {
            r[0] for r in await s.execute(
                select(CorpusExaminationModel.pericope_id).where(
                    CorpusExaminationModel.dimension == _DIMENSION
                )
            )
        }
        # Les neuf notes posées à la main précèdent le registre : leur unité est examinée, quoi
        # qu'en dise une table créée après elles.
        deja |= {
            r[0] for r in await s.execute(
                select(CorpusContextNoteModel.pericope_id).distinct()
            )
        }
        unites = list((await s.execute(select(CorpusPericopeModel))).scalars())

        # ⚠️ **Nommer la version.** Le corpus porte quatre traductions ; charger sans filtre
        # laisserait la dernière écraser les autres, et le texte montré au modèle ne serait pas
        # celui contre lequel la curation a été écrite.
        versets: dict[tuple[int, int, int], tuple[str, str]] = {}
        for rang, chapitre, verset, corps, norme in await s.execute(
            select(
                CorpusVerseModel.book_id, CorpusVerseModel.chapter,
                CorpusVerseModel.verse, CorpusVerseModel.body, CorpusVerseModel.body_norm,
            )
            .join(CorpusVersionModel, CorpusVersionModel.id == CorpusVerseModel.version_id)
            .where(CorpusVersionModel.code == VERSION_DE_CURATION)
        ):
            versets[(rang, chapitre, verset)] = (corps, norme)

        #: La rareté de chaque mot, telle que le corpus l'a mesurée — c'est elle qui décide
        #: si un renvoi hors du livre prouve quelque chose. Voir `_IDF_ANCRAGE`.
        idf: dict[str, float] = {
            token: valeur for token, valeur in await s.execute(
                select(CorpusIdfModel.token, CorpusIdfModel.idf).where(
                    CorpusIdfModel.language == "fr"
                )
            )
        }

    # L'ordre de lecture de chaque livre — c'est lui qui donne le voisinage sans avoir à
    # raisonner sur les fins de chapitre, dont les longueurs varient.
    suite: dict[int, list[tuple[int, int]]] = {}
    for rang, chapitre, verset in versets:
        suite.setdefault(rang, []).append((chapitre, verset))
    for places in suite.values():
        places.sort()

    a_faire = [
        u for u in sorted(unites, key=lambda u: (u.book_id, u.start_ch, u.start_v))
        if u.id not in deja
        and (livre_voulu is None or par_rang.get(u.book_id, ("", ""))[0] == livre_voulu)
    ]
    if limite is not None:
        a_faire = a_faire[:limite]

    print(f"  {len(unites)} unites, {len(deja)} deja examinees")
    print(f"  {len(a_faire)} a curer — modele {reglages.mistral_model}")
    print(f"  genre '{_GENRE}' seulement — forme attendue : {_ATTENDU}\n")
    if not a_faire:
        return

    verrou = asyncio.Semaphore(CONCURRENCE)
    cadence = Cadence(INTERVALLE)
    rejets: dict[str, list[tuple[str, list]]] = {motif: [] for motif in _MOTIFS}
    taches = []
    references: dict[UUID, str] = {}
    for u in a_faire:
        nom = par_rang.get(u.book_id, ("", "?"))[1]
        reference = f"{nom} {u.start_ch}:{u.start_v}-{u.end_v}"
        references[u.id] = reference
        places = suite.get(u.book_id, [])
        debut = bisect_left(places, (u.start_ch, u.start_v))
        fin = bisect_left(places, (u.end_ch, u.end_v))
        dedans = places[debut : fin + 1]
        corps = "\n".join(
            f"{c}:{v}  {versets[(u.book_id, c, v)][0]}" for c, v in dedans
        )
        texte_norme = " ".join(versets[(u.book_id, c, v)][1] for c, v in dedans)
        avant = "\n".join(
            f"{c}:{v}  {versets[(u.book_id, c, v)][0]}"
            for c, v in places[max(0, debut - _VOISINAGE) : debut]
        )
        apres = "\n".join(
            f"{c}:{v}  {versets[(u.book_id, c, v)][0]}"
            for c, v in places[fin + 1 : fin + 1 + _VOISINAGE]
        )
        invite = (
            f"{reference} — « {u.label or 'sans titre'} » (livre : {nom})\n\n"
            f"CE QUI PRECEDE :\n{avant or '(debut du livre)'}\n\n"
            f"LE PASSAGE :\n{corps}\n\n"
            f"CE QUI SUIT :\n{apres or '(fin du livre)'}"
        )

        unite = Unite(u.book_id, frozenset(c for c, _ in dedans))

        def verifier(contenu: str, ou=unite, norme=texte_norme) -> list[str] | None:
            return _notes_depuis(contenu, ou, norme, versets, livres, idf, rejets)

        taches.append(_une_unite(ia, verrou, cadence, u.id, invite, verifier))

    faites = sautees = sans_note = 0
    distribution = {0: 0, 1: 0, 2: 0}
    maintenant = datetime.now(UTC)
    lot: list[CorpusContextNoteModel | CorpusExaminationModel] = []

    for fini in asyncio.as_completed(taches):
        unite_id, notes = await fini
        if notes is None:
            # Une panne n'est pas un examen : l'unité doit revenir au prochain passage.
            sautees += 1
            continue
        faites += 1
        distribution[len(notes)] = distribution.get(len(notes), 0) + 1
        lot.append(CorpusExaminationModel(
            pericope_id=unite_id, dimension=_DIMENSION, found=len(notes),
            examined_by=SIGNATAIRE_IA, examined_at=maintenant,
        ))
        if not notes:
            sans_note += 1
            continue
        for ordinal, corps in enumerate(notes, start=1):
            lot.append(CorpusContextNoteModel(
                id=uuid4(), pericope_id=unite_id, context_kind=_GENRE,
                body=corps, ordinal=ordinal,
                source_ref=f"{references[unite_id]} (LSG 1910) — renvois resolus, non relu",
                reviewed_by=SIGNATAIRE_IA, reviewed_at=maintenant,
            ))
        if len(lot) >= 400:
            await _ecrire(lot)
            lot = []
            print(f"  … {faites}/{len(taches)} unites")

    if lot:
        await _ecrire(lot)

    print(f"\n  {faites} unites curees, {sautees} sautees")
    print(f"  {sans_note} sans aucune note "
          f"({100 * sans_note / (faites or 1):.0f} %) — c'est une reponse juste")
    print(f"  distribution (attendu : {_ATTENDU}) :")
    for combien in sorted(distribution):
        print(f"    {combien} note(s)   {distribution[combien]:>6}  "
              f"{100 * distribution[combien] / (faites or 1):5.1f} %")
    _dire_les_prises(rejets)


def _dire_les_prises(rejets: dict[str, list[tuple[str, list]]]) -> None:
    """⚠️ **Lire les prises avant de croire l'instrument.**

    Le détecteur d'écarts a signalé neuf formes interdites dont huit étaient les meilleures
    lignes du corpus. Un vérificateur qui ne montre pas ce qu'il jette se règle à l'aveugle ;
    celui-ci imprime deux exemples par motif, en entier."""
    total = sum(len(v) for v in rejets.values())
    if not total:
        return
    print(f"\n  {total} notes refusees — a lire avant de croire le verificateur :")
    for motif in _MOTIFS:
        pris = rejets[motif]
        if not pris:
            continue
        print(f"    {motif:24} {len(pris):>5}")
        for exemple, renvois in pris[:2]:
            print(f"      | renvois declares : {renvois}")
            print(f"      | {_lisible(exemple)}")


def _lisible(texte: str) -> str:
    """La console Windows n'est pas en UTF-8 ; une note accentuee ne doit pas tuer le lot."""
    encodage = sys.stdout.encoding or "utf-8"
    return texte.encode(encodage, errors="replace").decode(encodage)


async def _ecrire(lot: list[CorpusContextNoteModel | CorpusExaminationModel]) -> None:
    async with async_session_factory() as s:
        s.add_all(lot)
        await s.commit()


def main() -> None:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--livre", help="code OSIS, ex. Hag, Rom, John")
    analyseur.add_argument("--limite", type=int, help="nombre d'unites")
    analyseur.add_argument(
        "--purge", action="store_true",
        help="efface les notes litteraires de l'IA (jamais celles relues a la main)",
    )
    arguments = analyseur.parse_args()
    asyncio.run(curer(arguments.livre, arguments.limite, arguments.purge))


if __name__ == "__main__":
    main()
