# Les notes de contexte — pourquoi `litteraire` est peuplé et `historique` restera vide

`CorpusContextNoteModel` porte une règle nommée S40 :

> **Sourcé, ou absent. Il n'y a pas de troisième possibilité.**
> Ni contexte reconstitué, ni « on suppose que ». Un contexte historique inventé est le genre
> d'erreur qu'un pasteur répète en chaire avec assurance, parce qu'elle avait l'air documentée.

Cette dimension était à **6 unités sur 4 561** — 0,1 %. La question posée avant d'écrire une
ligne de code n'était donc pas *comment la remplir*, mais **si une machine en avait le droit**.

## La question, et pourquoi elle ne se règle pas comme les mises en garde

Le lot des mises en garde a pu exister parce que leur source est **le passage lui-même** :
« le texte ne dit pas X » se contrôle en relisant. Une note de contexte historique — une
coutume, une monnaie, une distance, un usage juridique — a pour source une érudition extérieure
que le modèle **inventera**, et que rien dans le dépôt ne contredit.

Ce n'est pas une crainte abstraite. Aucun des cinq détecteurs d'écarts ne verrait passer une
érudition fausse :

| détecteur | ce qu'il sait voir | pourquoi il rate une fausse realia |
|---|---|---|
| D1 contradiction | un caveat sur un locus `absent` | une note de contexte ne porte pas de locus |
| D2 gabarit | une formule répétée sur des centaines d'unités | une invention est unique par nature |
| D3 forme interdite | manuscrit, apparat, autorité nommée | « 520 av. J.-C. » ne nomme personne |
| D4 aberration | un profil hors de sa distribution | une note par unité est un profil normal |
| D5 citation fantôme | des mots cités absents du passage | une date n'est pas une citation |

**Le détecteur d'écarts sait voir une incohérence, pas une érudition fausse.** C'est la limite
que ce lot devait respecter, et non contourner.

## Ce que l'étalon a dit, et il ne dit pas ce que le schéma laisse croire

Les neuf notes posées à la main sont le seul étalon disponible. Réparties par `context_kind`,
elles suggèrent que le partage utile serait `litteraire` / `historique`. Réparties par **ce sur
quoi elles s'appuient**, elles disent tout autre chose :

| note | appui | dans le dépôt ? |
|---|---|---|
| Jean 3 · litt. — « reprend Nombres 21:8-9 » | Nb 21:8-9 | ✅ |
| Rom 8 · litt. — « le *donc* du v. 1 rattache à 7:24-25 » | Rm 7:24-25 | ✅ |
| 2 Co 5 · litt. — « chiasme autour du v. 18 » | le passage | ✅ |
| 1 R 21 · litt. — « les mots de Jézabel (9-10) exécutés (12-13) » | le passage | ✅ |
| Jean 3 · **hist.** — « pendant la Pâque (2:23) » | **Jn 2:23** | ✅ |
| 1 R 21 · **hist.** — « héritage inaliénable (Lévitique 25:23) » | **Lv 25:23** | ✅ |
| 2 Co 9 · **hist.** — « la collecte (1 Co 16:1-4, Rm 15:25-28) » | **ces versets** | ✅ |
| 2 Co 5 · hist. — « après une crise avec Corinthe » | la lettre entière | ~ |
| **Aggée · hist. — « 520 av. J.-C., seize ans après le retour »** | une chronologie extérieure | ❌ |

Trois des quatre notes « historiques » ne survivent que parce qu'elles portent un **renvoi
biblique** : ce sont des observations littéraires en habit d'historien. La quatrième est le cas
de test de S40 — vraie, invérifiable, et parfaitement imitable par un modèle sur 4 561 unités.

D'où la règle du lot, plus étroite que `context_kind` :

> **Une note est légitime exactement quand tout son contenu se résout à un endroit du corpus.**

Et cette propriété-là, contrairement à « est-ce théologiquement juste », **une machine sait la
vérifier**. `historique` n'a pas de vérificateur possible ; il reste aux quatre lignes humaines.

## Le mécanisme : le modèle déclare ses sources, la machine les résout

Les autres lots vérifient la **forme** d'une ligne générée. Celui-ci vérifie son **appui**. Le
modèle rend ses renvois dans un champ séparé du corps ; chacun est cherché dans
`urim_corpus_verse` (version LSG explicitement nommée) ; un renvoi qui ne tombe sur aucun verset
**jette la note entière**. « 520 av. J.-C. » ne cite aucun verset : refusé sans qu'on ait eu à
détecter une chronologie.

Trois gardes s'y ajoutent, chacun pour un contournement précis :

- **Un nom de livre présent et inconnu fait tomber la note**, sans repli sur le livre de
  l'unité. Sinon « Hénoch 3:2 » se résoudrait en Genèse 3:2, qui existe : l'invention passerait
  *en se faisant vérifier*.
- **La chronologie est refusée en dur**, car une date peut voyager en passager clandestin d'un
  renvoi juste — « deuxième année de Darius (1:1), soit 520 av. J.-C. ».
- **La note doit montrer sa référence au lecteur.** C'est le garde qui s'est révélé le plus
  utile, et pour une raison que je n'avais pas prévue : sur les Proverbes, le modèle accrochait
  des renvois justes et résolus à des notes qui ne s'en servaient pas — `['13:7', '13:8']` sur
  une note parlant des v. 11-12. **Un renvoi que le modèle n'écrit pas dans sa propre phrase est
  un renvoi dont il ne s'est pas servi.**

Un quatrième a existé et **les prises l'ont condamné** : exiger qu'un renvoi hors du livre
partage une ancre rare avec le passage. L'idée est juste, l'instrument ne l'est pas — un
recouvrement lexical mot à mot est un mauvais témoin du lien entre deux textes. Il refusait
2 Rois 23:25 renvoyant à Deutéronome 6:5, *« de tout son cœur, de toute son âme et de toute sa
force »* : la citation la plus littérale de l'Ancien Testament, perdue parce que le mot partagé
le plus rare était `force` à 4,76, sous un seuil de 5,0. **Une citation quasi verbatim ne
partage pas un mot rare, elle partage une phrase.** Rétrogradé en signal, comme le détecteur de
négation de doctrine l'avait été avant lui.

Le lot montre aussi au modèle **le voisinage** — six versets avant, six après. Une note
littéraire parle de ce qui précède et de ce qui suit ; sans ces versets dans l'invite, il les
inventerait, et on serait revenu au problème qu'on croyait avoir résolu.

## Ce que le témoin a appris, et que je n'aurais pas deviné

Cinq passages sur les **mêmes 77 unités** des Proverbes — un livre dont les chapitres 1-9 sont
un discours suivi et les chapitres 10+ des sentences indépendantes.

| tour | 0 note | 1 note | 2 notes |
|---|---|---|---|
| 1 | 2,6 % | 24,7 % | 72,7 % |
| 3 | 14,3 % | 33,8 % | 51,9 % |
| 5 | 15,6 % | 59,7 % | 24,7 % |

**Mais le chiffre qui a servi à régler n'est aucun de ceux-là.** C'est l'écart entre les deux
moitiés du livre. Au tour 3, les deux genres donnaient *exactement* 14,3 % de zéro — et les
sentences en produisaient même un peu plus que le discours. Un taux insensible au texte est un
quota, quelle que soit sa valeur : même famille de preuve que le « trou à un » des mises en
garde. Au tour 5 : **2,9 % de zéro sur le discours, 25,6 % sur les sentences.**

Trois causes, toutes lues dans les prises imprimées, aucune devinée :

1. **Je lui avais donné le gabarit moi-même.** « Progression en trois temps » figurait dans ma
   liste des espèces ; il me l'a renvoyé mot pour mot sur un distique des Proverbes.
2. **L'exigence de renvoi était devenue un rite.** Des références justes et résolues, accrochées
   à des notes qui ne s'en servaient pas. C'est ce qui donne son vrai sens au contrôle *aucun
   renvoi visible* : un renvoi que le modèle n'écrit pas dans sa propre phrase est un renvoi
   dont il ne s'est pas servi.
3. **La règle demandait un jugement là où il fallait un geste.** « Est-ce important ? » ne
   filtre rien ; « lis le verset d'avant et celui d'après, parlent-ils d'autre chose ? » filtre.

### Et trois fois, c'est l'instrument qui avait tort

Le vérificateur a rejeté de bonnes notes trois fois de suite, toujours sur la forme d'une
référence — « au v. 19 » au lieu de « 2:19 », « (1:12-15) » pour un renvoi à 1:13, « v. 26 »
après que la consigne lui eut demandé de déclarer ses propres versets. **La première de ces
règles, l'étalon humain y aurait échoué** : les neuf notes écrivent *« le chiasme autour du
v. 18 »*, *« les mots de Jézabel (v. 9-10) »*.

C'est la leçon des neuf formes interdites du détecteur d'écarts dont huit étaient les meilleures
lignes du corpus. Un vérificateur qui ne montre pas ce qu'il jette se règle à l'aveugle ; le
lot imprime donc ses prises **avec les renvois déclarés**, parce que le motif seul m'a fait
deviner une fois — et deviner faux.

Le passage sur le corpus entier en a produit trois autres, et le compte final est **cinq
corrections, toutes contre l'instrument** : la forme « v. 19 », la plage qui contient le verset,
la forme courte que ma propre consigne appelait, la section entière (« Exode 25-31 »), et le
seuil d'ancrage. Aucune ne venait du modèle.

### La limite de la trace, et ce qu'elle rend irrécupérable

`urim_corpus_examination` enregistre **combien** de notes une unité a produites, jamais
**pourquoi** une candidate est tombée. Une unité dont la seule note a été rejetée à tort est
donc aujourd'hui indiscernable d'une unité honnêtement muette. Les prises ne vivent que dans la
sortie d'un passage, et seulement deux par motif.

Conséquence directe : les notes perdues aux deux pannes découvertes sur le corpus — la section
entière et le seuil d'ancrage — **ne sont pas rattrapables autrement qu'en repassant les livres
concernés**, et on ne sait pas lesquels. C'est le prix d'une trace qui compte au lieu de
consigner, et il se paie une fois le passage terminé.

## Ce qui est garanti, et ce qui ne l'est pas

**Garanti par la machine.** Chaque référence citée existe dans le texte en base ; aucune date,
aucun siècle numéroté, aucune ère ; aucun manuscrit ni autorité extérieure
(`verifier_forme_machine`, partagé avec la route Plateforme) ; la note montre au lecteur où
aller voir.

**Non garanti.** Qu'un chiasme annoncé en soit un. Le modèle peut décrire une construction que
le texte ne porte pas — c'est une affirmation *sur le passage*, du même genre que celles des
mises en garde, et elle se contrôle de la même façon : en relisant. C'est le niveau de risque
que tout ce corpus accepte, et il est **différent en nature** de celui que S40 refuse : une
érudition extérieure fausse n'a aucun contradicteur, un chiasme faux en a un, et il est en base.

Les notes sont signées `ia-mistral` et leur `source_ref` porte « non relu ». Elles sont un point
de départ pour un relecteur, jamais un état définitif — c'est la seule chose qui rend la
signature d'une machine acceptable ici.

## Lancer

```
python scripts/urim_curate_context.py                 # toutes les unités non examinées
python scripts/urim_curate_context.py --livre Prov    # un livre, pour juger
python scripts/urim_curate_context.py --livre Prov --purge --limite 80
```

⚠️ **`--purge` est bornée par `--livre`, et bornée au genre généré.** Sans la borne de livre,
éprouver une invite sur un livre effacerait la curation des soixante-cinq autres. Sans la borne
de genre, elle emporterait les notes `historique` posées à la main — l'étalon contre lequel tout
ce lot a été décidé.

Le registre `urim_corpus_examination` (dimension `context_note`) enregistre **l'examen sans
trouvaille**. Sans lui, une unité regardée où le modèle a justement répondu « rien à signaler »
serait indiscernable d'une unité jamais regardée : la couverture mentirait, et rattraper cent
unités en referait des milliers. `scripts/urim_couverture.py` distingue les deux.
