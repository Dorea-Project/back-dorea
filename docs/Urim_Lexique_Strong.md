# Urim — le lexique Strong : ce qui est libre, ce qui ne l'est pas

> **Nature :** note d'acquisition. Écrite le **2026-08-13** après vérification des sources.
> **Née d'une demande** : *« pour les mots originaux, il y a le sens littéralement sous une
> désignation — pour soulier, ce qu'on porte sous le pied »*.
> Prolonge [`Urim_Livrable.md`](Urim_Livrable.md) §8 ter.

---

## 1. Ce qu'il faut, et ce que ça vaut

Deux choses distinctes, souvent confondues :

| # | Ce qu'on veut | À quoi ça sert dans la note |
| :-- | :-- | :-- |
| **A** | **La glose** — le sens littéral d'un lemme | remplir `urim_corpus_lemma.gloss`, vide aujourd'hui |
| **B** | **L'alignement mot à mot** — quel mot français rend quel mot grec | répondre à *« quel mot est-ce qu'il remplace ? »* autrement que par un indice |

**B est le plus dur, et c'est l'inverse de l'intuition.**

---

## 2. L'état de la base — mesuré, pas supposé

| Fait | Mesure |
| :-- | :-- |
| `urim_corpus_lemma.gloss` | **vide** — 0 ligne renseignée |
| Lemmes **hébreux** | 8 640, **tous avec un `strong_code`** (semés avec l'OSHM) |
| Lemmes **grecs** | 5 461, **aucun `strong_code`** — MorphGNT n'en porte pas |

> ⚠️ **Le pont n'existe qu'à moitié.** Côté hébreu, un lexique se branche demain sur les codes
> déjà là. Côté grec — celui que la note affiche aujourd'hui — il faut **d'abord** un mapping
> lemme MorphGNT → numéro Strong.

---

## 3. Les licences — vérifiées le 2026-08-13

| Ressource | Langue | Licence | Verdict |
| :-- | :-- | :-- | :-- |
| **Strong's Concordance, 1890** (l'original) | anglais | **domaine public** | ✅ librement utilisable, y compris pour en faire une traduction |
| **STEPBible TBESG / TBESH** (Tyndale House) | anglais | **CC BY 4.0** | ✅ redistribuable avec attribution ; TBESH porte les Strong étendus, TBESG les définitions grecques |
| **OpenScriptures Hebrew Lexicon** | anglais | **CC BY 4.0** | ✅ idem |
| **Le Strong « français »** tel qu'il circule (FreLSG et la plupart des logiciels francophones) | français | ⛔ **sous copyright** — *« Strongs (c) Timnathserah, Inc — Canada & Éditions CLE — Villeurbanne »* | ⛔ **inutilisable en l'état** |
| Le texte **Louis Segond 1910** lui-même | français | domaine public | ✅ déjà en base |

> **Le résultat de la recherche tient en une phrase** : *tout ce qui est libre est en anglais,
> et tout ce qui est en français est sous copyright.* Y compris le balisage Strong du texte
> français — c'est-à-dire exactement **B**, l'alignement mot à mot.

---

## 4. Les trois issues, et ce que chacune coûte

| | Ce qu'on fait | Ce qu'on obtient | Ce que ça coûte |
| :-- | :-- | :-- | :-- |
| **(a)** | Charger **TBESG/TBESH** tels quels | une glose **en anglais** sous chaque mot | gratuit et immédiat — mais le lecteur est un pasteur ivoirien : lui servir *« sandal, shoe »* est une demi-réponse |
| **(b)** | **Traduire nous-mêmes** le lexique du domaine public | la glose **en français**, à nous, redistribuable | ~14 000 entrées. C'est **une traduction d'une source publiée**, pas une invention — et elle reste **vérifiable** si l'entrée anglaise voyage à côté |
| **(c)** | **Négocier** une licence (Timnathserah / Éditions CLE) | le français déjà fait, et l'alignement **B** avec | un délai et un contrat — le seul chemin qui règle **B** proprement |

### Ce que je recommande

**(b) pour la glose, (a) comme filet, et (c) ouvert en parallèle pour l'alignement.**

⚠️ **Et (b) demande une décision que vous seul pouvez prendre**, parce qu'elle frotte contre la
règle du dépôt : *le sens s'acquiert, il ne se génère pas*. Traduire n'est pas inventer — la
définition existe, elle est publiée, elle est signée Strong. Mais la traduction, elle, sera
produite par une machine.

**La parade qui rend (b) acceptable, et sans laquelle il faut dire non** :

1. **l'entrée anglaise d'origine est stockée à côté de la traduction** — une glose française
   contestée se vérifie contre sa source en un coup d'œil ;
2. **le numéro Strong est affiché** : la note dit d'où vient le sens, comme elle dit déjà qui a
   relu la péricope ;
3. **rien n'est traduit qui ne soit sourcé** — pas d'entrée « complétée » quand le lexique se
   tait.

Sans ces trois-là, on retombe exactement sur ce que la feuille de route refusait : *« une glose
inventée aurait l'air d'une source »*.

---

## 5. Ce qui reste vrai en attendant

La note ne dit **pas** le sens, et elle le dit. À la place : la phonétique (mécanique), la
morphologie décodée, la référence, les occurrences **avec leur verset français**, et les mots
que ces versets ont en commun. Sur `πρῶτος`, cela donne *« ces versets ont en commun :
premièrement »* — un fait vérifiable, jamais une définition.

**C'est une bonne réponse par défaut, et elle le restera** : même avec un lexique, montrer les
trois versets vaut mieux qu'un synonyme.

---

## 6. Questions ouvertes

| # | Question |
| :-- | :-- |
| **L1** | **Traduit-on le lexique du domaine public (b) ?** C'est la décision de principe — traduire une source publiée n'est pas inventer une définition, mais c'est une machine qui écrira le français |
| **L2** | **Ouvre-t-on une demande de licence** à Timnathserah / Éditions CLE ? C'est le seul chemin propre vers l'alignement mot à mot |
| **L3** | **Le mapping grec → Strong** : par quelle source (STEPBible TAGNT porte les deux) ? Sans lui, la moitié grecque du corpus n'a aucun pont vers un lexique |
| **L4** | Si (a) est retenu en filet : **affiche-t-on une glose anglaise** à un pasteur francophone, ou vaut-il mieux ne rien afficher ? |
