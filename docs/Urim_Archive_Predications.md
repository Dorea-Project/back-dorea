# Urim — l'archive du prédicateur, sa fusion avec le Retour, et le rangement par loci

> **Nature :** note de conception. **Aucun code.** Écrite le **2026-08-13**, contre le dépôt à
> cette date.
> **Née d'un trou signalé** : le livrable ([`Urim_Livrable.md`](Urim_Livrable.md)) s'arrête à la
> porte de la chaire, et **rien n'attend le pasteur de l'autre côté**.
> Couvre le **chantier 8** (`UrimEngine_Specs_Implementation.md` §8 — « Archive + dictée ») et sa
> jonction avec `urim/capture` (`Dorea_Urim_Architecture_Transcription.md`).

---

## 1. Le constat — et il est plus grave que « ce n'est pas fait »

`urim_preached` **existe, est lue par le moteur, et n'est écrite par personne.**

| Fait | Où |
| :-- | :-- |
| L'étage 7 lit l'historique de l'auteur et sait dire *« Vous avez déjà prêché cet axe récemment »* | `app/contexts/urim/engine/stages/propose_theme.py:83` |
| Le service va le chercher en base à **chaque rejeu** | `app/contexts/urim/application/study_service.py:953` |
| **Aucun code n'écrit jamais une ligne de `urim_preached`** | vérifié sur tout `app/` — le seul écrivain serait la route `POST /urim/preached` de la spec §4, **qui n'existe pas** |

> **Cette phrase n'a donc jamais été affichée à personne, et ne le sera jamais** — la table est
> vide depuis toujours et le restera tant que rien ne l'écrit.

C'est **exactement la pathologie déjà nommée** sur `urim_usage_window` (*« cette table est lue et
n'a jamais été écrite »*, `models.py:384`). Deux fois le même mode de panne : une lecture qui
fonctionne parfaitement contre un vide, donc un test vert, donc un défaut invisible. La différence,
ici, c'est que **la fonctionnalité entière en dépend** — l'archive n'est pas un compteur, c'est le
seul endroit où le travail d'un pasteur s'accumule.

**Et le module de capture n'est pas plus avancé** : `app/contexts/urim/capture/` ne contient que le
**quatrième mur** (`FORBIDDEN_IN_MODEL_PROMPT`) et son domaine — la règle est en place *avant* le
module qu'elle garde, ce qui est la bonne façon de faire, mais le module n'existe pas. Ses quatre
tables, elles, **sont désormais définies** (`UrimCaptureModel`, `UrimTranscriptSegmentModel`,
`UrimCitedVerseModel`, `UrimReflectionModel`) : **S31 est levé au niveau du schéma**, et c'était le
blocage annoncé.

---

## 2. Trois objets, et celui qui manque est au milieu

```
préparer                prêcher                    revoir                  ranger
urim_preparation   →    urim_capture           →   urim_reflection    →    urim_preached
(ce que j'ai prévu)     (ce que j'ai dit)          (l'écart, mesuré)       (ce que j'ai prêché)
   ✅ livré               ⛔ pas construit           ⛔ pas construit         ⛔ jamais écrite
```

**L'archive n'est ni la préparation, ni le transcript.** C'est un **fait** : *ce jour-là, j'ai
prêché ce passage, sous cet axe.* Une préparation abandonnée n'y entre pas ; un transcript de
quarante minutes n'y entre pas non plus — il est la matière, pas le fait.

Ce qui était déjà tranché et ne bouge pas (D-B, S32) : l'archive est clée sur **`author_id`**, elle
**suit le pasteur s'il change d'église**, et `exportable_until NULL` la fait **survivre à la
résiliation** — *son travail lui appartient*.

⚠️ **Une fourche à ne pas ignorer** : [`Plan_Urim_Producteur.md`](Plan_Urim_Producteur.md)
(05/08/2026) révoque D-B/S32 et retire le contexte `sermon`, Urim devenant producteur de ce que le
fidèle lit. **Ce retrait n'a pas été exécuté** — `app/contexts/sermon/` est intact. Cette note ne
tranche pas cette fourche : l'archive du prédicateur est **la même dans les deux mondes** (elle est
à lui, pas à l'église). Seule la *publication* dépend de la fourche, et ce n'est pas le sujet ici.

---

## 3. Quand une préparation devient une prédication — **un geste, jamais une déduction**

Trois façons de remplir l'archive, et le schéma les prévoit déjà (`capture_kind`) :

| Origine | Ce qui la déclenche |
| :-- | :-- |
| `saisie` | **le pasteur dit « j'ai prêché ceci »** — depuis la préparation, ou à vide |
| `dictee` | une capture du culte a eu lieu (§4) |
| `import` | un sermon d'avant Dorea, sans préparation (`preparation_id` nullable) |

> **Tranché : rien ne s'archive parce qu'une date est passée.**

La tentation est forte — `service_date` est en base, le dimanche est connu, l'archive se
remplirait toute seule. **C'est faux, et le dépôt en a déjà la preuve.** Le Pasteur X a préparé
autour de six passages proposés et **a prêché le Psaume 125**, qui n'était dans aucun des six
(feuille de route, §2 bis). Une archive remplie par le calendrier aurait enregistré un sermon qui
n'a jamais eu lieu, sous un axe qu'il n'a pas prêché — **et la couverture du canon aurait menti dès
la première semaine.**

Un préparateur change d'avis, tombe malade, cède la chaire. **L'archive enregistre un fait ; seul
celui qui était en chaire sait qu'il a eu lieu.**

---

## 4. La fusion avec le Retour — ce que le transcript peut, et ce qu'il ne peut pas

C'est le cœur de la question, et il se décide en deux règles.

### 4.1 Le transcript ne réécrit jamais l'archive — il **propose**, et le pasteur signe

Le Retour (`urim_reflection`) calcule quatre compteurs **par différence déterministe, jamais par le
modèle** : versets prévus, cités, convoqués sans être prévus, prévus et jamais cités. Il peut donc
voir ce qu'aucun homme ne voit de lui-même : *vous aviez annoncé Romains 8:1-11, vous avez passé
les trois quarts du temps sur 8:12-17.*

**Ce constat ne corrige pas l'archive tout seul.** Il en fait la **proposition**, et l'archive ne
bouge que signée — exactement le patron que `urim_reflection` porte déjà en base :
`synthesis_state IN ('proposee','validee','rejetee')` avec la contrainte `synthese_validee_signee`
(*« une synthèse `validee` sans `validated_by` serait une parole attribuée à quelqu'un que personne
n'a signée »*).

> **La règle, en une ligne :** *le transcript sait ce qui a été dit ; il ne sait pas ce qui a été
> prêché.* Un texte longuement cité peut être une digression, et un texte lu une fois peut être le
> sermon entier.

⚠️ **Et le quatrième mur tient ici sans exception** (S29) : la fusion se calcule **par différence
sur des faits** — versets cités, horodatages, ancres. Le modèle ne voit jamais la préparation, donc
jamais l'archive. Le jour où quelqu'un voudra « demander au modèle sous quel axe ranger ce
sermon », c'est ce mur qu'il franchira.

### 4.2 **Prêché ≠ cité** — la confusion qui gonflerait le canon

Un sermon convoque une chaîne : huit textes chez le Pasteur X, douze dans la seconde prédication.
Si l'archive comptait chaque verset cité comme un passage prêché, **une prédication vaudrait douze
lignes de couverture** — et l'écran « couverture du canon », qui existe pour montrer où un pasteur
ne va jamais, dirait le contraire de la vérité.

| Couche | Ce que c'est | Combien par sermon |
| :-- | :-- | :-- |
| **Prêché** | le passage sur lequel il a prêché — la clé de l'archive | **un** |
| **Touché** | les textes convoqués en appui (`urim_cited_verse`, `urim_preparation_support`) | plusieurs, souvent douze |

**Les deux s'affichent, jamais additionnés.** *« Vous avez prêché 9 fois dans les Psaumes ; vous en
avez cité 41 fois »* dit quelque chose de vrai et d'utile. Un seul nombre mentirait.

### 4.3 Un sermon sans préparation — le passage se **propose** avec son motif

`preparation_id` est nullable, et c'est fait pour : on peut prêcher sans avoir préparé. Le
transcript rend alors des versets cités et rien d'autre. Le moteur peut proposer *« le passage
paraît être Actes 1:1-14 — c'est celui qui revient le plus, et le plus tôt »*, **avec son motif**,
et le pasteur confirme ou corrige.

Ce qu'il ne fait à aucun prix, c'est ranger tout seul. C'est la règle du dépôt entier — *le calcul
propose, la personne dispose* — et c'est la même que celle du détecteur d'entrée (S33) : *il ne
route pas, il propose une route.*

---

## 5. Le rangement par loci — **montrer, jamais prescrire**

Les deux index existent déjà et portent les deux vues : `(author_id, book_id, start_ch)` = la
couverture du canon ; `(author_id, axis_code, preached_on)` = la distribution doctrinale.

### 5.1 La clé de rangement est **l'axe qu'il a retenu**, et elle ne bouge plus

Un texte porte **dix** pesées (`dominant`, `porte`, `resiste`, `absent`). Ranger un sermon sous les
dix ne rangerait rien ; ranger sous le dominant calculé reviendrait à classer le travail d'un
homme d'après une curation qu'aucun humain n'a relue — **tout est signé `ia-mistral` aujourd'hui**.

> **Tranché : on range sous l'axe que le pasteur a retenu** (`preparation.axis_code`, son choix),
> **et cette clé est figée à l'archivage.**

Les axes **portés** restent lisibles à l'écran, mais **recalculés à la lecture** depuis l'unité —
jamais recopiés dans l'archive. Une pesée corrigée demain doit corriger la lecture ; une copie
figée deviendrait une seconde vérité qui diverge en silence.

⚠️ **La tension est réelle et il faut la nommer** : la lecture dérivée peut donc **changer** sous
un sermon déjà prêché. C'est le même problème que `judged_fingerprint` et `corpus_snapshot`
résolvent ailleurs — la réponse est identique : **on le dit** (« la curation de ce passage a changé
depuis »), on ne fige pas et on ne cache pas.

### 5.2 « Rangé sous » n'est pas « a prêché » — la distinction de S38, appliquée

Un pasteur peut avoir prêché le Saint-Esprit dans un texte dont le dominant retenu est la
christologie. La colonne dira alors *zéro* en pneumatologie.

> Un rayon vide ne dit pas *« il n'a jamais prêché cela »*.
> Il dit *« aucun sermon n'est rangé là »*.

C'est mot pour mot la règle S38 (*une ligne absente ne dit pas que le texte se tait — elle dit que
personne n'a regardé*), et l'écran doit la porter dans ses **libellés**, pas dans une note de bas
de page.

**Et le rayon « non rangé » est visible, obligatoirement.** Hors des unités curées — 99,77 % de
l'Écriture aujourd'hui — il n'y a aucun axe à retenir : `axis_code` est nul. Ces sermons doivent
apparaître dans une colonne nommée, jamais disparaître du graphique. Une distribution doctrinale
qui cache ce qu'elle n'a pas su ranger est un graphique qui ment par omission.

### 5.3 La ligne que le rangement ne franchit pas

L'étage 7 la porte déjà, en commentaire, et elle vaut pour tout l'écran d'archive :

> *« L'archive informe, elle n'interdit rien : prêcher deux fois le même axe est un choix légitime,
> et le pasteur est le seul à savoir pourquoi. »*

**Interdit, donc :** proposer un sermon pour combler un trou (*« vous n'avez pas prêché
l'eschatologie depuis 14 mois, voici un texte »*), noter la couverture, afficher un score, une
série, un badge, un pourcentage de complétude doctrinale.

Deux raisons, et la seconde est une règle du dépôt :

1. **C'est l'inversion du principe.** *Le signal informe l'homme. L'homme commande la machine.*
   Un moteur qui déduit d'un tableau ce qu'il faut prêcher dimanche décide de la chaire.
2. **C'est un compteur d'engagement**, et Dorea les refuse : le test est la boucle — production
   rafraîchissable dont le destinataire est l'auteur lui-même. Un score de couverture doctrinale
   la ferme parfaitement, et transformerait une aide à la fidélité en performance à tenir.

**Ce qui est permis, et suffit** : montrer le fait. Un pasteur qui voit *« pneumatologie : aucun
sermon rangé depuis dix-huit mois »* comprend seul — c'est la même économie que S10 (*« nommer les
deux axes suffit : un homme qui voit s'afficher lamentation comprend seul »*).

---

## 5 bis. ✅ **Livré le 2026-08-13** — l'archive par saisie

Le §7 disait « ce qui n'attend rien » ; c'est fait. **14 tests**, migration `e3f4a5b6c7d8`
appliquée et aller-retour `downgrade`/`upgrade` vérifié, `alembic check` propre, 1 458 tests
verts.

| Pièce | Où |
| :-- | :-- |
| Migration | `church_id` nullable (**A1**) · `pericope_id` ajoutée (**A2**) |
| Service | `app/contexts/urim/application/archive_service.py` — le geste, la saisie libre, les deux lectures |
| Dépôt | `.../persistence/archive_repository.py` (**A3**) |
| Routes | `POST /studies/{id}/preached` · `POST /preached` · `GET /preached` · `GET /preached/couverture` |
| Garde | `application/access.py` — **extraite**, plus recopiée (décision Q1 du livrable) |

**Trois choses que l'écriture a apprises, et qui ne sont pas dans la conception ci-dessus :**

1. **La garde d'accès était une méthode privée du service d'étude.** L'archive en avait besoin
   mot pour mot. La recopier aurait créé une seconde définition de « mes préparations » —
   elle vit désormais dans `access.py`, et les deux services l'appellent.
2. **`COUNT(DISTINCT (a,b,c,d))` n'est pas portable.** Postgres compte un tuple distinct,
   **SQLite refuse** plus d'un argument dans un agrégat `DISTINCT` — et la base de test se
   construit depuis les modèles, en SQLite. La rédaction évidente n'aurait donc cassé **qu'en
   production**. Corrigé par un regroupement sur les bornes, replié en Python ; et le seul
   test de ce fichier qui touche une base existe pour tenir cette propriété-là.
3. **Une préparation sans passage résolu s'archive quand même** (quatre bornes nulles). Le
   fait *« j'ai prêché ce dimanche »* reste vrai même si le moteur n'a pas su dire sur quoi ;
   refuser l'archive ferait perdre la date pour sauver une colonne.

**Ce qui reste ouvert dans cette note** : la fusion avec le Retour (§4), qui attend la capture
et son verrou ; et **A5** (signature de la correction venue du transcript), qui n'a pas d'objet
tant que le Retour n'existe pas.

---

## 6. Ce que le schéma ne permet pas encore

| # | Delta | Motif |
| :-- | :-- | :-- |
| **A1** | ✅ **fait** — `preached.church_id` était `NOT NULL` | **L'antichambre est cassée à l'archivage.** `preparation.church_id` est devenue nullable le 11/08 (« Urim s'installe seul, le pasteur sans église est le cas normal ») ; `preached` n'a pas suivi. **Un pasteur sans église peut préparer et ne peut pas archiver** — et c'est le cas d'usage d'entrée du produit |
| **A2** | ✅ **fait** — `pericope_id` (colonne nue) sur `preached` | L'archive porte les bornes, pas l'unité. Or c'est l'unité qui porte les pesées : sans elle, la lecture dérivée du §5.1 doit **re-résoudre** un passage à chaque affichage, et une re-résolution qui change ferait bouger un rangement passé sans que rien ne le dise |
| **A3** | ✅ **fait** — routes d'archivage + repository | Le seul écrivain manquant (§1). La spec l'annonce depuis le premier jour |
| **A4** | ✅ **fait** — `axis_code` nullable, et le rayon « non rangé » est rendu par l'API | §5.2 : « non rangé » est un état normal à 99,77 % de corpus non curé, pas une donnée manquante |
| **A5** | La correction de l'archive par le Retour : `validated_by` / `validated_at` sur la ligne d'archive corrigée | §4.1 — l'archive ne bouge que signée. `urim_reflection` porte déjà la contrainte, l'archive ne l'a pas |

**Et les tests qui tiennent les propriétés** (chacun avec son couple accepté/refusé) :

- **le passage du calendrier n'archive rien** — seule une action explicite le fait (§3) ;
- **un verset cité n'entre jamais dans la couverture du canon** ; le passage prêché, oui (§4.2) ;
- **aucun chemin ne passe l'archive ni la préparation au modèle** — c'est le quatrième mur, dont le
  test balaiera enfin un module qui existe ;
- **un pasteur sans église peut archiver** (A1) ;
- **un sermon sans axe apparaît dans la distribution**, dans son rayon nommé (§5.2).

---

## 7. L'ordre — ce qui peut avancer, et ce qui attend

**Ce qui n'attend rien.** L'archive par **saisie** (§3) ne dépend ni de la capture, ni de
l'audio, ni du modèle : une route, un repository, deux écrans de lecture. Elle **débloque une
phrase déjà écrite dans le moteur** (« vous avez déjà prêché cet axe récemment »), qui n'a jamais
atteint personne. C'est le meilleur rapport valeur/risque de tout le chantier Urim aujourd'hui.

**Ce qui attend, et le verrou n'est pas négociable.** La fusion avec le transcript (§4) dépend de
`urim/capture`, lui-même soumis à son **verrou interne** : *étape 1 seule — capture, transport,
transcript brut non exploité — jusqu'à mesure du taux d'erreur dans trois églises réelles.*

> *« Une synthèse bâtie sur une transcription non mesurée est une invention présentée comme un
> souvenir. »*

**L'ordre est donc : l'archive d'abord, le Retour ensuite.** Et il a une propriété utile — une
archive remplie à la main pendant quelques mois donne, le jour où la capture arrivera, **de quoi
mesurer ce que la transcription propose** contre ce qu'un homme a déclaré. On ne peut pas mesurer
un écart contre rien.

---

## 8. Questions ouvertes — **toutes tranchées le 2026-08-13**

| # | Question | Décision |
| :-- | :-- | :-- |
| **A-Q1** | ~~Un même sermon prêché deux fois : deux lignes, ou une à deux dates ?~~ | ✅ **Deux lignes** — deux prédications sont deux faits datés, dans deux assemblées ; les fondre perdrait que le second dimanche a eu lieu. **Et la couverture du canon compte des passages DISTINCTS**, pas des lignes : le pasteur lit « Psaume 125, prêché 2 fois » sans que son canon paraisse deux fois plus large. *Même règle que §4.2 : ne pas écrire dans la table ce qui est une lecture* |
| **A-Q2** | ~~Qui archive quand la chaire est cédée à un invité ?~~ | ✅ **Rien dans l'archive de l'hôte.** La clé `author_id` répond seule : l'archive mesure *sa* prédication, et y ranger un sermon qu'il n'a pas prêché fausserait précisément ce qu'elle existe pour montrer. Reste ouvert **ailleurs** : l'église a-t-elle besoin de son propre registre ? Cela dépend de la fourche `sermon` (§2), pas de cette note |
| **A-Q3** | ~~Un axe secondaire déclaré par le pasteur ?~~ | ✅ **Non — un seul axe retenu.** Les axes portés se **recalculent** depuis l'unité (§5.1) : les redemander serait un formulaire qui répète ce que le corpus sait déjà, et que personne ne remplirait. Ranger, c'est choisir un rayon ; un objet dans trois rayons n'est rangé nulle part |
| **A-Q4** | ~~Garde-t-on la correction refusée ?~~ | ✅ **Oui, conservée** — *jamais de résolution silencieuse*, comme les options écartées et les candidats non retenus. Et un refus dit ici quelque chose de rare : *le transcript croit que j'ai prêché autre chose, et je maintiens*. C'est la donnée qui dira un jour si la détection dérive |
| **A-Q5** | ~~Combien de temps garde-t-on le transcript ?~~ | ✅ **Règle minimale posée maintenant, durée fixée plus tard** : **toute donnée de capture porte une échéance dès son écriture**, comme l'audio. Motif : *ne pas décider une durée, c'est décider « pour toujours »* — une colonne datée qu'on rallonge est un choix, une absence de colonne est un oubli qu'on découvre le jour d'une demande d'effacement. La durée demande un juriste (loi 2013-450) et des églises réelles |
| **A-Q6** | ~~L'archive alimente-t-elle la publication au fidèle ?~~ | ✅ **Non, et la règle qui tient est déjà écrite** : *Urim ne publie jamais rien au membre* — ni son plan, ni son transcript, ni son archive. Si la fourche `sermon` (§2) est un jour tranchée dans l'autre sens, c'est un **port de publication** qui sera ajouté, jamais une lecture directe de l'archive |

> **Construction ouverte le 2026-08-13 sur demande explicite de l'auteur**, comme le socle du
> chantier 0 le 03/08. Le §11 d'`Architecture v2` n'est pas devenu vrai — le dimanche réel n'a pas
> eu lieu. C'est un choix assumé, pas une condition remplie.

---

*Note de conception. Le §11 d'`Architecture v2` reste au-dessus d'elle : Urim n'est pas autorisé à
la construction, et le dimanche réel n'a toujours pas eu lieu. Ce qui est écrit ici l'est pour que
le trou soit connu — une table lue et jamais écrite est le genre de défaut qui se découvre en
démonstration.*
