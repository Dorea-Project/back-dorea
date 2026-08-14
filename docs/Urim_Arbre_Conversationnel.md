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
| `resolve_passage` · `AWAIT` | les livres possibles, ou les textes à égalité + « ce n'est pas une citation » | `« 1 Roi ou 2 Roi… »`, une citation de mémoire |
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
décider ce que le pasteur veut prêcher »* — et avec un seul, il décide. La correction existe
dans l'API (`POST /decisions` sur `bear_axes`) et **aucun écran ne l'offre**.

⚠️ **Et cette décision n'est pas vérifiée** : `bear_axes` accepte n'importe quelle chaîne comme
axe doctrinal, exactement comme `shape_homiletic` acceptait n'importe quel couple. C'est la même
famille de trou, au même endroit du code — la bordure qui applique une décision sans demander au
corpus si elle existe.

**La glose peut adopter la thèse du pasteur.** Sur cette même saisie, le modèle a rebaptisé
*pneumatologie* en **« L'effusion obligatoire »**, puis **« L'effusion nécessaire »** au passage
suivant. `code` reste le locus, donc rien n'est faussé en aval — mais l'écran renvoie au pasteur
sa conviction promue au rang d'axe doctrinal. À regarder : la glose est censée parler sa langue,
pas ratifier sa thèse.

**La relecture est un écran que personne n'avait cartographié.** `GET /studies/{id}` rejoue les
huit étages sur un état déjà décidé : les étages qui rendaient la main ne s'appliquent plus, et
c'est `load_context` qui reste en queue de trace. C'est l'écran qu'un pasteur voit chaque fois
qu'il rouvre son travail du samedi, et il ne ressemble à aucun des six tours de la maquette.

**Le corpus a rattrapé sa documentation.** `propose_theme` porte encore la phrase *« sur un
passage non curé — soit 99,77 % de l'Écriture aujourd'hui — le pipeline s'arrête à la pesée
doctrinale »*. Ce n'est plus vrai : 4 561 unités couvrent les 66 livres, toutes pesées. Le
chemin qui menait au mur n°2 est passé du cas ordinaire au cas d'un bouton.

**Une mauvaise référence peut être remplacée par le modèle, en silence.** `« Hébreux 2:29 »` —
une note réelle du Pasteur X, dans un chapitre qui compte 18 versets — n'atteint le refus de
`resolve_passage` que **sans modèle branché**. Avec la clé, la bordure résout autre chose et la
préparation part sur un texte que le pasteur n'a pas nommé. La provenance est bien marquée
`ia`, et le comportement est documenté ; il mérite d'être regardé de nouveau, parce que le refus
qu'il remplace était précisément l'information utile.

---

## 7. Question ouverte — l'axe unique décide à la place du pasteur

> **Note de conception, non implémentée.** Posée le 2026-08-14 en marchant un sermon orthodoxe.
> Le trou de validation qui l'accompagnait est fermé ; la question, elle, reste entière.

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

### Ce qui existe déjà, et qui n'est offert nulle part

La correction est **possible aujourd'hui** : `POST /studies/{id}/decisions` avec
`stage_code: bear_axes` et un des dix loci repose l'axe, et le pipeline repart derrière. Aucun
écran ne la propose, et le contrat du tour n'a pas de bloc pour elle. C'est donc une porte
ouverte que personne ne voit — ce qui est la pire des trois situations, parce qu'elle a l'air
d'une absence de fonctionnalité alors que c'est une absence d'affichage.

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
médiane) : il y aurait donc presque toujours quelque chose à lui offrir. Seules **22 unités**
(1,1 %) n'ont rien d'autre — et là, le comportement actuel est exactement juste.

Ce que la mesure change : l'argument du *« tour de plus imposé à tout le monde »* pesait tant
qu'on croyait le cas rare. **Le pasteur passe déjà par un écran de choix d'axe sur 57,8 % des
textes.** Sur les 42,2 % restants, l'écran n'est pas ajouté à un fil qui n'en avait pas — il est
retiré à un fil qui en a un une fois sur deux. L'asymétrie n'est plus la même, et la
non-uniformité devient elle-même un défaut : le même geste existe ou non selon le texte, sans
que rien à l'écran ne l'explique.

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
