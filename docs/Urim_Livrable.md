# Urim — le livrable de prédication (`.docx` et `.pptx`)

> **Nature :** note de conception. **Aucun code.** Elle dit le pourquoi, tranche ce qui doit
> l'être, et s'arrête à la ligne où il faudrait écrire.
> **Écrite le 2026-08-13**, contre le dépôt à cette date. Complète le chantier 2 de
> [`UrimEngine_Specs_Implementation.md`](UrimEngine_Specs_Implementation.md) (§8) et le §3.6 de
> [`Dorea_Urim_Structure_et_Schema.md`](Dorea_Urim_Structure_et_Schema.md).
> **Sœur de** la note de transcription (S-6 / `urim/capture`) : les deux se rejoignent au §10.

---

## 1. La règle centrale, et pourquoi elle décide de tout le reste

> **Le livrable ne se génère jamais sans validation et modification par le pasteur — sinon il n'a
> aucun effet.**

Ce n'est pas une précaution d'interface. C'est la raison d'être du produit, et elle se déduit de
tout ce qu'Urim a déjà refusé : dix loci fermés plutôt qu'un thème en prose, aucun verset qui sorte
du modèle, la signature `ia-mistral` remontée jusqu'à l'écran (`curation_reviewed_by`), les mises en
garde sur ce que le texte **ne dit pas**. Un fichier qu'on télécharge et qu'on lit en chaire tel
quel annulerait ces quatre décisions d'un seul geste — et ce serait le geste le plus facile de
toute l'application.

### 1.1 Le danger n'est pas le fichier, c'est le canal

Le modèle n'a **aucune sortie en prose** : `axes` rend des codes de locus, `passages` rend des
références que le corpus vérifie. Cette contrainte tient parce qu'il n'existe nulle part un endroit
où du texte libre puisse s'écouler vers le pasteur.

Un générateur de document est exactement cet endroit. Il suffit qu'une case du gabarit s'appelle
« introduction proposée » pour que quelqu'un, dans six mois, la remplisse — d'abord par
concaténation de motifs, ensuite par un appel de modèle « pour que ce soit lisible ». **Le livrable
doit donc être conçu comme un verrou, pas comme une fonctionnalité d'export.**

### 1.2 La règle rendue structurelle — trois verrous, aucune déclaration

| # | Verrou | Ce qu'il rend impossible |
| :-- | :-- | :-- |
| **V1** | **La colonne vertébrale du document est le squelette Braga** (`urim_preparation_element`) — dix éléments **tous facultatifs**, *que le moteur ne remplit jamais* | Un document qui aurait un plan sans que personne l'ait écrit. Sans éléments, il n'y a pas de sermon à imprimer : **la page est vide par arithmétique, pas par règle** |
| **V2** | **Le texte biblique projeté est soumis par le pasteur, jugé par le serveur avant qu'un seul octet de fichier existe** (`urim_citation_check`) | Un verset altéré à l'écran — et, accessoirement, un fichier produit puis contrôlé « pour la forme » |
| **V3** | **Ce que le modèle a produit ne monte jamais à l'écran de l'assemblée** (§3) | Que la curation `ia-mistral` acquière l'autorité de la chaire en passant par une diapositive |

**V1 est le cœur.** Le squelette Braga porte déjà, en base et en commentaire, la phrase qui décide :
*« un plan qui arrive complet n'est pas un plan que quelqu'un a préparé »*
(`app/contexts/urim/infrastructure/persistence/models.py:124`). Le livrable ne fait
que **prendre acte** de cette décision : il imprime le plan du pasteur, entouré de la matière que le
moteur a rassemblée. Il ne fabrique pas de plan.

### 1.3 « Et s'il ne modifie rien ? » — la question, telle qu'elle est posée, est un piège

C'est le point le plus important de cette note, et il change la mécanique demandée.

Pour vérifier qu'un pasteur **a modifié** quelque chose, il faut lui avoir donné quelque chose à
modifier : un brouillon. Autrement dit, **il faudrait d'abord écrire le sermon à sa place pour
pouvoir constater qu'il l'a corrigé.** Le contrôle qui devait protéger de la machine à sermons
l'exige. Et le contournement est trivial — une espace en fin de ligne suffit à passer n'importe
quel `diff`.

> **Tranché : le livrable ne compare rien à rien. Il n'y a pas de brouillon.**
> Le critère n'est pas *« a-t-il modifié ? »* mais **« y a-t-il quelque chose de lui ? »**.

C'est la même règle, obtenue autrement — et elle est incontournable au lieu d'être déclarative.
Trois conditions cumulatives, vérifiées avant de produire quoi que ce soit :

1. **Le squelette porte le point central** — un seul élément, et c'est celui-là (§1.3 bis) ;
2. **chaque diapositive a été composée par lui** : le texte projeté vient de sa saisie, jamais d'un
   remplissage automatique ;
3. **le contrôle de citation rend `conforme`** sur toutes les diapositives (§4).

**Si l'une manque : refus motivé, jamais un fichier dégradé.** C'est le vocabulaire du moteur —
`REFUSE` avec son motif (S2), parce qu'un refus qui n'oriente pas est une porte fermée :

> *« Il n'y a pas encore de plan à imprimer. Le document met en page ce que vous avez écrit ;
> le moteur ne l'écrit pas à votre place. »*

**Générer en signalant a été écarté.** Un document marqué « non validé » est un document qui existe :
il se transfère par WhatsApp, s'imprime, se lit en chaire — et le bandeau est en page 1, que
personne ne regarde le dimanche matin. Un fichier qui n'a jamais été produit ne se lit pas.

### 1.3 bis Le seuil — ✅ **tranché le 2026-08-13 : le point central seul suffit**

> **Un élément, et un seul : la `proposition`** — le sermon en une phrase, dans le vocabulaire de
> Braga (`Architecture v2` §197 : titre, introduction, **proposition**, phrase interrogative, phrase
> de transition, divisions principales, subdivisions, illustrations, application, conclusion).

**Pourquoi un seul, et pourquoi celui-là.** Le seuil ne mesure pas l'avancement d'un travail — il
répond à une question binaire : *y a-t-il un homme derrière ce document ?* Un seul élément y
répond, à condition que ce soit celui qu'aucune machine ne peut fournir. Le titre est une étiquette,
les divisions se déduisent d'un plan, les illustrations viennent d'ailleurs ; **la proposition est
l'endroit où le pasteur dit ce qu'il va dire**. Chez Braga, elle gouverne les divisions — c'est la
pièce qui tient les autres, pas une case de plus.

Et un seuil plus haut se retournerait contre la règle : exiger trois ou cinq éléments, c'est
prescrire une méthode de préparation. Urim propose un ordre, **il n'impose aucun contenu**
(`study_service.set_elements`) ; un pasteur qui écrit sa proposition puis prêche de mémoire a
préparé, et le lui refuser serait juger son travail au lieu de constater sa présence.

⚠️ **On ne regarde jamais le contenu.** Le test est *non vide après normalisation* — aucune
longueur minimale, aucune appréciation de qualité, aucun modèle consulté. Une machine qui jugerait
la valeur du point central d'un prédicateur serait la machine à sermons sous un autre nom, et cette
fois avec une note.

**Et le motif de refus doit nommer la parade**, sinon le seuil devient un mur :

> *« Il manque le point central : la phrase qui dit ce que vous allez prêcher. Une ligne suffit —
> c'est la seule chose que le document ne peut pas écrire à votre place. »*

**La conséquence, et elle demande du code** : `urim_preparation_element.element_code` est un
**texte entièrement libre** — aucune contrainte en base, aucune validation dans
`set_elements`. Adosser un verrou à un code précis exige donc d'abord de **fermer la liste des dix**
(§9.4), sinon la garde se contourne par une faute de frappe, et — plus grave — un pasteur qui a
réellement écrit sa proposition se voit refuser son document parce que son client a envoyé
`Proposition` au lieu de `proposition`.

### 1.4 Ce qui est verrouillé, ce qui lui appartient

| Dans le document | Qui en répond | Modifiable par le pasteur |
| :-- | :-- | :-- |
| Le **texte biblique** servi (péricope, appuis) | le corpus — servi verbatim par le serveur | ⛔ jamais dans le document ; il change de **bornes** ou de **version**, pas de mots |
| Les **références** imprimées | `check_reference` / `citation_check` | ⛔ elles sont contrôlées ; une saisie illisible s'imprime **avec son motif**, jamais en silence |
| Les **pesées, mises en garde, faisabilités, motifs, variantes** | la curation, avec sa **signature** | ⛔ pas dans le document (la reprise se fait par `PATCH /pericopes/{id}`, à sa place) |
| Le **texte projeté** sur une diapositive | lui — jugé `exact` / `extrait` / `altere` | ✅ il coupe, il abrège ; il n'invente pas |
| **Le plan, le thème, les titres, les transitions, les illustrations** | **lui, entièrement** | ✅ c'est tout le document utile |

> Les illustrations — *Yamoussoukro, le mont Nimba* — ne sont pas du ressort d'Urim et ne doivent
> jamais l'être (feuille de route, §2 bis). Le livrable ne leur ouvre aucune case : il imprime ce
> qu'il a, et laisse la page respirer là où c'est au pasteur de parler.

---

## 2. L'état réel du dépôt — mesuré, pas supposé

| Ce que la spec suppose | Ce que le dépôt dit (2026-08-13) |
| :-- | :-- |
| Le livrable est le **chantier 2** (« ne dépend que du corpus ») | **Rien n'est écrit.** `UrimDeliverableModel` et `UrimCitationCheckModel` sont déclarées et **référencées par aucun code** — ni service, ni repository, ni test |
| Le verrou « pas de fichier non contrôlé » | ⛔ **Non levé, et c'est écrit à l'endroit exact** : `app/contexts/urim/interface/mobile_router.py:13` — *« Le livrable n'est pas exposé […] une route qui rendrait un fichier non contrôlé irait contre la règle »*. **Aucune ligne de contrôle de citation n'existe.** Cette note est ce qui permet de le lever ; le contrôle est un **prérequis du premier octet**, pas une suite |
| `kind IN ('pptx','pdf')` | ⚠️ **`docx` est interdit par la contrainte `CHECK`** — et la colonne mélange le *document* et son *encodage*, ce que le PDF gardé (§3.2) rend intenable. Migration nécessaire (§9) |
| Le serveur sait lancer un programme externe | ❌ **Aucun `subprocess` dans tout `app/`**, et l'image Docker (`python:3.13-slim`) n'installe aucun paquet système. La conversion PDF serait le premier des deux (§3.2) |
| `citation_check` clée sur `(deliverable_id, slide_no)` | Convient au `.pptx`. Le `.docx` n'a pas de diapositive — voir §4.3, il n'en produit aucune ligne **et c'est cohérent** |
| Le serveur sait rendre un fichier | ❌ **Aucune route du dépôt ne rend autre chose que du JSON** (aucun `StreamingResponse`, aucun `media_type`). Le livrable serait la première |
| La matière est « déjà en base » | ✅ **presque entièrement** — voir le tableau ci-dessous |

### 2.1 La matière disponible, et les deux trous

Tout ce que le document doit contenir est déjà servi par `StudyView`
(`app/contexts/urim/interface/schemas.py:181`) : `verses`, `bearings`, `caveats`,
`context`, `couples` (avec `refusal_reason` et `proof_text_risk`), `variants`, `supports` (avec
leur verdict), `resisting_elsewhere`, `pericope_label`, `curation_reviewed_by`, `trace`, `options`
(écartées comprises), `corpus_snapshot`.

**Deux exceptions, à connaître avant d'annoncer un sommaire :**

- **Les mots de l'original ne sont pas dans `StudyView`.** Ils vivent dans `PassageDetailView`
  (`original`), alimentés depuis `index.originals`. Le livrable devra les lire de la même source —
  ce n'est pas un manque, c'est un aiguillage à ne pas rater. Sur un livre dont la langue d'origine
  n'est pas chargée, la section est **vide** : elle doit alors le **dire** (« l'hébreu n'est pas
  encore chargé »), sinon un document muet se lit comme « ce passage n'a rien à montrer ».
- **Les mises en garde et le contexte peuvent être vides** sur la quasi-totalité des unités. La
  section *« ce que le texte ne dit pas »* sera alors absente. Même règle : **une section vide se
  nomme**, elle ne disparaît pas — sans quoi le silence de la curation ressemble au silence du
  texte, et c'est exactement la confusion que S38 a coûté une règle à séparer.

> ⚠️ **Ne pas planifier le sommaire sur des chiffres de seconde main.** La feuille de route mesurait
> au **10/08/2026** : une seule version (LSG), hébreu non semé, 11 caveats, 9 notes de contexte. Des
> commits **postérieurs** la contredisent — *« L'hébreu semé »*, *« Darby et Martin »*,
> *« Ostervald »*, *« Les mises en garde et le banc de la porte »* — et le document de route n'a pas
> été remesuré depuis. **Les compter en base avant d'écrire la première section**, parce que ces
> volumes décident de ce qui s'imprime : ils ne changent aucune règle de cette note, seulement le
> contenu réel des pages.

> **Et la ligne qu'aucun document ne doit franchir** : tout est signé `ia-mistral` aujourd'hui
> (4 553 péricopes, 37 500 pesées, aucune relecture humaine). Le `.docx` **imprime la signature**,
> à côté de la matière qu'elle couvre. C'est la contrepartie de V3.

---

## 2 ter. La structure réelle d'une prédication — **mesurée sur trois, pas supposée**

> Trois notes de prédication fournies le 2026-08-13 : `docs/temoins/Predication_Signes_Des_Temps.txt`
> (1 Ch 12:32), `Predication_Saint_Esprit.txt` (Jn 7:37-39), `Predication_Ascension.txt` (Ac 1:1-14).
> Elles ne confirment pas la conception : **elles en corrigent deux morceaux**.

### 2 ter.1 Le squelette observé

| Section | Signes | Saint-Esprit | Ascension |
| :-- | :--: | :--: | :--: |
| **Thème** — souvent « Aujourd'hui nous allons parler de… » | ✅ | ✅ | ✅ |
| **Objectif** — l'intention déclarée | — | ✅ | — |
| **Passage** + son texte recopié en entier | ✅ | ✅ | référence seule |
| **Introduction** = contexte du livre (datation, auteur, visée) puis contexte culturel | ✅ | ✅ | ✅ |
| **NB** — l'application immédiate, posée *avant* le plan | ✅ | — | — |
| **Définitions** des termes du thème | ✅ | — | — |
| **Phrase de transition** annonçant la division (« … en trois points ») | — | ✅ | — |
| **Divisions numérotées**, avec sous-points `a-` `b-` | 3 | 3 | 4 |
| Chaque division : une affirmation · **un ou plusieurs textes** · un commentaire · une application | ✅ | ✅ | ✅ |
| **Illustrations** de la vie courante (la CAN, les télénovelas) | ✅ | — | — |
| **Témoignage personnel** (« Mon Témoignage ») | ✅ | — | — |
| **Conclusion** | — | ✅ | ✅ |

**Ce que ça confirme** : le sermon convoque une **chaîne** (huit à douze textes), l'introduction
est massivement **contextuelle** (datation, destinataires, visée du livre — exactement la matière
de `context_note`), et le pasteur cherche le **sens des mots** (« signe », « prière », « soif »)
— ce que la concordance sert déjà.

### 2 ter.2 ⚠️ Le verrou du §1.3 refusait les trois

**Aucune des trois ne contient de `proposition`.** Le seuil s'y adossait ; il aurait donc refusé
son document aux trois pasteurs pour qui il est écrit. C'est le défaut de la chaîne de textes,
répété : *une garantie qui ne lit pas la notation de celui qu'elle protège ne protège personne.*

**Et le thème ne peut pas le remplacer** : `propose_theme` le remplit d'office, par gabarit fermé.
*Un verrou que le moteur satisfait lui-même n'est pas un verrou.*

> ✅ **Corrigé — le seuil est une division.** Un point du plan, écrit par lui. Les trois témoins
> en portent trois, trois et quatre ; le moteur n'en écrit jamais aucun.

Le seuil lui-même est inchangé (Q7 : *un seul élément suffit*) — seul l'élément qui le porte a
changé, parce que la donnée réelle a désigné le bon.

### 2 ter.3 ⚠️ Le contrôle de citation accusait un pasteur qui faisait l'inverse

Le témoin du 06/06 cite Jean 7:37-39 dans une version **amplifiée** :

> *« Jésus, se tenant debout, s'écria **[à haute voix]** : … Celui qui croit **[qui adhère,
> compte, et se confie]** en moi »*

Chaque insertion casse la contiguïté : verdict `altere`, fichier bloqué, et un pasteur qui
s'entend dire qu'il a falsifié l'Écriture **alors que le crochet dit lui-même ce qu'il ajoute**.

> ✅ **Corrigé — le contenu entre crochets est retiré de la comparaison, jamais du document.**
> À l'écran les crochets restent visibles : l'assemblée voit, elle aussi, où finit le texte et
> où commence l'explication. Et ce qui est **hors** crochets reste jugé mot pour mot — sinon il
> suffirait d'en poser autour d'un mot changé.

### 2 ter.4 ✅ **Q9 — tranché le 2026-08-13 : on juge contre toutes les versions détenues**

La règle des crochets sauve ce témoin-là. Elle ne réglait pas le cas général : **un pasteur cite
la Bible qu'il a**. Jugé contre une seule version, un texte parfaitement fidèle à une autre rend
`altere` — c'est-à-dire une **accusation**, là où la vérité est *« je ne détiens pas votre
Bible »*. C'est S19 appliqué au livrable : *on dit ce qui manque au corpus, jamais ce qui manque
au pasteur.*

**Et le cas d'école du dépôt tombe exactement dessus.** Le Texte Reçu ajoute à Romains 8:1
*« qui ne marchent point selon la chair, mais selon l'esprit »* — **Ostervald le porte, la LSG
l'omet** (S17). Un pasteur qui projette l'Ostervald — la version que les assemblées lisent —
s'entendait donc accuser de falsifier un verset qu'il citait mot pour mot.

**La règle** :

| Situation | Issue |
| :-- | :-- |
| une version détenue reconnaît le texte | ✅ son nom est **porté par le verdict** |
| `exact` sur l'une, `extrait` sur une autre | ✅ **`exact` gagne**, quel que soit l'ordre — mieux vaut nommer la version qui porte le texte entier |
| aucune ne le reconnaît | ⛔ `altere`, et le motif **nomme les versions consultées** et rend le texte servi |

> **La version reconnue n'est pas une information cosmétique.** Sur Romains 8:1, reconnaître
> Ostervald plutôt que la LSG **change la doctrine du verset projeté** : sans la clause,
> « aucune condamnation » est inconditionnel ; avec elle, c'est une condition morale. Deux
> sermons opposés sur la même référence — et c'est cette valeur que `citation_check.version_id`
> attendait depuis qu'elle a été déclarée.

**Les deux autres issues sont écartées, et il vaut la peine de dire pourquoi** : un quatrième
verdict *invérifiable* deviendrait la porte de sortie de quiconque veut projeter n'importe quoi ;
et exiger que la diapositive **déclare** sa version ferait porter au pasteur le travail que le
corpus peut faire seul. Si un texte fidèle à une version non détenue passe encore en `altere`, ce
sera un **manque de corpus** à combler — pas une règle à assouplir.

> **Deux documents, trois formats.** Le `.pdf` est gardé (Q3, tranché) — mais c'est un **encodage**
> de l'un des deux, jamais un troisième contenu. Voir §3.2, où la décision coûte plus qu'un
> `CHECK`.

Le `.pptx` **n'est pas le `.docx` découpé**. Ce sont deux objets qui ne s'adressent pas à la même
personne, et une seule question les sépare :

> **À qui cette phrase est-elle utile ?**
> Une mise en garde s'adresse au **prédicateur**. Une assemblée à qui l'on projette « ce texte ne
> dit pas ceci » reçoit un cours d'exégèse à la place d'une prédication — et un doute qu'elle n'a
> pas les moyens d'instruire.

| Matière | `.pptx` — l'assemblée | `.docx` — sa note |
| :-- | :--: | :--: |
| Thème, titres, points du plan, transitions *(ses mots)* | ✅ | ✅ |
| Texte biblique projeté *(soumis par lui, contrôlé)* | ✅ | — |
| Texte biblique servi verbatim par le corpus | — | ✅ |
| Références des textes d'appui | ✅ | ✅ *(avec le verdict, même illisible)* |
| Bornes de l'unité littéraire **+ le motif du découpage** | référence seule | ✅ intégral |
| Pesées doctrinales (`dominant` / `porte` / `resiste` / `absent`) + motifs | ⛔ | ✅ **les dix, `absent` compris** |
| Mises en garde — *ce que le texte ne dit pas* | ⛔ **jamais** | ✅ |
| Textes qui résistent, venus d'ailleurs | ⛔ | ✅ **au même rang que les portants** |
| Faisabilité homilétique (plan × matière), refus motivés, `proof_text_risk` | ⛔ | ✅ |
| Mots grecs/hébreux, morphologie décodée | ⛔ | ✅ |
| Variantes textuelles (`textual_variant`) | ⛔ *(sauf s'il en fait une de ses phrases)* | ✅ |
| Options **écartées** avec leur motif de refus | ⛔ | ✅ |
| Signature de curation, `corpus_snapshot`, date | ⛔ | ✅ **pied de page** |

**Les trois règles qui rendent ce tableau vérifiable** — et qui sont testables une par une :

1. **Rien de ce qui n'a pas été relu par un humain ne monte à l'écran.** Aujourd'hui, cela revient
   à : sur une diapositive, il n'y a que **le texte biblique** (corpus, contrôlé) et **ses mots à
   lui**. C'est une règle de provenance, pas de goût — et elle survivra à la relecture humaine, où
   elle s'assouplira d'elle-même.
2. **Aucun motif du moteur ne devient une phrase de diapositive.** Un `rationale` est écrit pour
   être contesté par un pasteur, pas lu par trois cents personnes.
3. **Le `.docx` porte une mention de destination** — *note de préparation, non destinée à la
   diffusion* (`Q5`). C'est le pendant écrit de la frontière : ce document contient des doutes
   nommés, et un doute qui circule sans son prédicateur devient une rumeur doctrinale.

### 3.1 Deux détails de forme qui se voient depuis le fond de la salle

- **Le format 16:9 se pose explicitement.** `python-pptx` ouvre en 4:3 par défaut ; un cadre noir
  de chaque côté est la première chose que l'assemblée voit du travail de la semaine.
- **Le grec exige une police qui le porte** (et l'hébreu, quand il viendra, exige en plus la
  direction droite-à-gauche — `OriginalWordView.language` existe pour ça). Un mot rendu en carrés
  vaut moins que pas de mot du tout : sur substitution impossible, la section ne s'imprime pas.

### 3.2 Le PDF — ✅ **gardé (Q3, tranché le 2026-08-13)**, et ce que ça engage

Le motif est juste et il est du terrain : **le PDF est le format qui circule réellement** — il
s'ouvre sur n'importe quel téléphone, ne se déforme pas d'un appareil à l'autre, et se projette
depuis un écran quand il n'y a pas d'ordinateur. Le refuser aurait été refuser la manière dont ces
documents voyagent vraiment.

Il engage trois choses, et aucune n'est le `CHECK` de la migration.

**(a) La colonne `kind` ne peut plus dire ce qu'elle disait.** `('pptx','pdf')` mélangeait déjà deux
questions ; avec trois formats et deux documents, la confusion devient une perte d'information :
`kind = 'pdf'` **ne dit pas si c'est le deck ou la note qui est sorti** — c'est-à-dire précisément
la frontière du §3, et précisément ce que la trace (§7) existe pour savoir.

> **Tranché : deux colonnes.** `kind IN ('deck','note')` — *quel document* — et
> `format IN ('pptx','docx','pdf')` — *sous quel encodage*. Plus un `CHECK` qui interdit les deux
> couples impossibles : un deck n'est jamais `docx`, une note n'est jamais `pptx`.
>
> Le coût est nul : la table n'a **jamais été écrite**, il n'y a aucune ligne à reprendre.

**(b) Le PDF est une conversion, jamais une seconde mise en page.** La tentation sera d'écrire un
troisième rendu (`reportlab`, `fpdf2`, `weasyprint`). **À refuser** : deux moteurs de mise en page
pour le même document dérivent, et ils dérivent en silence. Le jour où le rendu PDF oublie une mise
en garde que le `.docx` porte encore, personne ne le voit — et c'est la note du pasteur qui devient
fausse, pas une diapositive.

> **Le PDF est produit en convertissant le fichier déjà validé** (`.pptx` ou `.docx`), par
> **LibreOffice en mode sans interface** (`soffice --convert-to pdf`, MPL-2.0, invoqué comme
> **processus**, jamais lié au code). Aucune ligne de mise en page à écrire, et la propriété qui
> compte est acquise par construction : **le PDF ne peut pas dire autre chose que le fichier dont
> il sort.**

⚠️ **Ce que ça coûte, dit franchement** — c'est la décision la plus chère de cette note :

| Coût | Mesure |
| :-- | :-- |
| **L'image Docker** | `python:3.13-slim` n'installe **aucun paquet système** aujourd'hui. LibreOffice ajoute plusieurs centaines de Mo — l'image change d'ordre de grandeur |
| **Le premier processus externe du backend** | ⚠️ **Aucun `subprocess` n'existe dans `app/`.** La conversion doit donc apporter ce que le dépôt n'a jamais eu à écrire : **délai maximum**, **répertoire temporaire isolé et nettoyé**, **une conversion à la fois** (elle est gourmande, et une file d'attente non bornée est une panne mémoire un dimanche matin) |
| **La latence** | quelques secondes. Acceptable sur un geste explicite (« je veux le PDF »), inacceptable si c'était le format par défaut — **il ne l'est pas** |

**(c) Deux règles qui ne se négocient pas** :

1. **On ne convertit que ce qui est déjà `conforme`.** Le PDF **hérite** de la validation, il ne
   l'accorde jamais. Un chemin qui produirait un PDF sans passer par §4 serait la porte dérobée que
   toute cette note existe pour fermer.
2. **Un échec de conversion ne bloque rien.** Le `.docx` ou le `.pptx` reste servi, avec son motif —
   *aucun mur un vendredi soir*, la règle du moteur s'applique ici telle quelle.

**Et la conséquence qui rend Q5 urgente.** Le PDF fait exactement ce qu'on lui demande : il
circule. Une **note** en PDF emporte donc avec elle les mises en garde doctrinales nommées, les
motifs de refus et la signature `ia-mistral` — hors de la main de celui qui pouvait les instruire.
Ce n'est pas une raison de la refuser (le pasteur a le droit d'emporter sa note sur son téléphone),
c'en est une pour que la mention de destination soit **dans la page, pas dans un réglage**.

> **L'option écartée, et pourquoi** : laisser le client Flutter fabriquer le PDF. C'est gratuit
> côté serveur — et c'est une **troisième** mise en page, dans un autre langage, hors de portée des
> tests du §9, et sans aucune trace. Le fichier qui circulerait ne serait alors plus celui que le
> serveur a validé, seulement un document qui lui ressemble.

---

## 4. Le contrôle de citation — le verrou, et l'ordre dans lequel il se ferme

### 4.1 Le contrôle est **en amont du fichier**, jamais un contrôle qualité après coup

```
il compose ses diapositives (référence + texte projeté)
        ↓
POST … /deliverable        ← le serveur juge CHAQUE diapositive contre le corpus
        ↓                     verdict ∈ exact | extrait | altere
   ┌────┴─────┐
 altere      tout passe
   ↓            ↓
validation    validation = 'conforme'  →  le fichier peut être produit
 = 'rejete'                                (et pas avant : aucun octet n'existe encore)
 aucun fichier
```

**Pourquoi cet ordre, et pas « générer puis vérifier » :** un fichier produit est un fichier
qui circule. Le contrôle d'après coup protège la base de données, pas l'assemblée.

**La règle du verdict est déjà écrite et ne bouge pas** (S4/S5) : sous-chaîne contiguë du corpus
après normalisation, « … » autorisant plusieurs fragments contigus dans l'ordre et sans
chevauchement ; comparaison sur la référence **traduite via `versification_map`**, jamais sur la
référence brute. La troncature est légitime — c'est l'altération qui est fatale. Un booléen ferait
mourir le garde-fou de son excès de zèle.

### 4.2 Un rejet n'est pas une erreur HTTP

Même raison que pour les issues du moteur (`app/contexts/urim/interface/mobile_router.py:7`) :
une citation altérée est **ce que le produit veut montrer**, pas un échec de requête. Réponse
`200`, `validation: "rejete"`, et par diapositive : la référence, ce qu'il a écrit, ce que le
corpus porte. Un `422` ferait disparaître le seul écran où un verset abîmé se voit avant le
dimanche.

### 4.3 Pourquoi le `.docx` n'a aucune ligne de contrôle — et n'en a pas besoin

> **Le `.docx` n'accepte aucun texte biblique saisi.** Il n'imprime que ce que le corpus sert, à
> partir de références déjà contrôlées.

Il n'y a donc rien à falsifier : l'objet du contrôle (du texte tapé qui prétend être un verset)
n'existe pas dans ce format. Le pasteur qui veut citer *à sa façon* le fait sur une diapositive,
où c'est jugé. `citation_check` reste clée sur `slide_no` sans que ce soit un compromis : elle
décrit ce qui est **projeté**.

⚠️ **Conséquence à assumer** : `validation` d'un `.docx` ne peut pas être gagnée par le contrôle de
citation. Elle l'est par les **conditions de §1.3** — c'est le seul endroit où la règle centrale
tient toute seule, et c'est pourquoi §1.3 est écrit avant tout le reste.

---

## 5. Où ça vit

**Contexte `urim`, module `deliverable/`** — l'architecture le prévoit déjà nommément
(`Dorea_Urim_Architecture_v2.md` : *« deliverable/ — diapositives, import, export, validation de
sortie »*). Trois couches, la norme du dépôt :

| Couche | Contenu | Pourquoi là |
| :-- | :-- | :-- |
| `deliverable/domain/` | **la frontière du §3** — ce qui monte à l'écran, ce qui reste dans la note ; le jugement de citation (pur, sur des chaînes) | C'est la seule partie qui porte une décision de produit. Elle doit se tester sans lxml, sans base, sans fichier |
| `deliverable/application/` | l'assemblage : lire la préparation, vérifier les conditions, appeler le rendu | Port `DeliverableRenderer` |
| `deliverable/infrastructure/` | **les deux seuls fichiers qui importent `docx` et `pptx`** | Même posture que `adapters/mistral.py` : la bibliothèque tierce reste à la bordure |

### 5.1 Les routes (mobile — le client est Flutter)

```
POST /api/mobile/urim/studies/{id}/deliverable                soumet les diapositives, rend les verdicts
GET  /api/mobile/urim/deliverables/{id}/fichier?format=…      rend les octets — seulement si 'conforme'
```

Le `format` (`pptx` | `docx` | `pdf`) est un **paramètre de la lecture**, pas une seconde
validation : le document est validé une fois, il s'encode ensuite comme le pasteur en a besoin
(§3.2). Le défaut est le format natif du document — le PDF se demande, il ne s'impose pas.

Deux routes plutôt qu'une : la validation est un **écran**, pas une étape invisible d'un
téléchargement. Le pasteur doit voir ce qui sortira avant que ça sorte — c'est le passage
obligatoire que la règle centrale exige, et il n'existe que s'il a sa propre requête.

⚠️ **Le livrable se génère toujours depuis une préparation existante, jamais depuis une saisie
libre.** Une route qui accepterait « Romains 8 » et rendrait un document court-circuiterait V1,
la propriété (`author_id`) et la trace, d'un seul paramètre.

### 5.2 Stockage : **flux, pas `media`** — tranché

| Option | Verdict |
| :-- | :-- |
| Réutiliser le contexte `media` | ⛔ **Non.** `MediaStore.put` rend une **URL publique** (statique en dev, S3/CDN en prod). Une préparation appartient à son auteur et reste invisible à l'administrateur de son église ; la publier derrière une URL devinable ou partageable contredirait la seule garde qui la protège. Accessoirement, `media_allowed_types` ne connaît que des images et des vidéos |
| Servir en **flux authentifié** | ✅ **Retenu.** Le fichier est produit à la demande, rendu dans la réponse, et **n'est stocké nulle part**. Un `.pptx` de sermon pèse quelques dizaines de kilo-octets : le régénérer coûte moins cher que le garder |

**Ce qu'on garde n'est pas le fichier, c'est ce qui a été projeté** — et le dépôt le stocke déjà :
`citation_check` conserve, par diapositive, la référence et le `projected_text`. **On sait donc
exactement ce qui est monté à l'écran sans conserver un seul octet de binaire.** C'est la même
économie que partout ailleurs dans Dorea : garder le fait, pas l'artefact.

---

## 6. La bibliothèque — licences et poids réels

| | Licence | Déjà là ? |
| :-- | :-- | :-- |
| **`python-pptx` 1.0.2** | **MIT** | ✅ **déclaré dans `pyproject.toml`** (contexte `sermon`, S-5, en *lecture*) et **installé** dans le `.venv` |
| **`python-docx`** | **MIT** (même auteur, même architecture) | ❌ à ajouter |
| `lxml` 6.1.1 | BSD-3 | ✅ ~10 Mo — **la seule dépendance de `python-docx`**, déjà tirée par `python-pptx` |
| `Pillow` 12.3.0 · `XlsxWriter` | MIT-CMU · BSD-2 | ✅ ~16 Mo — tirés par `python-pptx`, **rien à voir avec `docx`** |
| **LibreOffice** *(conversion PDF, §3.2)* | **MPL-2.0** — invoqué comme **processus**, jamais lié au code : aucune obligation ne remonte au dépôt | ❌ **paquet système**, pas une dépendance Python. Il n'apparaîtra **ni dans `pyproject.toml` ni dans `uv.lock`** — il vit dans le `Dockerfile`, et c'est là qu'il faudra le voir |

**Le poids ajouté par `python-docx` est donc d'environ un demi-mégaoctet.** Le vrai coût — lxml et
Pillow — est déjà payé depuis S-5. Aucune licence n'est copyleft ; aucune n'impose de mention dans
un produit distribué.

⚠️ **Le PDF déplace le vrai coût hors de Python.** Les trois formats coûtent ensemble moins d'un
mégaoctet de dépendances ; la conversion, elle, se paie en **centaines de mégaoctets d'image** et en
un processus à surveiller (§3.2). Le tableau ci-dessus ne doit pas donner l'impression que le PDF
est gratuit parce qu'il n'ajoute aucune ligne au lock.

⚠️ **Deux choses à savoir avant d'exécuter `uv add python-docx` :**

1. **`uv.lock` est en retard sur `pyproject.toml`** — il ne contient **ni `python-pptx` ni
   `pypdf`**, pourtant déclarés. La prochaine résolution les y fera entrer en même temps que
   `docx` : le diff du lock sera plus large que la ligne ajoutée, et ce n'est pas un accident.
2. **Le plan de retrait de `sermon`** ([`Plan_Urim_Producteur.md`](Plan_Urim_Producteur.md), 2026-08-05)
   supprimerait l'extracteur S-5, seul usage actuel de `python-pptx`. Le livrable en devient
   l'unique porteur — en **écriture** cette fois. La dépendance ne disparaît donc pas avec
   `sermon` ; elle change de justification, et il vaut mieux que ce soit écrit avant que quelqu'un
   la retire en nettoyant.

> Et une garde à ne pas perdre en chemin : `sermon` mesure un `.pptx` **décompressé** avant de
> l'ouvrir (bombe zip, `_guard_zip_bomb`). Elle protège la **lecture** de fichiers reçus. Le
> livrable ne fait qu'écrire — la garde ne s'applique pas, et sa disparition avec `sermon`
> n'est un problème que le jour où Urim acceptera un import (`deliverable/` le prévoit).

---

## 7. La trace — *une décision ne vaut que sur l'objet qu'elle a regardé*

Le dépôt tient déjà cette règle à trois endroits : `corpus_snapshot` sur la préparation (le moteur
n'est déterministe qu'à corpus constant), `input_hash` sur les suggestions du modèle,
`judged_fingerprint` sur la curation — *« périme le verdict quand ce qu'il jugeait change »*.

**Un livrable pose exactement la même question, et plus durement : il est daté, il est sorti de
l'application, et il sera relu en chaire une semaine plus tard.** Un document produit contre une
curation qui a changé depuis n'est pas faux — il est **antidaté**, et rien à l'écran ne le dit.

> **Tranché : le livrable est enregistré. Qui, quand, sur quelle préparation, et contre quel état.**

| Ce qu'on enregistre | Pourquoi |
| :-- | :-- |
| `preparation_id`, `kind`, `generated_at` | déjà au schéma |
| **`validated_by` + `validated_at`** | Le patron du dépôt : `reviewed_by NOT NULL` côté corpus, `synthese_validee_signee` côté Retour. **Un `validation = 'conforme'` sans signataire serait une validation que personne n'a faite** — précisément ce que la règle centrale interdit. Contrainte à ajouter |
| **`corpus_snapshot`** *(celui du moment de la génération)* | La préparation porte le sien ; s'ils divergent, le document a été produit contre un autre corpus que celui où le raisonnement a été mené |
| **`content_fingerprint`** *(empreinte de ce qui a été imprimé — plan, bornes, références)* | Deux documents de la même préparation à deux semaines d'écart ne sont pas le même document. Sans empreinte, on ne peut ni le dire ni le prouver |
| `citation_check` (référence + `projected_text` + verdict, par diapositive) | **L'archive de ce qui est monté à l'écran** — déjà au schéma, et c'est ce qui dispense de garder le fichier |

**Ce que la trace autorise ensuite** — et qui vaut mieux qu'un blocage : `StudyView.corpus_drifted`
existe déjà. Rouvrir une préparation dont le corpus a bougé peut **le dire**, et proposer de
régénérer. Bloquer une régénération pour dérive serait punir un pasteur pour un enrichissement
qu'il n'a pas demandé (`Q4`).

---

## 8. Le quota — vérifié, aucun contournement

**La génération d'un document ne fait aucun appel de modèle. Elle ne doit donc rien décompter.**
Vérification faite contre le code, pas contre l'intention :

| Fait vérifié | Où |
| :-- | :-- |
| Ce qui est compté, ce n'est ni un appel ni une lecture : c'est une **réservation par texte** (`pericope_key`), posée à l'ouverture | `UrimStudyReservationModel` |
| `metered_at` ne se pose **qu'au premier service `metered`**, via `mark_assisted`, et seulement si le résolveur a été **effectivement sollicité** (`sollicite`) — une fois par réservation | `app/contexts/urim/application/study_service.py:1142` |
| Le plafond éteint **l'assistance**, jamais Urim : corpus, pesées, concordance et contrôle de référence continuent | `app/contexts/urim/application/study_service.py:936` |
| Sans église (l'antichambre), il n'y a **ni réservation ni fenêtre** | feuille de route, Lot D |

**Trois conséquences, dont une garde à écrire :**

1. Générer un document sur une préparation existante **ne peut rien coûter** : la réservation est
   déjà posée, `metered_at` déjà décidé, et aucun chemin du livrable ne touche le résolveur.
2. **Le contournement possible n'est pas là où on le craint.** Servir du texte biblique n'est pas
   facturé — `GET /passages` le fait déjà en lecture pure, sans réservation. Ce qui est compté,
   c'est l'assistance du modèle, et le livrable n'en demande aucune. **Il n'y a donc pas de porte
   dérobée vers le corpus** ; le §5.1 (jamais depuis une saisie libre) ferme la seule qui vaille,
   et il la ferme pour la propriété et la trace, pas pour l'argent.
3. ⚠️ **La garde à écrire** : la génération lit la préparation, donc **rejoue le pipeline** — et un
   rejeu peut solliciter le modèle. C'est déjà vrai de chaque `GET /studies/{id}`, et
   `mark_assisted` est idempotent par réservation : rien ne double. Mais la propriété *« générer un
   document ne consomme rien »* mérite **son test**, sinon elle ne survivra pas à la première
   refonte du rejeu.

---

## 8 bis. ✅ **Livré le 2026-08-13** — la validation, les deux rendus, quatre routes

| Lot | Pièces |
| :-- | :-- |
| **Le cœur pur** | `deliverable/domain/citation.py` (trois verdicts, gloses, toutes les versions) · `documents.py` (la frontière **portée par les types**) |
| **La validation** | migration `f4a5b6c7d8e9` (`kind` × `format`, signature, empreinte) · `deliverable/application/service.py` · `persistence/deliverable_repository.py` |
| **Les rendus** | `deliverable/infrastructure/renderers.py` — **les deux seuls fichiers qui importent `pptx` et `docx`**, en import paresseux |
| **Les routes** | `POST /studies/{id}/deliverable` · `GET /deliverables/{id}` · `GET /deliverables/{id}/fichier` · (+ archive) |

**Ce que l'écriture a appris, et qui n'était pas dans la conception :**

1. **`load_corpus_index` ne charge le texte que de la version de repli.** Quatre versions sont
   semées ; l'index n'en sert qu'une. Q9 aurait donc jugé contre une seule sans que rien ne le
   signale. Le contrôle lit les autres **en base** — c'est un geste rare, et charger quatre
   versions dans l'index ferait payer à chaque résolution le prix d'un contrôle hebdomadaire.
2. **Le motif d'un contrôle ne se stocke pas**, il se recalcule. Le corpus peut apprendre une
   version qu'il ignorait ; une phrase figée continuerait d'accuser un texte désormais reconnu.
3. **La note se bâtit sur le dossier rejoué** (`UrimStudyService.get`), passé en port : les
   pesées, les mises en garde et les motifs ne sont nulle part en base sous forme lisible — le
   moteur rejoue au lieu de stocker sa trace. Et ce rejeu ne persiste rien, **donc ne consomme
   rien** : le service du livrable n'a ni port de réservation ni résolveur, et un test tient
   cette absence.
4. **La section « mots de l'original » reste vide** : `StudyDTO` ne les rend pas (ils vivent dans
   la vue « en savoir plus sur un passage »). Vide **et nommée**, plutôt qu'inventée.

**Ce qui reste** : le **PDF** (§3.2) — LibreOffice dans le `Dockerfile`, conversion bornée — et
la fermeture des dix codes Braga (§9.4), qui touche une route déjà en service.

⚠️ **`uv` n'étant pas dans le `PATH`, `python-docx` a été installé par `pip` et déclaré dans
`pyproject.toml` ; `uv.lock` reste en retard** (il ignore déjà `python-pptx` et `pypdf`). Le
prochain `uv sync` les y fera entrer tous les trois d'un coup.

---

## 9. Ce que cette note appelle comme code — et où elle s'arrête

Elle s'arrête ici. Voici ce qu'il faudra écrire, pour que personne ne le découvre en cours de route.

**Une migration** (le schéma actuel refuse le livrable demandé) :

| # | Delta | Motif |
| :-- | :-- | :-- |
| 1 | **`kind IN ('deck','note')` + `format IN ('pptx','docx','pdf')`**, et un `CHECK` qui interdit *deck × docx* et *note × pptx* | `docx` est aujourd'hui **interdit par la contrainte** ; et une seule colonne ne peut pas dire à la fois *quel document* et *sous quel encodage* — or c'est la frontière du §3 qu'on perdrait dans la trace (§3.2). Table jamais écrite : aucune reprise |
| 2 | `deliverable` : **+ `validated_by`, `validated_at`**, et un `CHECK` — `validation = 'conforme'` ⇒ les deux `NOT NULL` | §7 : une validation sans signataire n'est pas une validation |
| 3 | `deliverable` : **+ `corpus_snapshot`, + `content_fingerprint`** | §7 |
| 4 | **Fermer la liste des dix codes Braga** — `preparation_element.element_code` est aujourd'hui un texte libre, sans `CHECK` ni validation | §1.3 bis : le seuil s'adosse au code `proposition`. Une liste ouverte le rend contournable par une majuscule, **et refuse un pasteur qui avait pourtant écrit son point central**. Même patron que les dix `doctrinal_axis` et les trois `plan_source` : des codes de référence semés par la migration |

⚠️ **Le delta 4 déborde le livrable et doit être traité comme tel.** Il touche une route déjà en
service (`PUT /studies/{id}/elements`) : fermer la liste rendra invalide tout `element_code` qu'un
client enverrait aujourd'hui hors des dix. À vérifier contre le client Flutter **avant** la
migration — un verrou de sortie ne doit pas casser une saisie qui marche.

**Quatre modules** : la frontière du §3 (pur), le jugement de citation (pur, sur des chaînes
normalisées + `versification_map`), deux rendus derrière un port. **Deux routes** (§5.1). **Un
repository** pour deux tables déclarées et jamais écrites.

**Et les tests qui tiennent les propriétés**, sans lesquels cette note n'est que du texte :

- une diapositive dont un mot est changé est **`altere`** ; la même tronquée est **`extrait`**
  *(le couple accepté/refusé — une garde qui rejette tout ne prouve rien)* ;
- **aucun fichier n'est produit tant qu'une diapositive est `altere`** ;
- une préparation **sans `proposition`** refuse, avec motif — et la **même** préparation, la seule
  proposition renseignée, produit son document *(le couple : sans lui, la garde pourrait tout
  refuser et paraître juste)* ;
- **une proposition d'un seul mot suffit** — le test constate, il n'apprécie pas (§1.3 bis) ;
- **le `.pptx` ne contient ni `caveat`, ni `rationale`, ni `proof_text_risk`** — par inspection du
  document produit, pas par relecture du gabarit ;
- **générer ne pose ni `metered_at`, ni réservation nouvelle** (§8.3) ;
- **aucun PDF ne sort d'un livrable qui n'est pas `conforme`**, et **une conversion en échec rend
  quand même le format natif** (§3.2c) — les deux règles du PDF, chacune avec son test.

**Et un mot sur ce que la migration ne peut pas garder :** les couples impossibles (*deck × docx*,
*note × pptx*) sont refusés par la base, pas par le service. Un `CHECK` tient sans qu'on y pense ;
une validation applicative se contourne par le prochain chemin d'écriture qu'on ajoutera.

---

## 10. Le point de jonction avec S-6 (la dictée)

La note de transcription et celle-ci se rejoignent en un endroit précis, et un seul :
**le squelette Braga (V1) est la seule chose que le pasteur doive écrire.** C'est aussi la plus
pénible à taper sur une tablette, un vendredi soir.

Une dictée qui remplit les éléments de son plan satisfait donc V1 — **à une condition qui vient
tout entière de S36** : `entry_origin` distingue déjà le tapé du dicté, parce qu'*« une entrée
dictée par un micro ouvert ne se corrige pas comme une faute de frappe »*. Un plan dicté doit être
**confirmé** avant d'entrer dans un document, avec ce qui a été entendu rendu tel quel. Sans quoi
le livrable imprimerait, sous le nom du pasteur, ce qu'un moteur de transcription a cru comprendre
— et V1 serait satisfaite par une machine, ce qui est exactement le contraire de son objet.

⚠️ **Le quatrième mur tient ici aussi** (S29) : le modèle ne voit jamais la préparation. Un livrable
ne devient pas une entrée de prompt parce qu'il est bien mis en page.

### 10.1 Et après la chaire — l'archive, qui n'existe pas

Cette note s'arrête à la porte de la chaire, et **rien n'attend le pasteur de l'autre côté** :
`urim_preached` est **lue par l'étage 7 et écrite par personne**, la route d'archivage n'existe pas,
et la fusion avec le Retour n'était conçue nulle part.

C'est l'objet de [`Urim_Archive_Predications.md`](Urim_Archive_Predications.md) (2026-08-13) — le
geste d'archivage, ce que le transcript peut proposer sans jamais réécrire, et le rangement par
loci qui **montre sans prescrire**. Le lien avec le livrable est direct : le document est la
dernière chose produite avant le dimanche, l'archive est la première après.

---

## 11. Questions ouvertes — **toutes tranchées le 2026-08-13**

| # | Question | Décision |
| :-- | :-- | :-- |
| **Q1** | ~~Qui peut générer le livrable d'une préparation d'église ?~~ | ✅ **Qui peut la lire peut la générer** — on réutilise la garde existante (`_ensure_owner_or_preacher`) plutôt que d'écrire une seconde définition de « mes préparations », qui divergerait. **Mais `validated_by` est celui qui a validé, pas l'auteur** : un collègue qui génère produit un document signé de son nom. La responsabilité reste nominative, et l'écran le dit |
| **Q2** | ~~Conserver le fichier, ou le régénérer ?~~ | ✅ **Régénérer — aucun binaire conservé** (§5.2). Le pasteur qui veut *exactement* le fichier de dimanche dernier **l'a déjà** : il est sur son téléphone. Stocker les documents privés de tous les prédicateurs pour un besoin que l'appareil couvre serait une charge de confidentialité durable contre un bénéfice nul. Ce que le serveur garde, c'est **ce qui a été projeté** (`citation_check`) et l'empreinte (§7) |
| **Q3** | ~~Le `.pdf` : abandonné ou gardé ?~~ | ✅ **Tranché le 2026-08-13 : gardé** — c'est le format qui circule vraiment. **Conversion** du fichier déjà validé (LibreOffice sans interface), **jamais** un troisième rendu ; `kind` se scinde en *document* × *format* (§3.2). ⚠️ Coût réel : premier processus externe du backend, image Docker changée d'ordre de grandeur |
| **Q4** | ~~Corpus dérivé : avertir ou bloquer ?~~ | ✅ **Avertir, jamais bloquer.** Un enrichissement du corpus n'est pas une faute du pasteur ; lui refuser son document parce qu'un autre a curé une péricope serait le punir d'un travail qu'il n'a pas demandé. `corpus_drifted` existe déjà et dit la vérité — la régénération reste à lui |
| **Q5** | ~~La note porte-t-elle une mention « ne pas diffuser » ?~~ | ✅ **Oui — en pied de CHAQUE page, jamais une page de garde.** Une page de garde ne survit ni à une capture d'écran, ni à un partage partiel, ni à une impression recto. Formulation : *note de préparation — mises en garde destinées au prédicateur* |
| **Q6** | ~~Quelle police pour le grec (et l'hébreu) ?~~ | ✅ **Une police sous licence OFL, incorporée au document** — l'OFL autorise explicitement l'incorporation, contrairement à la plupart des polices système. **Si l'incorporation échoue, la section s'imprime quand même avec un nom de police explicite** : jamais de retrait silencieux, jamais de translittération inventée à la place |
| **Q7** | ~~Le seuil de « quelque chose de lui » : combien d'éléments Braga ?~~ | ✅ **Tranché le 2026-08-13 : le point central seul suffit** — un élément, la `proposition`, jamais jugée sur son contenu (§1.3 bis). **Ouvre un delta hors livrable** : fermer la liste des dix codes (§9.4) |
| **Q8** | ~~Un plan dicté puis confirmé satisfait-il V1 ?~~ | ✅ **Oui, sous confirmation explicite** (§10) — ce qui a été entendu est rendu tel quel avant d'entrer dans un document. Sans cette confirmation, V1 serait satisfaite par un moteur de transcription, ce qui est exactement son contraire |

| **Q9** | ~~Le texte projeté vient d'une version que le corpus ne détient pas~~ | ✅ **Tranché le 2026-08-13 : on juge contre TOUTES les versions détenues**, et le verdict **nomme celle qui reconnaît le texte** (§2 ter.4). Le `CHECK` de `citation_check` ne bouge pas — pas de quatrième verdict *invérifiable*, qui deviendrait la porte de sortie de n'importe quoi. Ce qui reste refusé est un **manque de corpus** à combler, pas une règle à assouplir |

> **Toutes tranchées le 2026-08-13**, Q9 comprise — ouverte et refermée le même jour par trois
> prédications réelles (§2 ter). **Et la construction est ouverte sur demande explicite de
> l'auteur** — comme le socle du chantier 0 l'avait été le 03/08. Le §11 d'`Architecture v2` n'est
> pas *levé* pour autant : le dimanche réel n'a pas eu lieu, et R1 (dispersion) reste le risque
> dominant. C'est une décision de l'auteur, prise en connaissance de cause, pas une condition
> devenue vraie.

---

*Note de conception. Elle ne devance pas le §11 d'`Architecture v2` : Urim n'est toujours pas
autorisé à la construction, et le seul verrou qui reste — **un dimanche réel, dans une église
réelle** — n'est pas de ceux qu'un document lève.*
