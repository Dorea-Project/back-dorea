# Urim — l'arbre conversationnel

> **Nature :** la carte de ce que la conversation rend possible, et la preuve qu'aucune branche
> ne se termine par un mur. `docs/Urim_Conversation.md` est le **contrat** — ce que le serveur
> promet au client. Ce document-ci est le **territoire** : ce que le pasteur reçoit réellement,
> tour après tour, sur chacun des chemins.
>
> Établi le 2026-08-13 en marchant l'arbre contre le corpus réel — 31 170 versets, 4 561 unités
> curées. `scripts/urim_banc_arbre.py` refait la marche ; `tests/contexts/urim/test_arbre_conversationnel.py`
> tient la propriété en CI.

---

## 1. La règle, et pourquoi elle se perdait ici

Le produit tient partout la même règle : **aucun mur un vendredi soir**. `Outcome.DEGRADE` ne
coupe jamais le pipeline, les adaptateurs `Null*` sont des états de production, une panne de
modèle n'est jamais une panne d'Urim.

Cette règle était **tenue par le moteur et perdue à la présentation**. Le moteur ne peut pas
fabriquer de cul-de-sac : `StageResult` refuse un `AWAIT` sans options, `DEGRADE` continue,
`REFUSE` porte son motif. Mais le tour, lui, est construit **après** — dans `interface/turn.py` —
à partir d'un état où les options ont été marquées, filtrées, et présentées. C'est là que les
deux murs vivaient, et personne ne les y cherchait.

> Un chemin sans issue ne se voit pas en lisant le code. Il se voit en marchant.

La question posée à chaque tour, et c'est la seule :

    Après ce tour, le pasteur a-t-il quelque chose à faire ?

Trois réponses acceptables — des options à toucher, une action ouverte, ou une barre de saisie
**dont la passerelle est nommée**. Rien des trois : c'est un mur.

⚠️ **`expects: text` sans `ask` ne compte pas.** Un champ vide sans rien qui dise ce qu'on
attend est un cul-de-sac poli — et c'est la forme sous laquelle un mur survit à une relecture
de code, parce que la structure a l'air correcte.

---

## 2. Ce que l'espace est réellement

L'énoncé de départ — 7 intentions × 8 étages × 4 issues — décrit **224 combinaisons**. Le compte
réel est bien plus petit, et l'écart est l'information :

| | |
| :-- | :-- |
| 9 entrées de `PIPELINE` × 4 issues | **36 cellules** |
| ce qu'un étage sait produire | **19 cellules** (les autres sont interdites par sa doctrine) |
| ce qui **rend un tour** au pasteur | **13 cellules terminales** |
| ce que la marche a touché | **11** en 127 tours |

Les 7 intentions ne multiplient rien **aujourd'hui** : l'aiguilleur n'est pas encore branché
dans la boucle (§5). Quand il le sera, il ajoutera des tours *à côté* du pipeline, pas dedans.

### Traversée, terminale, interdite

Trois statuts, et les confondre est ce qui fait croire à une couverture qu'on n'a pas.

- **traversée** — l'étage s'exécute et le pipeline continue. Son motif entre dans la trace,
  mais le tour affiché est celui d'un étage **plus loin**. Une cellule traversée ne peut pas
  être un mur : elle n'est jamais la dernière.
- **terminale** — le moteur s'arrête là. C'est cette cellule qui rend un tour, donc c'est
  elle, et elle seule, qui peut être un mur.
- **interdite** — l'étage ne sait pas produire cette issue, et c'est écrit dans sa doctrine :
  *« il ne refuse jamais »*, *« il ne rend jamais la main »*. Ce n'est pas un trou de test.

---

## 3. La carte

`·` interdite par la doctrine de l'étage · `→` traversée · **T** terminale (rend un tour)

| étage | `CONTINUE` | `AWAIT` | `REFUSE` | `DEGRADE` |
| :-- | :-- | :-- | :-- | :-- |
| `route_entry` | → routé | **T** dictée à confirmer | **T** charabia · livre inconnu | · |
| `weigh_conviction` | · | **T** axes · textes · passages | **T** rien de curé | · |
| `resolve_passage` | → résolu | **T** S24 · S16 · égalité | **T** aucun candidat | · |
| `bound_pericope` | → coïncide | **T** coupe · englobe | · | → hors corpus curé |
| `serve_corpus` | → domaine public | · | · | → plafond de licence |
| `load_context` | **T** *la relecture* | · | · | · |
| `bear_axes` | → un dominant | **T** plusieurs · portants | · | **T** rien de relu |
| `shape_homiletic` | → couple retenu | **T** les faisables | **T** aucun plan ne tient | → rien de relu |
| `propose_theme` | **T** le thème | · | · | · |

### Ce que chaque cellule terminale rend, et comment y arriver

| cellule | le tour | comment y arriver |
| :-- | :-- | :-- |
| `route_entry` · `AWAIT` | *« J'ai entendu : … C'est bien ce que vous vouliez ? »* + « Ce n'est pas ça » | une **dictée** dont la lecture est une intention (S36) |
| `route_entry` · `REFUSE` | *« Je ne sais pas quoi ouvrir avec cette saisie. »* barre ouverte | `« Zorobabel 3:5 »`, une saisie vide, `« jefgf »` |
| `weigh_conviction` · `AWAIT` | les 10 loci, ou les unités groupées par ce qu'elles font du sujet | toute intention |
| `weigh_conviction` · `REFUSE` | *« Sur cet angle, la curation n'a encore relu aucun texte. »* | **non visité** — exige un corpus sans dogmatique ou sans unité sur l'axe |
| `resolve_passage` · `AWAIT` | les livres possibles, les textes à égalité + « ce n'est pas une citation », ou **la correction proposée** | `« 1 Roi ou 2 Roi… »`, une citation de mémoire, `« Hébreux 2:29 »` avec modèle |
| `resolve_passage` · `REFUSE` | *« Je n'ai pas su ouvrir le passage que vous nommez. »* | `« Hébreux 2:29 »` **sans modèle branché** |
| `bound_pericope` · `AWAIT` | l'unité relue contre les bornes du pasteur, avec la conséquence | `« Luc 1:28 »`, `« Apocalypse 12 »` |
| `load_context` · `CONTINUE` | l'écran de **relecture** — pesées, faisabilité, thème, actions | rouvrir une préparation déjà décidée |
| `bear_axes` · `AWAIT` | les axes qui dominent, au même rang | `« Luc 1:26-38 »` (2 dominants) |
| `bear_axes` · `DEGRADE` | *« Le texte est là, entier — ce qui manque, c'est la relecture. »* | **« Mes bornes »** au bornage (S22) |
| `shape_homiletic` · `AWAIT` | les couples plan × matière, les refusés avec les faisables | toute unité curée |
| `shape_homiletic` · `REFUSE` | *« Aucun de ces plans ne tient sur cette unité. »* | **non visité** — exige une unité dont tous les couples sont refusés |
| `propose_theme` · `CONTINUE` | le thème, et les trois sorties dont deux verrouillées | aller au bout d'un chemin curé |

**Les deux cellules non visitées ne sont pas des trous du banc** : elles exigent un état du
corpus qui n'existe plus. La curation couvre aujourd'hui **les 66 livres**, chaque unité porte
ses pesées, et seules deux unités sur 4 561 n'ont pas de faisabilité relue. Elles restent dans
la carte parce qu'un corpus se sème, et qu'un semis neuf les rouvre.

### Ce que la carte dit et qui surprend

**`bound_pericope` ne refuse jamais, `serve_corpus` non plus, `load_context` ne rend jamais la
main.** Trois étages sur neuf ne peuvent pas interrompre. C'est le cœur du *aucun mur* : la
moitié du pipeline est structurellement incapable de fermer une porte.

**`serve_corpus` n'est jamais terminal** — donc le repli du plafond de licence, le seul
`DEGRADE` du moteur d'origine, **n'a jamais de tour à lui**. Le pasteur ne voit pas d'écran de
limite : il voit le tour suivant, et le motif du repli voyage dans la trace. C'était l'intention
écrite (*« pas de compteur visible »*), et la carte montre qu'elle est tenue mécaniquement.

**`load_context` n'a pas de phrase à lui** dans `_PAR_ETAGE`, et il est pourtant terminal à
chaque relecture. Il n'en a pas besoin : quand il termine, l'écran porte déjà le thème, la
faisabilité et les pesées, et c'est le bloc le plus avancé qui parle. Le seul point de couture
visible est que le `why` affiché est alors le motif du contexte — la dernière chose que le
moteur ait calculée, rarement la plus intéressante. On ne le réécrit pas : `why` est le motif du
moteur, tel quel, et c'est le filet doré.

---

## 4. Les murs trouvés, et ce qu'ils sont devenus

### Mur n°1 — la liste épuisée

Le pasteur écarte les dix loci l'un après l'autre. Le moteur, lui, n'a rien fait de mal : son
`AWAIT` est intact et ses options existent — elles sont seulement toutes reléguées. C'est la
présentation qui filtrait les écartées **après** avoir décidé qu'il y avait un choix à faire :

```
expects  choice          <- le client ouvre un selecteur
ask      Sur lequel prêchez-vous ?
blocks   [chips(0)]      <- ... sur zero pastille
```

**Réparé** dans `interface/turn.py` : les trois branches d'options testent désormais les
**vivantes**, plus aucun bloc vide n'est émis, `expects` retombe à `text`, et le tour nomme la
limite — celle du produit, jamais celle du pasteur :

> « Ces dix axes sont ce que la dogmatique de ce corpus sait nommer — un sujet peut n'entrer
> dans aucun. **Donnez-moi un texte, même un seul verset : je l'ouvre entier, avec ce qui en a
> été relu.** »

C'est la règle des deux répondeurs (`engine/repondeurs.py`), appliquée telle quelle : on nomme
ce qu'Urim est, on tend la passerelle, on situe où en est la préparation.

### Mur n°2 — le « voici » au-dessus de rien

Hors unité curée, la pesée doctrinale dégrade sans retenir d'axe ; sans axe, ni la mise en forme
ni le thème ne s'appliquent. Le pipeline s'arrête là — et le tour disait :

```
say      Voici ce que ce texte porte — et ce à quoi il résiste.
ask      (aucune)        expects text        blocks  (aucun)
```

La cause est plus large que la phrase : **`say` était indexé sur le nom de l'étage**, alors que
tous les étages servent plus d'un écran. Trois symptômes du même défaut, relevés en marchant :

1. `weigh_conviction` demandait *« Sur lequel prêchez-vous ? »* devant quatre péricopes ;
2. `bear_axes` annonçait *« Voici ce que ce texte porte »* devant un écran vide ;
3. `bear_axes` rendait **deux axes à choisir sans poser de question** — sa phrase était celle
   des pesées, qui n'appelle aucune réponse.

**Réparé** : la phrase suit **l'écran**, pas l'étage. L'écran ne peut pas mentir — c'est ce que
le pasteur a sous les yeux. Quand l'étage offre un choix, c'est le bloc des options qui parle ;
quand il n'offre rien, c'est le bloc le plus avancé, et le décor ambiant ne prend pas la parole
à sa place.

⚠️ **Ce mur est vivant, et il tient à un bouton.** Depuis que la curation couvre les 66 livres,
on ne l'atteint plus par un passage non curé — mais **« Mes bornes »** (S22) fait retomber
`pericope_id` à `None`, et rien de curé n'est plus lisible. Le pasteur catholique qui insiste
pour garder `Luc 1:28` seul y arrive en un tap. C'est le cas que le banc marche.

### Mur n°3 — `AWAIT` sans options : l'invariant tient

Les neuf constructions d'`Outcome.AWAIT` du moteur sont toutes gardées par un test de
non-vacuité en amont ; `_marquer_les_ecartees`, à la bordure, **marque et ne retire pas**. Aucun
chemin ne franchit `EngineInvariantError`.

Le seul endroit qui *retirait* des options est `_pastilles`, en aval du moteur — et c'est
exactement lui qui produisait le mur n°1. L'invariant n'a pas été franchi : il a été
**contourné**, une couche plus haut, là où il ne s'applique pas.

> C'est la leçon à garder de ce chantier : un invariant du moteur ne protège pas la
> présentation. Les deux murs étaient tous les deux dans `turn.py`.

---

## 5. Les sept intentions, et pourquoi elles n'entrent pas encore dans l'arbre

L'aiguilleur (`INTENTIONS_CONNUES`) n'existe **qu'à partir du deuxième tour**, et il n'est pas
encore branché dans la boucle — une autre worktree y travaille. Les intentions ne produisent donc
aujourd'hui aucun tour, et l'arbre ci-dessus est complet sans elles.

| code | ce qu'il rend | le tour, quand il sera branché |
| :-- | :-- | :-- |
| `preciser` | options `origin: entree` | des pastilles — jamais vide, l'étage 0 en pose toujours |
| `interroger_texte` | concordance, contexte, motif, original | ⚠️ **peut ne rien trouver** — il lui faudra la forme « rien à montrer » |
| `interroger_travail` | `couples`, `bearings`, `resisting_elsewhere` | ⚠️ **idem** : posé avant qu'un texte soit résolu, il n'a rien à dire |
| `demander_production` | thème ✅ / livrable ❌ verrouillé | le verrou porte son motif (trou 3) |
| `changer_de_sujet` | propose une nouvelle préparation | une proposition, jamais un acte |
| `hors_champ` | `repondre_hors_champ` | ✅ écrit, avec son ancre |
| `indechiffrable` | `repondre_indechiffrable` | ✅ écrit, avec son ancre |

**Les deux qui ne préparent rien sont déjà les mieux protégés** : ils nomment ce qu'Urim est,
tendent une passerelle et situent la préparation. Ce sont les deux qui **risquent le moins** le
mur, parce qu'ils ont été écrits en sachant qu'ils n'avaient rien à donner.

Les deux à surveiller sont `interroger_texte` et `interroger_travail` : ils *croient* avoir
quelque chose à rendre, et rendent parfois le vide. C'est exactement la situation de `bear_axes`
avant réparation.

---

## 6. Ce que la marche a trouvé en plus

**Le déversoir — et ce qu'il enterrait.** `weigh_conviction` servait **toutes** les unités de
l'axe retenu, sans plafond. Le banc l'a d'abord compté comme le jumeau du mur — *trop pour
choisir vaut rien à choisir* — puis la mesure a montré que le problème était ailleurs, et bien
plus grave. `sites_by_axis` est trié **par force**, donc les textes qui résistent arrivent en
queue :

| axe | unités servies | dont résistantes | **rang du 1ᵉʳ résistant** |
| :-- | --: | --: | --: |
| anthropologie | 4 302 | 5 | **4 298ᵉ** |
| hamartiologie | 2 916 | 532 | 2 385ᵉ |
| sotériologie | 2 386 | 657 | 1 730ᵉ |
| eschatologie | 1 820 | 628 | 1 193ᵉ |
| christologie | 817 | 6 | 812ᵉ |
| pneumatologie | 285 | 5 | 281ᵉ |

Le contrat dit *« elles sont affichées au même rang, exprès »* — et l'ordre disait exactement le
contraire. **La seule protection anti-proof-texting du mode conviction était enterrée sous
quatre mille textes**, et elle l'était d'autant plus que l'axe était large.

**Réparé — quota égal par groupe, étalé sur le canon.** Chaque groupe (`dominant`, `porte`,
`resiste`) reçoit **le même** nombre de places : c'est ce qui rend « au même rang » mécanique au
lieu de déclaratif — un groupe pléthorique ne peut plus prendre celle d'un groupe rare. La
sélection reprend la mécanique de `_resistent_ailleurs` : un livre ne parle qu'une fois, puis
des positions régulièrement espacées, **déterministe** donc rejouable. Et le compte réel voyage
dans le motif, règle de la concordance : *on écourte, on ne dissimule pas*.

    anthropologie   4 302 -> 17 options, et les 5 resistants sont tous la
    soteriologie    2 386 -> 18 options, dont « 6 sur 657 » qui resistent
    theologie_propre 3 971 -> 12 options

⚠️ Le plafond ne ferme aucune porte : `expects: choice` **autorise** le texte libre — *les
pastilles sont des raccourcis, jamais des barreaux* — et `POST /decisions` accepte toujours
n'importe quelle unité du corpus par son identifiant. Effet de bord non négligeable : la réponse
de cet écran passait près du mégaoctet, sur un téléphone à Abidjan.

**Le plafond a révélé ce qui manquait à la sélection : la pertinence.** L'étalement canonique ne
connaît que la diversité, et le dossier que le modèle avait proposé pour la saisie disparaissait
dès qu'un axe était choisi. Sur *« on prie pour les malades et rien ne change »*, il trouvait
**2 Corinthiens 12:7-10** — l'écharde non retirée, trois prières sans réponse, présentée comme
une grâce : le garde-fou même de cette intention, que le dépôt cite lui-même. Le texte *porte*
l'axe sans en être le sujet, donc il concourait avec plus de mille autres pour six places
tirées au compas : **une chance sur mille sept cents**.

Mesuré avant d'être branché : les passages proposés tombent presque toujours dans des unités
curées qui portent les axes suggérés — l'intersection n'est pas rare, elle est quasi totale.

**Réparé — la moitié des places au dossier, l'autre au canon.** Dans chaque groupe, les unités
que le modèle a désignées passent en tête et prennent **trois places sur six** ; l'étalement
garde les trois autres. Deux gardes rendent ce biais acceptable :

- **le quota par groupe** — quoi que le modèle corrobore, il ne peut affamer aucune force. Les
  résistants ont leurs six places, et il arrive qu'il en remonte un (« Le contrôle des
  constellations » résiste à l'anthropologie) ;
- **une proposition vague ne corrobore rien** — `Job 38:1-42` recouvre sept unités, on ne sait
  pas laquelle il visait. C'est la règle de l'exploration : *quand plusieurs unités couvrent la
  demande, la curation ne s'attache à aucune.*

    « on prie pour les malades »   AVEC : L'experience mystique de Paul (2 Co 12:7-10)
                                          Conseils pour la priere et la guerison (Jc 5)
                                  SANS : La force militaire des Rubenites
                                          L'annonce de la mort de Saul et de Jonathan

Et le motif le dit — *« Celles que votre formulation désignait sont en tête »* : un ordre qui
cesse d'être neutre doit s'annoncer, sinon le pasteur croit lire le canon là où il lit une
pertinence supposée.

**Un étage entier était injoignable, et avec lui la protection de S26/S37.** Trouvé en marchant
un sermon protestant — *« le baptême du Saint-Esprit, une obligation »*. `shape_homiletic.applies()`
exige `subject_matter is None`, et la décision écrivait `plan_source` **et** `subject_matter`
d'un coup : l'étage ne se ré-exécutait donc plus jamais, et toute sa seconde moitié était morte.

    _releve()               la charge ne relevait aucun risque, jamais
    le REFUSE du couple     un couple non faisable etait accepte
    _motif_du_risque()      « Releve d'un cran » n'atteignait aucun pasteur

La preuve visible : le couple **`abracadabra:sur-mesure`**, qui n'existe dans aucune curation,
traversait tout et ressortait dans le thème — *« pneumatologie, en abracadabra sur-mesure »*.
Trois tests étaient verts sur cette moitié morte : ils appellent `execute()` sur un état que
`applies()` rejette. **Le test était vrai, l'état inatteignable** — la version fine du piège de
la vacuité que ce dépôt connaît déjà.

**Réparé** : la bordure valide le couple contre la curation et refuse avec **le motif du texte**
(*« ce passage ne porte aucun personnage nommé »*), et le risque relevé se lit désormais sur les
options de l'écran de mise en forme — à l'endroit exact où l'écran des axes avait promis qu'il
apparaîtrait. Les deux branches de l'étage restent en place comme garde interne, avec un
commentaire qui dit qu'elles ne sont pas la protection du pasteur.

**Un texte à un seul axe dominant verrouille l'axe — sans le dire.** Trouvé en marchant un
sermon orthodoxe sur la théosis. Le pasteur ouvre `2 Pierre 1:4` *pour* la déification ;
l'unité relue a **un seul** dominant, `christologie`, donc `bear_axes` continue sans poser de
question et l'axe est posé d'office. Tout l'aval suit : le thème, la faisabilité, et les textes
qui résistent — qui résistent alors à la **christologie**, pas à sa thèse.

L'unité porte pourtant `anthropologie`, `soteriologie`, `theologie_propre` et `eschatologie` en
`porte`. L'étage le dit lui-même quand il y a plusieurs dominants — *« les ordonner serait
décider ce que le pasteur veut prêcher »* — et avec un seul, il décide. La correction existait
dans l'API (`POST /decisions` sur `bear_axes`) et **aucun écran ne l'offrait**. Traité en §7 —
où l'on a découvert que la porte de sortie était en plus cassée.

⚠️ **Et cette décision n'est pas vérifiée** : `bear_axes` accepte n'importe quelle chaîne comme
axe doctrinal, exactement comme `shape_homiletic` acceptait n'importe quel couple. C'est la même
famille de trou, au même endroit du code — la bordure qui applique une décision sans demander au
corpus si elle existe.

**La glose, mesurée avant d'être jugée — et le soupçon était à moitié faux.** Sur la saisie
protestante, le modèle avait rebaptisé *pneumatologie* en **« L'effusion obligatoire »**, puis
**« L'effusion nécessaire »** au passage suivant. J'en avais conclu que la glose *ratifiait la
thèse*. Huit saisies, trois appels chacune, zéro échec de transport :

| | |
| :-- | :-- |
| titres **qui tranchent** | 3 sur 17 — et **tous** sur des saisies qui portaient déjà leur thèse |
| titres instables d'un appel à l'autre | 5 sur 17, variantes synonymes (« déification » / « divinisation ») |
| saisies neutres | titres neutres : « La prière sans réponse », « L'Église sans amour », « Le poids du péché » |

**Le modèle fait écho, il n'invente pas.** L'invite le lui demande explicitement — *« dans la
langue du pasteur et non celle de l'école »* — et elle porte déjà une garde, mais une seule :
*« le titre nomme un ANGLE DE PRÉDICATION, jamais l'état de celui qui écrit »*. Elle interdit de
**diagnostiquer le pasteur**. Elle ne dit rien de **reprendre sa thèse**, et c'est là que la
mesure a déplacé le problème.

Le vrai défaut n'est pas la formulation : `AxisGloss` a décidé que cet écran parle la langue du
pasteur, et c'est juste. Le défaut est que **sept libellés viennent du corpus et trois du
modèle, et que rien ne les distinguait** — `origin` valait `locus` pour les dix. Le pasteur lit
*« voici les dix axes de la dogmatique »*, et l'un d'eux s'appelle « L'effusion obligatoire ».

**Réparé** — `Option.signature`, remontée jusqu'à `ChipItem`. C'est §5.4 appliqué là où il
manquait (*pour que rien de généré ne se confonde avec une relecture*), avec le mot de
`reviewed_by` pour que le client n'ait qu'un vocabulaire :

    [locus] Théologie propre — Dieu
    [locus] L'effusion obligatoire        <- ia-mistral
    [locus] La grâce indispensable        <- ia-mistral
    [locus] Ecclésiologie — l'Église

⚠️ `origin` et `signature` répondent à deux questions et les confondre dirait faux : l'axe vient
de la dogmatique dans les dix cas, seul son **habit** est généré.

**La relecture est un écran que personne n'avait cartographié.** `GET /studies/{id}` rejoue les
huit étages sur un état déjà décidé : les étages qui rendaient la main ne s'appliquent plus, et
c'est `load_context` qui reste en queue de trace. C'est l'écran qu'un pasteur voit chaque fois
qu'il rouvre son travail du samedi, et il ne ressemble à aucun des six tours de la maquette.

**Le corpus a rattrapé sa documentation.** `propose_theme` porte encore la phrase *« sur un
passage non curé — soit 99,77 % de l'Écriture aujourd'hui — le pipeline s'arrête à la pesée
doctrinale »*. Ce n'est plus vrai : 4 561 unités couvrent les 66 livres, toutes pesées. Le
chemin qui menait au mur n°2 est passé du cas ordinaire au cas d'un bouton.

**Une mauvaise référence était remplacée par le modèle, en silence.** `« Hébreux 2:29 »` — une
note réelle du Pasteur X, dans un chapitre qui compte 18 versets — n'atteignait le refus de
`resolve_passage` que **sans modèle branché**. Avec la clé, la bordure posait `Hébreux 2:9`
comme résolu et l'écran sautait au bornage : le pasteur demandait le verset 29, recevait le
verset 9, et perdait le fait — *la seule chose qu'Urim savait dire depuis le premier jour et
n'avait jamais pu dire*, puisque ses notes portaient deux références inexistantes.

Ce n'était pas systématique : `Philippiens 28:9` et `1 Corinthiens 5:99` restaient refusés. Le
modèle ne parlait **que** quand une correction plausible existait — c'est-à-dire exactement quand
le pasteur avait fait une faute qu'il voudrait connaître. Et sur `Zorobabel 3:5`, la vue rendait
`outcome: refuse` **avec** `resolved: Esdras 3:5` : un enregistrement qui pointait vers un texte
que personne n'avait nommé.

La règle existait pourtant, à quinze lignes de là, appliquée à **l'autre** appel de modèle —
`_est_une_impasse_de_recherche` exclut le chemin référence *parce qu'un fait sur l'orthographe ne
se noie pas sous des passages thématiques*. Elle ne couvrait pas la résolution assistée, qui
ne noyait pas le fait : elle l'écrasait.

**Réparé — la trouvaille devient une option, le fait reste le motif.** Quand le moteur a établi
un fait (`_a_etabli_un_fait`), la bordure pose la référence dans `suggested_reference` au lieu de
`resolved`, et `resolve_passage` rend la main :

    WHY      Aucun passage ne correspond. Ecarte : Hebreux 2 compte 18 versets — il n'y a
             pas de verset 29. Vouliez-vous dire Hebreux 2:9 ?
    SAY      J'ai cherche la reference la plus proche de ce que vous avez ecrit.
    ASK      Est-ce celle-la ?
    OPTION   [correction] Hebreux 2:9

C'est le patron du chemin citation — *le refus devient une proposition* — et la règle de l'étage
0 : **le calcul propose, la personne dispose**. Le pasteur touche, et c'est *lui* qui résout.

⚠️ `correction` est une **provenance à elle seule** : « trouvé dans vos mots », « traite votre
sujet » et « je crois que vous vouliez écrire ceci » ne se valent pas, et seule la troisième
parle de ce que le pasteur a *tapé*.

⚠️ **Limite assumée** : sur un livre inconnu (`Zorobabel`), le refus vient de l'étage 0, dont le
vocabulaire d'options est celui des **modes d'entrée** — y glisser une référence se ferait
refuser au clic. La trouvaille n'y est donc pas offerte ; elle n'est plus appliquée non plus, et
l'incohérence a disparu.

---

## 7. L'axe unique — la porte invisible, et la cascade qu'elle cachait

> Posée le 2026-08-14 en marchant un sermon orthodoxe, **résolue le même jour** — et la
> résolution a coûté plus que la question, parce que la porte de sortie n'était pas seulement
> invisible : elle était cassée.

### Le fait

`bear_axes` ne rend la main que devant **plusieurs** dominants, ou devant aucun. Un texte à un
seul axe dominant voit donc son axe posé d'office, et tout l'aval en découle — le thème, la
faisabilité, et surtout les textes qui **résistent**, qui résistent alors à l'axe du corpus et
non à la thèse du pasteur.

Le cas mesuré : `2 Pierre 1:4`, ouvert *pour* la déification. L'unité relue porte

    christologie   dominant        <- l'axe pose d'office
    theologie_propre, anthropologie, hamartiologie, soteriologie, eschatologie   porte
    pneumatologie, ecclesiologie, angelologie, demonologie                       absent

Le pasteur repart avec un thème christologique et des objections christologiques (Ézéchiel 44,
Psaumes 118) — justes, et hors de son sujet.

### Pourquoi c'est une vraie question et pas un bug

L'étage énonce lui-même la règle contraire, quand plusieurs axes dominent : *« Les ordonner
serait décider ce que le pasteur veut prêcher. »* Avec un seul, il décide — et il a de bonnes
raisons : **le cas ordinaire est celui où le pasteur est d'accord**, et lui imposer un tour de
plus à chaque préparation pour un désaccord rare est exactement le genre de zèle que le bornage
s'interdit (*« on ne fatigue pas quelqu'un qui a visé juste »*).

Les deux corrections possibles ont donc chacune leur coût :

| | ce qu'on gagne | ce qu'on paie |
| :-- | :-- | :-- |
| **offrir les `porte` en second rang** | un geste possible, aucun tour imposé | le tour porte deux familles d'options qui ne valent pas la même chose |
| **rendre la main dès qu'il y a un choix** | fidèle à la doctrine de l'étage | un tour de plus sur presque toutes les préparations |

### Ce que la marche a trouvé : la porte n'était pas seulement invisible

Avant d'offrir un geste, il fallait vérifier ce qu'il faisait. `POST /decisions` sur `bear_axes`
reposait bien l'axe — et laissait le thème de l'ancien. Les quatre révisions possibles, mesurées
une par une :

| le pasteur change… | ce qui restait périmé |
| :-- | :-- |
| **l'axe** | le thème nommait encore `christologie` |
| **le couple** | le thème nommait encore la mise en forme abandonnée |
| **ses bornes** | l'axe, le couple **et** le thème survivaient à l'unité devenue illisible |
| **le texte** | l'unité, l'axe, le couple et le thème, tous inchangés |

**Aucune décision amont ne remontait l'aval.** La cause est une phrase du service qui n'était
vraie que de la trace :

> *« Le rejeu est le choix structurant : on stocke les décisions, et on refait tourner les huit
> étages. »*

Les bornes, l'axe, le couple et le thème ne sont pas des décisions : ce sont des **résultats**,
stockés comme tels, et chaque étage qui les produit se garde de tourner deux fois (`applies`).
Le rejeu ne rejouait donc que ce que personne n'avait encore décidé. C'est la racine commune des
deux bugs déjà réparés — `shape_homiletic` injoignable, `propose_theme` qui ne recalcule jamais.

Le cas des bornes forcées est le plus grave : S22 promet que la liberté accordée *« se propage
d'elle-même, sans qu'aucun étage n'ait à connaître la règle »*. Elle ne se propageait pas du
tout — le pasteur gardait un thème et une faisabilité tirés d'une unité que le produit venait de
déclarer illisible.

### La résolution — en deux temps, et le premier n'était pas la question posée

**1. La cascade** (`UrimStudyService._perimer`). Une décision périme ce que les étages avals
avaient calculé, et le pipeline le recalcule. Trois portées, nommées par ce qu'elles emportent
plutôt que par l'étage qui les déclenche :

    tout l'aval      un mode d'entree, un autre texte  -> unite, bornes, axe, couple, theme
    sous le texte    un texte choisi sur une intention -> unite, bornes, couple, theme
                     (l'AXE reste : sur le chemin inverse, le pasteur l'a nomme en premier)
    sous les bornes  une autre unite, ou « mes bornes » -> couple, theme  (S22 se propage enfin)

⚠️ **Un thème réécrit par le pasteur ne se périme jamais.** *Une proposition, jamais un titre —
le titre, c'est votre voix.* On ne distingue pas sa phrase de celle du moteur par une colonne :
le gabarit est déterministe, donc l'égalité suffit à dire que personne n'y a touché. Même ruse
que `_une_unite_existait`, qui repose la question au corpus plutôt que d'ajouter un champ qui
pourrait le contredire.

Effet de bord heureux : la branche que `propose_theme` déclarait inatteignable — *« Hors unité
curée — le thème ne s'appuie sur aucune faisabilité relue »* — atteint enfin un pasteur.

**2. Le choix, rendu visible là où il était déjà affiché.** Le bloc `bearings` accompagne tous
les tours avals et porte les dix axes avec leur force. Il marque désormais l'axe **retenu**
(`selected`) et ceux qu'on peut prendre à la place (`selectable`), et il dit **où poster**
(`decide_stage: "bear_axes"`) — sans quoi un client enverrait la décision à l'étage qui vient de
parler, et se ferait refuser.

`absent` n'est jamais prenable — *un axe absent n'affiche rien, et aucun plan ne se construit
dessus* — ni `resiste` : c'est un garde-fou, pas un angle. Même partage que `bear_axes`, qui
offre les dominants, sinon les portants, et jamais les résistants.

**Aucun tour n'a été ajouté à personne.** Les 42,2 % de préparations qui n'avaient pas d'écran
de choix n'en ont toujours pas : elles ont une phrase qui nomme le geste, et des pesées qui le
portent. On n'a pas construit une fonctionnalité — on a rendu visible celle qui existait, après
l'avoir réparée.

⚠️ **Ce que la phrase ne dit pas, et pourquoi.** Le geste n'est nommé que sur le tour où les
pesées sont le sujet. Au tour du thème — le plus probable pour s'apercevoir que l'angle n'est
pas le sien — l'affordance est portée par le bloc seul. L'ajouter à cette question-là était
tentant et faux : le thème s'affiche aussi hors unité curée, où il n'y a **aucune** pesée à
l'écran, et la phrase promettrait alors un geste sans rien pour le faire. C'est exactement le
mur n°2, dans l'autre sens. Un client qui rend `selectable` n'a pas ce problème ; une phrase
qui l'ignore, si.

### Vérifié de bout en bout, sur le cas qui a posé la question

    2 Pierre 1:4  ->  axe pose d'office : christologie
                      theme « christologie, en expositif doctrinal »
                      a prendre : theologie_propre, anthropologie, hamartiologie,
                                  soteriologie, eschatologie
    il prend anthropologie (la deification)
                  ->  theme « anthropologie, en expositif doctrinal »
                      et les textes qui resistent CHANGENT : Job 38:31-33,
                      Romains 11:33-36 — l'insondabilite des jugements de Dieu

La protection suit désormais l'angle que le pasteur prêche, et non celui que le corpus a jugé
dominant. C'était toute la question.

### La mesure, prise sur les 4 561 unités

Elle était nécessaire avant de trancher, et elle déplace la question. Une passe sur
`index.bearings`, sans modèle :

| dominants sur l'unité | unités | ce que le pasteur vit |
| :-- | --: | :-- |
| **0** | 1 948 · 42,7 % | l'étage rend la main sur les axes `porte` — **il choisit déjà** |
| **1** | 1 926 · 42,2 % | l'axe est posé d'office — **on décide pour lui** |
| 2 | 605 · 13,3 % | il choisit |
| 3 et plus | 82 · 1,8 % | il choisit |

Et parmi les 1 926 unités à dominant unique, **98,9 % portent au moins un autre axe** (trois en
médiane) : il y a donc presque toujours quelque chose à lui offrir. Seules **22 unités** (1,1 %)
n'ont rien d'autre — et là, le comportement d'origine était exactement juste.

Ce que la mesure change : l'argument du *« tour de plus imposé à tout le monde »* pesait tant
qu'on croyait le cas rare. **Le pasteur passe déjà par un écran de choix d'axe sur 57,8 % des
textes.** Sur les 42,2 % restants, l'écran n'est pas ajouté à un fil qui n'en avait pas — il est
retiré à un fil qui en a un une fois sur deux. L'asymétrie n'est plus la même, et la
non-uniformité devient elle-même un défaut : le même geste existe ou non selon le texte, sans
que rien à l'écran ne l'explique.

C'est ce qui a écarté la troisième voie — *rendre la main dès qu'il y a un choix*. Elle est la
plus fidèle à la doctrine de l'étage, et elle imposerait un tour à 1 926 préparations pour un
désaccord qui, lui, n'est pas mesuré. Le geste offert sans tour supplémentaire donne la même
liberté et ne coûte rien à celui qui était d'accord.

---

## 8. Marcher l'arbre soi-même

```bash
python scripts/urim_banc_arbre.py
```

30 cas — les saisies réelles du Pasteur X, les trois confessions, et les chemins que personne
ne prévoit (micro resté ouvert, livre inconnu, saisie vide, acquiescement seul). Le banc ouvre,
répète le geste du pasteur jusqu'au bout, puis **rouvre** la préparation.

```bash
python scripts/urim_banc_arbre.py --tout
```

⚠️ **Relire compte plus que le verdict.** `--tout` redéballe chaque prise entière — `say`,
`why`, `ask`, `expects`, blocs. Un instrument qu'on ne peut pas relire fait arbitrer sur sa
parole : neuf « formes interdites » signalées un matin, huit étaient les meilleures lignes du
corpus.

**Deux configurations, et la plus sévère est la seconde.** Avec `MISTRAL_API_KEY`, le banc
mesure la production. Sans clé, les suggestions disparaissent, le moteur n'a plus que le corpus,
et deux cellules de refus s'ouvrent qui restaient fermées. Les deux passent à **0 mur**.

Le même détecteur — `mur()` — est importé par `tests/contexts/urim/test_arbre_conversationnel.py`,
qui tient la propriété sur les 36 cellules sans base ni réseau. Deux implémentations du mot
« mur » auraient dérivé, et le jour où elles se contrediraient, c'est le banc qu'on croirait.

Chaque garde y est doublée d'un **témoin fautif** : les deux tours réellement rendus avant la
réparation. C'est le détecteur qui est testé, pas le vide.
