# Urim — raccord des quatre specs entrantes au moteur construit

> **Nature :** note de lecture, 22 août 2026. **Aucune ligne de code n'a été touchée.**
>
> Quatre documents sont entrés ce jour et sont versés tels quels :
> [`Urim_Spec_Conversationnelle_v2.md`](Urim_Spec_Conversationnelle_v2.md),
> [`Urim_Cahier_Recette.md`](Urim_Cahier_Recette.md),
> [`Urim_Grammaire_Homiletique.md`](Urim_Grammaire_Homiletique.md),
> [`Urim_Spec_Renforcement.md`](Urim_Spec_Renforcement.md).
>
> **Statut des quatre : specs entrantes, non appliquées.** Cette note dit ce qu'elles décrivent
> réellement de ce dépôt, ce qu'elles décrivent d'ailleurs, et ce qu'il en reste une fois la
> confrontation faite.

---

## 0. La décision prise ce jour

Le point le plus lourd des quatre documents est tranché avant tout le reste, parce que trois
renforcements en dépendent.

> **§7 de la spec conversationnelle et RF2 posent un proforma rédigé complet** — *« pour
> développer Romains 8, le modèle doit lire Romains 8 »*. Ce dépôt tient le verrou **inverse**,
> et le verrou tient.

Le livrable exige une **division écrite par le pasteur**
([`deliverable/domain/documents.py`](../app/contexts/urim/deliverable/domain/documents.py)) :

> *« Le thème ne peut pas non plus tenir ce rôle, et c'est décisif : `propose_theme` le remplit
> d'office. Un verrou que le moteur satisfait lui-même n'est pas un verrou. »*
>
> *« Le moteur n'en écrit jamais aucune : un plan qui arrive complet n'est pas un plan que
> quelqu'un a préparé. »*

Ce seuil n'est pas une position doctrinale flottante : il a été **corrigé le 13/08/2026 par
trois prédications réelles** (`docs/temoins/`), après qu'une première rédaction adossée à la
*proposition* de Braga aurait refusé son document aux trois pasteurs pour qui il est écrit.
Une spec écrite sans ces trois témoins ne le défait pas.

**Conséquence, et elle est nette :**

| Élément | Sort |
|---|---|
| §7 « contrat de marqueurs » (le modèle rédige, `{{Rm 8:1}}` résolu au rendu) | **écarté** — il n'y a pas de texte rédigé par le modèle où poser un marqueur |
| RF2 (le proforma s'arrête où les notes s'arrêtent) | **sans objet** — on ne referme pas ce qu'on n'ouvre pas |
| RF3 (marqueur d'emplacement) | **partiellement récupérable**, voir §5 |
| RF5-A (*les sujets de prière dérivent du proforma*) | **à réécrire** — ils dériveront du plan du pasteur, voir §5 |
| I13, I20, I21 | **sans objet en l'état** |

⚠️ RF2 et G8 ont raison sur le **constat** — les notes des trois sermons s'arrêtent en pleine
phrase — et ce constat renforce le verrou au lieu de l'affaiblir : si le pasteur n'écrit pas sa
fin, une machine qui l'écrit à sa place ne comble pas un manque, elle prend la place de l'oral.

---

## 1. Pourquoi cette note existe

La spec conversationnelle §5 écrit : *« **Implémenté** :
`app/contexts/urim/conversation/route_turn.py`, 50 tests verts »*. **Ce fichier n'existe pas
dans ce dépôt.** Ni `route_turn`, ni `TurnReading`, ni `TurnKind`, ni `CIVILITE`, ni
`vestibule` n'apparaissent dans une seule ligne de `app/`.

Ce n'est pas un reproche à la spec — elle décrit un objet voisin, peut-être une autre branche,
et son raisonnement se tient. C'est un avertissement de lecture : **une citation de fichier a
l'air vérifiable**, et la famille A du cahier de recette (six scénarios, six invariants) serait
écrite contre un objet absent par quiconque l'ouvrirait en croyant tester ce moteur.

---

## 2. L'état réel au 22 août 2026

≈ 370 tests sur `tests/contexts/urim/`.

| Pièce | Ce que la spec suppose | Ce que le dépôt a | Verdict |
|---|---|---|---|
| Les étages | 10 étages, `route_entry` → `shape_homiletic` | `PIPELINE` **plein** : 9 entrées, 8 étages + `WeighConviction` en chemin inversé ([`pipeline.py`](../app/contexts/urim/engine/pipeline.py)) | ✅ concordant au décompte près (§3) |
| §1 · `weigh_conviction` étage 1-bis | requalification à faire | **déjà là**, et pour le motif exact que la spec donne | ✅ acquis |
| Le tour | vestibule `lire_tour`, 7 règles, puis Mistral qui affine | **liaison exacte → aiguilleur (7 codes) → répondeurs déterministes** ([`application/conversation.py`](../app/contexts/urim/application/conversation.py)) | ⚠️ divergent (§4.2) |
| Les blocs du fil | `{parole, question, texte, refus, outil}` persistés, `CHECK` en base | blocs **typés et reconstruits à chaque tour** : `chips`, `units`, `bounds`, `bearings`, `feasibility`, `theme`, `actions` ([`interface/turn.py`](../app/contexts/urim/interface/turn.py)) | ⚠️ divergent (§4.4) |
| Homilétique | `HomileticFit` × 4 gabarits déduits | couple **plan × matière**, faisabilité **curée en base**, refus motivé ([`shape_homiletic.py`](../app/contexts/urim/engine/stages/shape_homiletic.py)) | ⚠️ deux référentiels (§4.3) |
| Le proforma | un document rédigé | **deux documents** — deck `.pptx` (l'assemblée) et note `.docx` (le prédicateur), séparés par un **type**, pas par un filtre | ⚠️ tranché (§0) |
| Réservoir sémantique §9 | pgvector, embedding local CPU, scan exact | **rien.** Aucune dépendance, aucune table, aucune ligne | ✅ terrain vierge (§5) |
| Paliers 0/1/2 | dégradation sans mur | doctrine tenue **et mesurée** : `Outcome.DEGRADE` ne coupe jamais, les adaptateurs `Null*` sont des états de production, `scripts/urim_banc_arbre.py` marche l'arbre | ✅ acquis, plus fort que la spec |
| O4 · « aucun verset inventé » | *« à instrumenter »* | **instrumenté** : trois verdicts `exact` / `extrait` / `altere` ([`deliverable/domain/citation.py`](../app/contexts/urim/deliverable/domain/citation.py)) + table `urim_citation_check` | ✅ la case du cahier est fausse pour ce dépôt |

---

## 3. Les faux-amis — même mot, deux sens

C'est la partie la plus dangereuse du raccord : ces mots se lisent sans frotter.

| Mot | Dans les specs | Dans ce dépôt |
|---|---|---|
| `metered` / `ceiling_reached` | plafond d'**abonnement** au modèle ; E3 fait retomber le produit au palier 1 | plafond de **licence de traduction** — trop de versets servis depuis une version sous droits. Le moteur n'en voit rien d'autre ([`application/ports.py:105`](../app/contexts/urim/application/ports.py#L105)) |
| « le vestibule n'est jamais `metered` » (I12) | le modèle ne doit pas garder la porte | **l'argument est déjà écrit**, mais sur `route_entry` : *« s'il était une étape modèle il serait `metered` : au plafond, la porte d'entrée disparaîtrait »* |
| `expositif` | un **gabarit déduit** d'un déclencheur constatable (RF1) | une **source de plan curée**, moitié d'un couple relu par un humain |
| « dix étages » | dix | neuf entrées, **huit étages** — le neuvième est l'alternative de l'étage 1, pas sa suite |
| « bloc » | ligne persistée avec un `kind` et un `CHECK` | modèle de présentation typé, reconstruit à chaque tour, jamais stocké |
| « proforma » | un document rédigé | deux livrables qui **refusent de sortir sans plan du pasteur** |

⚠️ **E3 et I12 sont à réécrire avant tout test.** Écrits tels quels, ils testeraient le plafond
de licence en croyant tester le plafond d'abonnement — et passeraient au vert pour la mauvaise
raison.

---

## 4. Les divergences structurelles

### 4.1 Le proforma rédigé

Tranché en §0.

### 4.2 Le vestibule

Les sept règles de `lire_tour` classent une saisie **avant** tout appel, puis Mistral *affine*.
Ce dépôt fait l'inverse dans l'ordre et la même chose dans l'esprit : la **liaison** — exacte,
déterministe, zéro appel — prend le tour ; l'aiguilleur ne coûte quelque chose que si elle rend
la main. Sur les six tours de la maquette, **quatre sont des liaisons**.

Ce que le dépôt a **en plus** de la spec, et qu'aucun des quatre documents ne prévoit :

- **le contrôle de référence passe avant la liaison** — `Hb 2v29` s'entend répondre *« Hébreux 2
  compte 18 versets »* au lieu d'être silencieusement lu comme l'option « Hébreux 2 » ;
- **une panne n'est pas une réponse** — photo du compteur d'échecs avant et après l'appel, pour
  ne jamais servir *« je n'ai rien reçu qui concerne la préparation »* à un pasteur dont la
  seule faute est d'avoir écrit pendant une coupure ;
- **l'acquiescement hors attente ne dit rien et ne coûte rien** ;
- `Tour.appels` — *« ce n'est pas de la télémétrie : c'est la mesure du défaut »*.

Ce que la spec a en plus : les règles 2 et 3 — civilité, méta. Voir §7 : c'est le seul endroit
où le cahier de recette mord sur du code réel.

**Famille A du cahier de recette : à ne pas écrire telle quelle.** A1, A5 et A6 visent des
`TurnKind` qui n'existent pas ; A2, A3 et A4 énoncent des propriétés que la liaison tient
autrement — *une cible sans geste n'est une décision que si le moteur attend une décision* — et
qui méritent d'être **retraduites** avant d'être testées.

### 4.3 RF1 — deux référentiels concurrents pour la même sortie

`HomileticFit(gabarit, franchi, motif)` **déduit** la faisabilité de déclencheurs constatables.
`deps.homiletics.couples_for(pericope_id)` la **lit d'un relu humain**, et distingue déjà deux
choses que RF1 confond :

    aucune ligne    →  personne n'a encore regardé        →  DEGRADE
    que des refus   →  quelqu'un a regardé, rien ne tient →  refus motivé, couple par couple

Cette distinction a été payée : sans elle, *ajouter du relu rendait la sortie pire*. RF1-B
(« un texte qui ne porte aucun gabarit produit un refus explicable ») est donc **déjà tenu**,
par la curation et non par la déduction. RF1-C (les quatre toujours rendus) l'est aussi, sous
un autre nom : *les couples refusés voyagent avec les faisables*.

Ce que RF1 apporte vraiment, et qui manque ici : un **vocabulaire de forme** — onomastique,
lexical, narratif allégorisé — que le couple plan × matière ne nomme pas. La question n'est donc
pas « déduire ou curer », c'est : *ouvre-t-on la liste des sources de plan curées à ces quatre
formes ?* Question de curation, pas de moteur.

### 4.4 Le fil n'est persisté ni en tours ni en blocs

Il n'existe ni `urim_thread`, ni `urim_thread_turn`, ni `urim_thread_block`. L'état vit sur
`urim_preparation`, ses éléments et les décisions ; le tour se **rejoue** depuis la trace —
c'est pourquoi `corpus_snapshot` est persisté.

Donc **les contre-scénarios X1, X2 et X9 n'ont aucune surface** dans ce dépôt. La propriété
qu'ils protègent — *le proof-texting devient inécrivable* — y est tenue ailleurs : `serve_corpus`
est seul à servir du texte, et le contrôle de citation juge ce qui est projeté.

§11 reste une **proposition ouverte** : faut-il matérialiser le fil ? Le fil d'accueil sait déjà
dire où en est chaque préparation *sans rejouer le moteur*, ce qui était le besoin réel.

---

## 5. Ce qui s'applique tel quel

| # | Ce qui entre | Pourquoi c'est propre |
|---|---|---|
| §9 | **Le réservoir sémantique** | Terrain entièrement vierge, et **aucune contradiction** avec le construit : additif (S37), sans force (`BearingSite` qualifie seul), rejouable. C'est le lot le plus sain des quatre documents. Coût réel : pgvector + un embedding local — **zéro dépendance aujourd'hui**. |
| R5 | La chute d'AS12 | *La similarité cosinus ne détecte pas la contradiction* — c'est déjà la doctrine du dépôt ([`corpus/readers.py:211`](../app/contexts/urim/infrastructure/corpus/readers.py#L211)). Rien à défaire. |
| RF3 | Le **trou nommé** | Le contrat `{{...}}` tombe avec §0, mais `temoignage` **est déjà un code d'élément** ([`domain/squelette.py:63`](../app/contexts/urim/domain/squelette.py#L63)), et la liste des codes reste ouverte en base. RF3-B — « le modèle peut poser un emplacement, jamais le remplir » — est ici **gratuit** : le modèle n'écrit rien. |
| RF5 | Les deux livrables dérivés, **réécrits** | Pensée directrice et sujets de prière dérivent du **plan écrit par le pasteur**, jamais d'un proforma. RF5-C (disponibles au palier 1) devient alors vrai **pour de bon** : aucun modèle n'est en jeu. RF5-D — le dirigeant de réunion, second compte flottant dans la même église — est intact, et reste l'argument le plus fort des quatre documents. |
| §13 | *Urim ne tranche pas une controverse entre confessions* | Règle manquante, et elle manque **aussi ici**. À écrire au rang de « il n'écrit pas le sermon ». |

---

## 6. Les vingt-deux invariants — statut réel dans ce dépôt

| # | Statut ici |
|---|---|
| I1 · `bonjour` n'ouvre rien | ⚠️ tenu **à l'entrée** — `route_entry` refuse le charabia sans modèle — **non tenu en cours de fil** (§7) |
| I2 · le tour suivant une question ne crée pas d'entrée | ✅ tenu autrement (`ecran.attend` : hors attente, une désignation nue n'a pas de geste) |
| I3 · seuls `TRAVAIL` / `REPONSE` portent un `carry` | ⛔ sans objet |
| I4 · le motif n'est jamais vide | ✅ tenu, sur tout le pipeline (tests d'architecture) |
| I5 · lecture déterministe et rejouable | ✅ tenu — la liaison ne devine jamais |
| I6 · aucun bloc `texte` ne porte de corps | ⛔ sans objet (§4.4) — propriété tenue par `serve_corpus` et le contrôle de citation |
| I7 · aucune sortie sans l'étage franchi | ✅ tenu par construction — `StageResult` refuse un `AWAIT` sans options |
| I8 · un refus est dit dans le fil, motivé | ✅ tenu — `REFUSE` porte son motif, les refusés voyagent avec les faisables |
| I9 · modèle injoignable → ça dégrade | ✅ tenu, et mesuré (banc de l'arbre) |
| I10 · le contexte n'enfle pas avec le fil | ✅ tenu par construction — l'aiguilleur reçoit la saisie, jamais l'historique |
| I11 · rejeu à corpus et décisions constants | ✅ tenu (`corpus_snapshot`, moteur pur) |
| I12 · le vestibule jamais `metered` | ⚠️ **à réécrire** — faux-ami (§3) |
| I13 · marqueur non résolu = refus visible | ⛔ sans objet (§0) |
| I14 · `weigh_conviction` s'efface | ✅ tenu |
| I15 · le réservoir ne retire jamais | 🔜 à écrire avec le réservoir |
| I16 · même recherche, même ordre | 🔜 à écrire avec le réservoir |
| I17 · panne du réservoir sans refus | 🔜 à écrire avec le réservoir |
| I18 · le réservoir ne pose aucune force | 🔜 à écrire avec le réservoir |
| I19 · les quatre `HomileticFit` toujours rendus | ⚠️ tenu sous un autre nom (§4.3) |
| I20 · un emplacement jamais rempli | ✅ gratuit ici (§5) |
| I21 · le proforma ne referme pas | ⛔ sans objet (§0) |
| I22 · les deux dérivés au palier 1 | 🔜 à écrire avec RF5 réécrit |

**Quatre des invariants marqués « à écrire » sont déjà tenus** — I7, I8, I10, I11 — sous
d'autres noms et par d'autres pièces. Quatre autres sont sans objet.

---

## 7. Le seul défaut que ces documents révèlent dans le code

> **« Bonjour » en cours de fil coûte un appel.**

La liaison ne le reconnaît pas — aucune option ne s'appelle ainsi ; la saisie porte des jetons,
donc le court-circuit `indechiffrable` ne s'applique pas ; et le tour part à l'aiguilleur, qui
le classe `hors_champ` ou `indechiffrable`. Le pasteur reçoit une réponse correcte, et on a payé
un appel pour apprendre qu'il n'y avait rien à apprendre.

Ce n'est **ni un mur ni une panne** : le repli déterministe existe (`repondre_sans_lecture`).
C'est exactement le défaut que `conversation.py` se donne lui-même pour critère — *« un tour que
la liaison pouvait résoudre et qui compte un appel est le bogue même que ce module vient
corriger »*.

La règle 2 de `lire_tour` — ≤ 4 mots, tous de politesse — est **la seule des sept qui se
transpose sans rien défaire** : un vocabulaire fermé, en amont de l'aiguilleur, au même rang que
les marqueurs de retrait que la liaison possède déjà. Le piège A2 (« Bonjour, je veux prêcher sur
le pardon dimanche ») est ce qui la borne, et le cahier de recette a raison de le mettre en
face : *une règle de civilité trop gourmande crée une panne pire que celle qu'elle répare*.

Coût estimé : une heure, un vocabulaire, deux tests.

---

## 8. Ce qui reste à trancher

| # | Question | Qui décide |
|---|---|---|
| T1 | Les crochets d'amplification — **dans** le verset ou à côté ? La piste « incise typographiée tirée des `ContextNote` » est compatible avec ce qui existe : c'est ce que `load_context` produit déjà, présenté autrement. | fondateur, non délégable |
| Q-RF1 | Ouvre-t-on les sources de plan curées aux quatre formes (onomastique, lexical, narratif allégorisé, expositif) ? Question de **curation**, pas de moteur. | fondateur + curation |
| Q-fil | Matérialise-t-on le fil en tours et en blocs (§11), ou le rejeu depuis la trace suffit-il ? | technique, tranchable seul |
| Q-§13 | Écrire la règle manquante : *Urim ne tranche pas une controverse entre confessions*. | fondateur |
| Q-embedding | Le modèle d'embedding contre une LSG archaïsante — la spec le note elle-même. La piste « vectoriser aussi les annotations curées » est la bonne, et elle se mesure avant de graver. | à mesurer |

---

## 9. Le premier pas que la spec de renforcement propose

> **Test D1 — faire descendre *Odyssée biblique du nom Joseph* dans le moteur.** Une heure.

Il reste valable **et il change de sens** : il ne mesure plus si `onomastique` est franchi — le
gabarit n'existe pas ici — mais ce que le moteur réel fait d'un sujet qui ne borne aucune
péricope. La réponse attendue au vu du code est `DEGRADE` : *bornes hors unité curée, la
préparation continue*, et non un refus.

**Si c'est bien ce qui arrive, RF1 perd son urgence** — le moteur ne punit pas D1, il
l'accompagne sans faisabilité relue. Si c'est un refus, RF1 redevient prioritaire.

C'est le seul point de ces quatre documents qui soit une vérification plutôt qu'une décision.
