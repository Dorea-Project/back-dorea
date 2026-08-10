# Urim — feuille de route pour boucler

> **Nature :** état des lieux mesuré et ordre de marche. Pas une spec — les specs sont
> ailleurs : [le moteur](UrimEngine_Specs_Implementation.md),
> [l'architecture](Dorea_Urim_Architecture_v2.md), [la porte d'entrée](Urim_Porte_Entree.md),
> [le domaine utilisateur](Urim_Domaine_Utilisateur.md).
>
> **Mesuré le 10/08/2026 sur `main` à `1d215ef`** — 201 opérations HTTP, 1 362 tests. Tous les
> chiffres de ce document viennent de la base et de l'OpenAPI, pas d'une estimation.

---

## 1. Ce qui tourne

**Le corpus.** La LSG 1910 entière — 31 170 versets. 4 561 péricopes couvrant **1 189 chapitres
sur 1 189**. Le grec du Nouveau Testament : 137 554 mots, 5 461 lemmes, morphologie décodée par
table (MorphGNT/SBLGNT, CC BY 4.0).

**Le moteur.** Les huit étages s'enchaînent de la saisie au thème proposé. La porte d'entrée
devine seule — référence, citation, intention — sans que le pasteur coche quoi que ce soit.
Mistral sert quatre lectures, toutes à la **bordure**, jamais dans un étage : retrouver un
passage désigné, nommer les loci dans la langue du pasteur, lever les drapeaux de forme,
proposer des passages par le sens.

**14 routes HTTP**, dont `GET /passages` (étudier un passage sans s'engager dessus) et
`PATCH /pericopes/{id}` (un relecteur reprend une unité à son compte).

---

## 2. Ce qui est faux, par ordre de conséquence

### 2.1 Le dominant est mal attribué — **le seul défaut qui produit un mauvais sermon**

`theologie_propre` est dominant sur **2 644 unités sur 4 561** (58 %). Et l'angélologie l'est
sur Hébreux 13:1-6, au motif de « quelques-uns ont logé des anges, sans le savoir » — une
illustration de passage au verset 2, pas le sujet du texte.

La chaîne est courte et sans amortisseur : le dominant pose l'axe, l'axe pose le thème. Un
pasteur préparant un culte sur l'adultère s'est vu proposer l'angélologie.

Le reste des défauts se **voit** (un tableau vide, un refus). Celui-là ne se voit pas : il
produit une réponse plausible et fausse, ce qui est la pire des deux.

### 2.2 La curation est incomplète

| couche | unités faites | manque |
| :-- | --: | --: |
| péricopes | 4 561 | — |
| pesées doctrinales | 3 758 | **803** |
| faisabilité homilétique | 2 913 | **1 648** |
| mises en garde | 11 lignes | ~4 550 unités |
| contexte historique/littéraire | 9 lignes | ~4 550 unités |
| variantes textuelles | 1 ligne | — |

Les deux premières lignes sont mécaniques : les scripts sont reprenables, il suffit de les
relancer. Les trois suivantes ne le sont pas — voir §4.

### 2.3 Tout est signé `ia-mistral`

4 553 péricopes, 37 500 pesées, 52 290 couples. **Aucune relecture humaine n'a eu lieu.** La
signature remonte jusqu'à l'écran du pasteur (`curation_reviewed_by`) et la route pour la
reprendre existe (`PATCH /pericopes/{id}`, `PUT /pericopes/{id}/bearings`) ; personne ne s'en
est encore servi.

C'est acceptable pour une bêta, et ça ne l'est pas pour une publication : le pasteur doit
pouvoir distinguer ce qu'un bibliste a relu de ce qu'un modèle a produit, et aujourd'hui la
réponse est *rien n'a été relu*.

### 2.4 La couche `application` n'a aucun test

Chaque défaut trouvé pendant la mise au point l'a été **par l'utilisateur, pas par la suite** :
un 500 sur toutes les ouvertures, un 422 au clic sur six options, le bouclage du chemin
intention, la citation abîmée classée en conviction, `shape_homiletic` qui refusait ce que
personne n'avait relu.

Les 1 362 tests couvrent le moteur pur et les lecteurs d'index. Ni `UrimStudyService`, ni les
routes. C'est structurel, et c'est la raison pour laquelle les régressions se découvrent en
démonstration.

### 2.5 Deux marges à surveiller

**Le seuil de citation.** `l'amour fraternel n'existe plus dans l'église` mesure 0,427 pour un
seuil à 0,45. Si une intention bascule un jour en citation, ce sera par là.

**La latence.** ~8 s en régime normal sur le chemin intention (trois appels de modèle en
parallèle), ~40 s au premier appel d'un processus — c'est l'index qui se charge, pas le modèle.
Un client mobile qui tape un serveur fraîchement démarré doit préchauffer ou patienter.

---

## 3. Ce qui n'existe pas encore — le domaine utilisateur

C'est l'objet de [`Urim_Domaine_Utilisateur.md`](Urim_Domaine_Utilisateur.md), et c'est le
chantier qui manque pour qu'Urim soit **distribuable seul**. La règle qui le gouverne tient en
une ligne :

> Ce qui est vrai de la personne vit dans le noyau. Ce qui n'est vrai que d'Urim vit dans Urim.

### 3.1 Vérification de la spec contre `main`

Elle a été rédigée sur `4c56d54` ; voici ce qu'elle vaut à `1d215ef`.

| affirmation | vérifié |
| :-- | :-- |
| `auth` a 6 routes, sans reset ni suppression | **exact** — `register`, `verify-registration`, `login`, `verify-device`, `refresh`, `logout` |
| `account` a `change-password` et `change-phone` en request/confirm | **exact** — 4 routes |
| `PUT /iam/me/birthday` est livré | **exact** |
| il n'y a **pas** de `GET /iam/me` | **exact** — seules `memberships`, `membership`, `birthdays` existent |
| `urim_user_settings` et `urim_workspace` n'existent pas | **exact** — aucune des deux tables |

**Deux écarts à corriger dans la spec :**

`urim_corpus_version` ne porte pas de colonne `name` mais **`label`**, et il n'y a **qu'une
seule version en base** : la LSG. Ostervald, Darby et Segond 21 n'existent nulle part. Le
`available_versions` du §3.1 décrit donc un catalogue qui n'a pas de contenu — il faudra
acquérir ces textes (Ostervald et Darby sont dans le domaine public, la S21 ne l'est pas) avant
que l'écran de réglages ait quelque chose à proposer.

`GET /urim/settings` ne peut pas non plus rendre `workspaces` tant que `urim_workspace`
n'existe pas. Les deux points sont liés : le catalogue se dérive de l'espace courant.

### 3.2 Les sept éléments

| # | élément | contexte | taille | bloque |
| :-- | :-- | :-- | :-- | :-- |
| 1 | `GET /iam/me` — profil en un appel | `iam` | trivial | le premier écran d'Urim |
| 2 | `urim_user_settings` + `GET`/`PATCH /urim/settings` | `urim` | petit | le choix de version |
| 3 | `urim_workspace` + résolution paresseuse | `urim` | petit | Urim autonome |
| 4 | `POST /auth/reset-secret-code` (+ confirm) | `auth` | petit | **la distribution** |
| 5 | `POST /account/delete-account` (+ confirm) | `account` | petit | les stores, la loi 2013-450 |
| 6 | `GET`/`DELETE /account/devices` | `account` | petit | la parade sécurité |
| 7 | Langue d'interface | `iam` | petit | l'internationalisation |

**4, 5 et 6 ne sont pas des chantiers Urim** : ce sont des lacunes du noyau que la distribution
publique rend visibles, et les combler profite aussi à Dorea. Aucun ne bloque une bêta fermée ;
tous bloquent la publication.

⚠️ **Le piège nommé par la spec, et il faut le répéter ici** : ne pas créer de « profil Urim ».
L'écran de compte s'**assemble** de quatre sources — `iam/me` pour l'identité, `urim/settings`
pour les réglages, `iam/me/memberships` pour l'église, `account` pour la sécurité. Recopier le
prénom dans une table `urim_*` créerait une seconde vérité qui divergerait au premier changement.

---

## 4. Ce que je ne recommande pas de générer

**Les mises en garde** (`caveat`) et le **contexte historique**. Dire ce qu'un texte *ne dit
pas* engage plus lourdement que dire ce qu'il dit, et un caveat confessionnel nomme des
traditions — se tromper là ne produit pas un sermon à côté, il produit une offense.

**La glose française** des lemmes grecs. MorphGNT n'en porte aucune et les lexiques libres sont
en anglais ; la faire produire par un modèle donnerait des définitions qu'aucun pasteur ne
vérifiera. Il faut un lexique, pas une génération.

**L'hébreu**, en revanche, se **récupère** : Open Scriptures `morphhb` (WLC), XML par livre. Ce
n'est pas de la génération, c'est le même geste que le grec. 23 243 versets de l'AT attendent.

---

## 5. L'ordre de marche

### Lot A — la justesse *(avant tout le reste)*

1. **Reprendre l'invite du dominant** et repeser les 4 561 unités. La règle qui manque : *le
   dominant est ce dont le texte TRAITE, jamais le détail le plus saillant ; une illustration
   de passage n'est pas un dominant.* ~1 h d'appels.
2. **Finir les 803 pesées et 1 648 faisabilités** manquantes — scripts reprenables, mécanique.

### Lot B — le filet *(avant d'ajouter quoi que ce soit)*

3. **Tests sur `UrimStudyService` et les routes mobile.** Les cinq défauts trouvés en
   démonstration en sont le cahier des charges : chacun mérite son test de non-régression.

### Lot C — le domaine utilisateur *(la distribution)*

4. `GET /iam/me`, puis `urim_user_settings`, puis `urim_workspace` — dans cet ordre, chacun
   débloquant le suivant.
5. Les trois lacunes du noyau : `reset-secret-code`, `delete-account`, `devices`.

### Lot D — la profondeur *(quand le reste tient)*

6. **L'hébreu** (`morphhb`) — l'AT sans original est aujourd'hui les trois quarts de l'Écriture.
7. **Le prompt dynamique** : `raw_input` n'existe qu'à l'ouverture. Le pasteur ne peut pas
   demander « et ce mot ? » en cours de préparation, alors que c'est le geste le plus naturel
   une fois le texte sous les yeux.
8. **Ostervald et Darby** — pour que le catalogue de versions ait un contenu.

### Hors lot — la relecture humaine

Elle ne se planifie pas comme du code : elle demande un bibliste et du temps. Mais la surface
existe, et chaque unité re-signée fait reculer le `ia-mistral` d'un cran. C'est le seul chantier
dont la fin ne dépend pas de nous.
